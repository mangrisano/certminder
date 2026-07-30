<div align="center">

<img src="https://raw.githubusercontent.com/mangrisano/certminder/main/docs/logo.svg" alt="certminder" width="440">

[![CI](https://github.com/mangrisano/certminder/actions/workflows/ci.yml/badge.svg)](https://github.com/mangrisano/certminder/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/certminder?logo=pypi&logoColor=white&cacheSeconds=3600)](https://pypi.org/project/certminder/)
[![Python](https://img.shields.io/pypi/pyversions/certminder?logo=python&logoColor=white&cacheSeconds=3600)](https://pypi.org/project/certminder/)
[![Downloads](https://static.pepy.tech/badge/certminder)](https://pepy.tech/project/certminder)
[![License: MIT](https://img.shields.io/pypi/l/certminder?color=blue)](LICENSE)

**Scheduled checks · Expiry & revocation alerts · Fingerprint change detection · Deduplicated notifications · Console / email / Slack / webhook · Prometheus metrics**

[PyPI](https://pypi.org/project/certminder/) · [Quick start](#quick-start) · [Configure](#configure) · [Alerts](#what-it-alerts-on) · [Prometheus](#prometheus-metrics) · [Deployment](#deployment) · [Issues](https://github.com/mangrisano/certminder/issues)

</div>

**Continuous TLS certificate monitoring and alerting** — the watch loop on top
of [certinspect](https://github.com/mangrisano/certinspect).

`certinspect` tells you what a certificate looks like _right now_.
`certminder` runs it on a schedule, remembers what it saw last time, and
**alerts you when a certificate is about to expire, gets revoked, changes
fingerprint, or becomes unreachable**.

## Why a separate tool

certminder never re-implements TLS or X.509 logic — that all lives in
certinspect. certminder adds only what a monitor needs:

- a **schedule** (run once for cron, or loop as a daemon),
- **state memory** to detect _changes_ between runs,
- **deduplicated alerts** (notify once per condition, recover once),
- pluggable **notifiers** (console, email, Slack, generic webhook),
- optional **Prometheus** metrics for the node_exporter textfile collector.

## Install

```bash
pip install certminder       # pulls in certinspect automatically
# or from source:
pip install -e '.[dev]'
```

## Quick start

```bash
# inspect a single host ad hoc
certminder check example.com

# copy and edit the sample config, then:
certminder once   -c certminder.yml   # one cycle — ideal for cron
certminder run    -c certminder.yml   # run continuously as a daemon
certminder report -c certminder.yml   # print the current problems (from state)
```

## Configure

Everything is driven by a YAML file (see
[`certminder.example.yml`](certminder.example.yml)):

```yaml
interval: 6h
state_file: ~/.certminder/state.json
defaults:
  verify: true
  days: 30
  critical_days: 15
notifiers:
  - type: console
  - type: slack
    webhook_url: "https://hooks.slack.com/services/XXX/YYY/ZZZ"
    min_severity: critical # only critical events reach Slack
  - type: email
    host: smtp.example.com
    port: 587
    username: alerts@example.com
    password: CHANGE_ME
    from_addr: alerts@example.com
    to: [ops@example.com]
targets:
  - host: example.com
  - host: api.example.com
    port: 8443
  - host: mail.example.com
    starttls: smtp
  - host: internal.example.lan
    cafile: /etc/ssl/internal-ca.pem # verify against a private CA, not the public store
  - host: short-lived.example.com
    cab_forum: true # fail if validity exceeds today's CA/Browser Forum cap
  - host: hardened.example.com
    require_sct: true # require Certificate Transparency SCTs
    require_must_staple: true # require the OCSP Must-Staple extension
    min_tls_version: TLSv1.2 # require at least TLS 1.2
  - host: strict.example.com
    profile: strict # one-flag hardening bundle (lenient/standard/strict)
```

The opt-in **policy checks** (all raise `POLICY_VIOLATION`) are: `cab_forum` or
`not_after_max` (maximum validity), `require_sct` (Certificate Transparency),
`require_must_staple` (OCSP Must-Staple), and `min_tls_version` (minimum
negotiated TLS version). `cab_forum` and `not_after_max` are mutually
exclusive. A `profile` (`lenient`, `standard` or `strict`) applies a named
bundle of these checks in one line; any explicit check above overrides it.

Any notifier also accepts `min_severity` (`info`/`warning`/`critical`) to
receive only events at or above that level — e.g. keep everything on the console
but send only `critical` to Slack. Targets on an internal/private CA take
`cafile:`/`capath:` so the chain is verified against that bundle instead of the
public trust store, which avoids false `CHAIN_UNTRUSTED` alerts.

### Grouping targets (shared settings)

Put targets that share settings — say a whole installation behind its own
internal CA — under a `groups:` entry instead of repeating the keys on every
target. Group-level keys apply to all of the group's targets; precedence is
`defaults` < group < per-target. Top-level `targets:` and `groups:` can coexist.

```yaml
defaults:
  verify: true
groups:
  - name: Site A (internal CA)
    cafile: /etc/certminder/site-a-ca.pem
    targets:
      - host: iap.site-a.lan
      - host: trustapp.site-a.lan
      - host: webauth.site-a.lan
        cafile: /etc/certminder/other-ca.pem # per-target override wins
targets:
  - host: public.example.com # ungrouped, uses only defaults
```

## What it alerts on

Each certificate is inspected on every axis, so a certificate with several
faults raises **one alert per problem** (e.g. expired _and_ an untrusted chain
give two separate events) — nothing is hidden behind a single headline status.
Every problem is deduplicated independently: it is notified once and clears with
its own `RECOVERED` event. When a **new** problem appears on a certificate its
full current set is re-shown together, so a fresh fault never hides the ones
already active. On (re)start the daemon reports every currently-active problem
once (`startup_report`, on by default), so a restart surfaces the current
picture instead of staying silent until the next change. Set `renotify_after`
(e.g. `24h`) to re-alert a still-active problem periodically so a persistent
fault is never silent for long, and `heartbeat` (on by default) prints a
one-line summary after each cycle so a quiet daemon is visibly alive. Set
`failure_threshold` (e.g. `2`) to require a problem to persist that many
consecutive cycles before it alerts, so a one-cycle network blip is dampened.

| Event                  | Severity | Trigger                                           |
| ---------------------- | -------- | ------------------------------------------------- |
| `EXPIRING`             | warning  | within `--days` of expiry                         |
| `CRITICAL` / `EXPIRED` | critical | within `critical_days`, or already expired        |
| `NOT_YET_VALID`        | critical | validity period starts in the future              |
| `REVOKED`              | critical | OCSP/CRL says revoked (needs `verify`)            |
| `CHAIN_UNTRUSTED`      | critical | chain fails to validate                           |
| `HOSTNAME_MISMATCH`    | critical | cert does not match the hostname                  |
| `POLICY_VIOLATION`     | critical | fails an opt-in policy check (see below)          |
| `WEAK_CRYPTO`          | warning  | small key or SHA-1/MD5 signature                  |
| `CHAIN_EXPIRING`       | warning  | an intermediate/root CA is expired or near expiry |
| `FINGERPRINT_CHANGED`  | warning  | fingerprint differs from last cycle               |
| `UNREACHABLE`          | critical | host/handshake failed                             |
| `RECOVERED`            | info     | a specific problem cleared                        |

### Acknowledging known problems (`expect`)

Some problems are known and accepted: a test endpoint on a private CA that will
never be publicly trusted, a service that deliberately serves a shared
certificate, and so on. List those problem kinds per target in `expect` and
certminder stops alerting on them — while still alerting on **anything else**,
so a _new_, unexpected fault on the same host is never buried under the ones you
already know about.

```yaml
targets:
  - host: trustapp-cit.azero.veneto.it
    expect: [chain_untrusted, hostname_mismatch] # known: private CA + shared cert
  - host: internal.lab.example
    expect: [chain_untrusted] # internal CA, expected
```

Accepted kinds are the alertable ones: `expiring`, `critical`, `expired`,
`not_yet_valid`, `revoked`, `chain_untrusted`, `hostname_mismatch`,
`policy_violation`, `weak_crypto`, `chain_expiring`, `unreachable` (an unknown
kind is a config error).

How it behaves:

- An **expected** problem raises no alert and is not tracked as an active alert
  — it is silently accepted.
- Any **other** problem on the same target still alerts normally (with
  `expect: [chain_untrusted]`, an `EXPIRED` on that host is still reported).
- Remove a kind from `expect` and it starts alerting again on the next cycle.
- `expect` silences only the **alerts** (console/Slack/webhook/email and the
  startup digest). The Prometheus `certminder_certificate_problem` metric still
  reflects the real state, so Grafana keeps full visibility.

Each condition alerts **once**; certminder remembers it and stays quiet until it
changes, then sends a single recovery notice.

## Exit codes (`once`)

- `0` — no events this cycle
- `1` — at least one event was emitted
- `2` — configuration error

Add `--json` to `once` to print a machine-readable summary of the cycle (one
entry per target plus the events) to stdout, handy for piping:

```bash
certminder once -c certminder.yml --json | jq '.targets[] | {target, status, days_to_expire}'
```

## Prometheus metrics

Set `prometheus_file` in the config to a path inside the node_exporter
[textfile collector](https://github.com/prometheus/node_exporter#textfile-collector)
directory. certminder rewrites it atomically at the end of every cycle:

```
certminder_certificate_expiry_days{target="example.com:443",host="example.com",port="443",status="VALID"} 42
certminder_certificate_valid{...} 1
certminder_target_up{...} 1
certminder_certificate_problem{target="example.com:443",host="example.com",port="443",problem="chain_untrusted"} 1
certminder_certificate_problem{...,problem="expired"} 1
certminder_last_run_timestamp_seconds 1700000000
```

`certminder_certificate_problem` emits one series per active problem, so a
certificate with several faults is fully visible to Grafana/Alertmanager
instead of collapsing to the single `status` label — mirroring the per-problem
alerts. A healthy certificate emits no such series.

Example Alertmanager rules (per-problem, expiry, and a stalled-daemon guard):

```yaml
groups:
  - name: certminder
    rules:
      - alert: CertificateProblem
        expr: certminder_certificate_problem > 0
        for: 15m
        annotations:
          summary: "{{ $labels.problem }} on {{ $labels.target }}"
      - alert: CertificateExpiringSoon
        expr: certminder_certificate_expiry_days < 14
        for: 1h
      - alert: CertminderStalled
        expr: time() - certminder_last_run_timestamp_seconds > 86400
```

## Deployment

Ready-to-use units live in [`deploy/`](deploy/) plus a [`Dockerfile`](Dockerfile):

- **systemd timer** — [`certminder.service`](deploy/systemd/certminder.service) +
  [`certminder.timer`](deploy/systemd/certminder.timer) run one cycle on a
  schedule (cron-style, recommended).
- **systemd daemon** — [`certminder-daemon.service`](deploy/systemd/certminder-daemon.service)
  runs the `run` loop under supervision.
- **cron** — [`certminder.cron`](deploy/cron/certminder.cron) for hosts without
  systemd timers.
- **Docker** — multi-stage build; mount your `certminder.yml` at
  `/etc/certminder/certminder.yml` and a volume at `/var/lib/certminder`.

### Docker

Build the image:

```bash
docker build -t certminder .
```

Run a single cycle (cron-style — config and state mounted from the host):

```bash
docker run --rm \
  -v "$PWD/certminder.yml:/etc/certminder/certminder.yml:ro" \
  -v certminder-state:/var/lib/certminder \
  certminder once -c /etc/certminder/certminder.yml
```

Run continuously as a daemon (this is the default `CMD`):

```bash
docker run -d --name certminder \
  --restart unless-stopped \
  -v "$PWD/certminder.yml:/etc/certminder/certminder.yml:ro" \
  -v certminder-state:/var/lib/certminder \
  certminder
```

The named volume `certminder-state` persists `state.json` and the Prometheus
file across restarts — keep it so deduplication survives container recreation.
The console notifier prints to stdout; read it with `docker logs -f certminder`
(timestamps from Docker with `-t`, or set `timestamp: true` on the console
notifier). The container runs in **UTC**.

### Docker Compose

```yaml
services:
  certminder:
    build: . # or: image: certminder
    container_name: certminder
    restart: unless-stopped
    command: run -c /etc/certminder/certminder.yml
    volumes:
      - ./certminder.yml:/etc/certminder/certminder.yml:ro
      - certminder-state:/var/lib/certminder
    logging: # cap the daemon's logs so they don't grow without bound
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

volumes:
  certminder-state:
```

```bash
docker compose up -d            # build (if needed) and start the daemon
docker compose logs -f certminder
docker compose up -d --build    # rebuild after upgrading certminder/certinspect
docker compose down             # stop and remove
```

## Development

```bash
ruff check . && ruff format --check .
pytest -q
```

Tests mock the certinspect subprocess, so the suite never touches the network.

## Support

If certminder is useful to you, the best ways to support it are:

- Star the repo to help others discover it
- [Open an issue](https://github.com/mangrisano/certminder/issues) for bugs or ideas
- Send a pull request
- Share it with others who monitor TLS certificates

## License

MIT — see [LICENSE](LICENSE).
