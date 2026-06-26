# certwatch

**Continuous TLS certificate monitoring and alerting** — the watch loop on top
of [certinspect](https://github.com/mangrisano/certinspect).

`certinspect` tells you what a certificate looks like _right now_.
`certwatch` runs it on a schedule, remembers what it saw last time, and
**alerts you when a certificate is about to expire, gets revoked, changes
fingerprint, or becomes unreachable**.

## Why a separate tool

certwatch never re-implements TLS or X.509 logic — that all lives in
certinspect. certwatch adds only what a monitor needs:

- a **schedule** (run once for cron, or loop as a daemon),
- **state memory** to detect _changes_ between runs,
- **deduplicated alerts** (notify once per condition, recover once),
- pluggable **notifiers** (console, email, Slack, generic webhook),
- optional **Prometheus** metrics for the node_exporter textfile collector.

## Install

```bash
pip install certwatch       # pulls in certinspect automatically
# or from source:
pip install -e '.[dev]'
```

## Quick start

```bash
# inspect a single host ad hoc
certwatch check example.com

# copy and edit the sample config, then:
certwatch once -c certwatch.yml     # one cycle — ideal for cron
certwatch run  -c certwatch.yml     # run continuously as a daemon
```

## Configure

Everything is driven by a YAML file (see
[`certwatch.example.yml`](certwatch.example.yml)):

```yaml
interval: 6h
state_file: ~/.certwatch/state.json
defaults:
  verify: true
  days: 30
  critical_days: 15
notifiers:
  - type: console
  - type: slack
    webhook_url: "https://hooks.slack.com/services/XXX/YYY/ZZZ"
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
```

## What it alerts on

| Event                  | Severity | Trigger                                    |
| ---------------------- | -------- | ------------------------------------------ |
| `EXPIRING`             | warning  | within `--days` of expiry                  |
| `CRITICAL` / `EXPIRED` | critical | within `critical_days`, or already expired |
| `REVOKED`              | critical | OCSP/CRL says revoked (needs `verify`)     |
| `CHAIN_UNTRUSTED`      | critical | chain fails to validate                    |
| `HOSTNAME_MISMATCH`    | critical | cert does not match the hostname           |
| `FINGERPRINT_CHANGED`  | warning  | fingerprint differs from last cycle        |
| `UNREACHABLE`          | critical | host/handshake failed                      |
| `RECOVERED`            | info     | a prior problem cleared                    |

Each condition alerts **once**; certwatch remembers it and stays quiet until it
changes, then sends a single recovery notice.

## Exit codes (`once`)

- `0` — no events this cycle
- `1` — at least one event was emitted
- `2` — configuration error

Add `--json` to `once` to print a machine-readable summary of the cycle (one
entry per target plus the events) to stdout, handy for piping:

```bash
certwatch once -c certwatch.yml --json | jq '.targets[] | {target, status, days_to_expire}'
```

## Prometheus metrics

Set `prometheus_file` in the config to a path inside the node_exporter
[textfile collector](https://github.com/prometheus/node_exporter#textfile-collector)
directory. certwatch rewrites it atomically at the end of every cycle:

```
certwatch_certificate_expiry_days{target="example.com:443",host="example.com",port="443",status="VALID"} 42
certwatch_certificate_valid{...} 1
certwatch_target_up{...} 1
certwatch_last_run_timestamp_seconds 1700000000
```

## Deployment

Ready-to-use units live in [`deploy/`](deploy/) plus a [`Dockerfile`](Dockerfile):

- **systemd timer** — [`certwatch.service`](deploy/systemd/certwatch.service) +
  [`certwatch.timer`](deploy/systemd/certwatch.timer) run one cycle on a
  schedule (cron-style, recommended).
- **systemd daemon** — [`certwatch-daemon.service`](deploy/systemd/certwatch-daemon.service)
  runs the `run` loop under supervision.
- **cron** — [`certwatch.cron`](deploy/cron/certwatch.cron) for hosts without
  systemd timers.
- **Docker** — multi-stage build; mount your `certwatch.yml` at
  `/etc/certwatch/certwatch.yml` and a volume at `/var/lib/certwatch`.

## Development

```bash
ruff check . && ruff format --check .
pytest -q
```

Tests mock the certinspect subprocess, so the suite never touches the network.

## License

MIT © Michele Angrisano
