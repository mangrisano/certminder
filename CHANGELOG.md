# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.5.0] - 2026-09-25

### Security

- The email notifier refuses to start with `username`/`password` when both
  `use_tls` and `use_ssl` are off. It used to log in over the plain connection,
  sending the SMTP credentials in clear text. An unauthenticated relay can still
  run without TLS.

### Fixed

- The Prometheus file is written world-readable (`0644`) again, so a
  node_exporter textfile collector running as another user can read it; it had
  inherited the private `0600` mode meant for the state file. Both files are now
  flushed to disk before they replace the old one, so a crash cannot leave an
  empty file behind.
- Configuration mistakes are caught before the first cycle. `interval` must be
  positive and `concurrency` at least 1 (a zero `concurrency` used to crash the
  cycle, a zero `interval` made the daemon spin without pause), and an invalid
  notifier setting now exits with code 2 and a clear message instead of a
  traceback in the middle of the first cycle.
- `certminder report` now covers every target of the last cycle, including the
  hosts found through `discover`. It used to list only the targets written in
  the config, so a problem on a discovered host never showed up there. Each
  target's state now records when it was last checked (`last_seen`).
- The state file no longer grows forever. The state of a target that is no
  longer checked (removed from the config, or a discovered host that stopped
  showing up) is dropped after 7 days, so a discovery source that is down for a
  few cycles does not make certminder forget the alerts it already sent.
- Slow but healthy endpoints are no longer reported as unreachable. certinspect
  was killed after `timeout + 30` seconds, but a verified check does two TLS
  handshakes (each retried `retries` times, each bounded by the connect and
  read timeouts) and then up to three 60-second revocation downloads, so a
  check with `retries` or an OCSP responder that answered slowly could be cut
  off mid-way. The limit now follows that worst case.
- Alerts are no longer lost when a notifier fails to deliver them. State was
  saved before the notifiers ran, so an alert whose email or webhook failed was
  already marked as notified and never sent again. Events are now delivered
  first; if any notifier fails, the affected targets keep their previous state
  and the same events are sent again on the next cycle (at-least-once). A sink
  that did succeed may therefore see the same event twice. A startup report that
  could not be delivered is retried as well. `Notifier.send` now returns `False`
  on a delivery failure (`True` or `None` means delivered).
- The daemon no longer dies on a single bad cycle. An unexpected error during a
  cycle is logged with its traceback and the loop carries on at the next
  interval; if the startup cycle fails, the startup report is kept for the next
  one. A notifier that raises no longer stops the remaining notifiers.
- A corrupt state file (valid JSON but not an object, or a malformed entry) is
  ignored with a warning instead of crashing every start. A certinspect binary
  that exists but cannot be run is reported as an error for that target instead
  of aborting the whole cycle.

## [2.4.2] - 2026-09-25

### Fixed

- `verify: false` now actually turns chain and revocation checks off. Since
  certinspect 2.0 verifies by default, certminder only ever passed `--verify`
  and never `--no-verify`, so a target with `verify: false` (an internal or
  self-signed host) still raised a critical `chain_untrusted` alert every
  cycle. `verify: false` combined with `cafile`, `capath` or
  `require_revocation_check` is now rejected when the config is loaded,
  instead of showing up as an unreachable target.

### Changed

- Require `certinspect>=2.4.5` (was `>=2.2.0`). It brings authenticated OCSP/CRL
  answers, Ed25519/Ed448 certificates that no longer show up as unreachable,
  `--min-key-size` (and the `standard`/`strict` profiles) no longer failing
  ECDSA keys, severity-based exit-code precedence, and hardening against DNS
  rebinding, slow-drip servers and load balancers serving mixed certificates.

## [2.4.1] - 2026-09-23

### Changed

- Internal refactor, no behavioural change: deduplicated atomic file writes
  (`state.py`, `metrics.py`) into a shared `atomic_write()` helper, unified
  notifier delivery-error handling behind a `RemoteNotifier` template method,
  and split several over-complex functions (`config.load_config`,
  `engine.build_command`, `evaluator.detect_problems`/`evaluate`) into
  smaller, single-purpose helpers.

## [2.4.0] - 2026-09-20

### Added

- A target may set `file: PATH` instead of `host:` to watch a local
  certificate (PEM/DER) instead of a live endpoint (`port`, `starttls`,
  `min_tls_version` and `require_revocation_check` don't apply to it and are
  rejected at config load).
- `discover:` expands a domain into every hostname Certificate Transparency
  logs have a certificate for (via certinspect's `--discover-only`),
  re-queried every cycle so newly issued or forgotten subdomains are picked
  up automatically, without a static `targets:` entry.
- `certminder check` accepts `--file PATH` as an alternative to `HOST`, for an
  ad hoc check of a local certificate.

## [2.3.0] - 2026-09-20

### Added

- Any string value anywhere in the config — a notifier secret, a target
  `host`, `state_file`, `cafile`, `secrets_file` itself, etc. — can reference
  an environment variable with Docker Compose-style `${VAR}`/`$VAR` syntax
  (`$$` for a literal `$`). The value is resolved following an `env > file`
  order: the real environment first, then a `.env` file (parsed with
  `python-dotenv`) next to the config, or one named by a top-level
  `secrets_file:`. There is no default-value fallback: a variable that is not
  set is a configuration error.

### Changed

- `python-dotenv` is now a runtime dependency, used to parse the `.env` file
  above.

## [2.2.1] - 2026-09-18

### Changed

- Require `certinspect>=2.2.0` (was `>=2.1.1`) to track the current release.

## [2.2.0] - 2026-09-18

### Added

- `email` notifier option `order` to sort the summary body: `expiry` (default,
  soonest-expiring certificates first), `severity` (worst first), or `none`
  (in detection order).

## [2.1.0] - 2026-08-15

### Added

- Target/defaults option `require_revocation_check`, forwarded to
  certinspect's `--require-revocation-check`, so certminder can alert with
  `POLICY_VIOLATION` when OCSP/CRL cannot return a definitive `GOOD` verdict.

## [2.0.1] - 2026-08-03

### Fixed

- `certminder --version` reported a stale `1.6.0` because the version string was
  hard-coded and not bumped with the package. It is now derived from the
  installed package metadata, so it always matches the release.

## [2.0.0] - 2026-08-03

### Removed

- **Dropped Python 3.10 and 3.11.** The minimum supported version is now
  Python 3.12, matching certinspect 2.0 (a required dependency).

### Changed

- Require `certinspect >= 2.0.0` and pin its legacy JSON schema with
  `--json --schema 1`. certinspect 2.0 changed the default `--json` output to a
  nested, versioned document (schema 2); certminder reads the flat schema-1
  array, so it now requests it explicitly. Without this pin, certinspect 2.0
  output would be silently ignored — every certificate detail (expiry,
  fingerprint, revocation, hostname, policy) reported as missing.

## [1.6.0] - 2026-07-31

### Added

- Per-notifier `kinds` allowlist: scope a sink to specific event types (e.g.
  `kinds: [expired]` to receive only expired-certificate alerts), complementing
  the existing `min_severity` filter. `recovered` is itself a kind, so include
  it to also be told when a selected problem clears.

## [1.5.0] - 2026-07-30

### Added

- Per-target (and `defaults`) network-robustness options forwarded to
  certinspect: `retries` (retry transient connection failures), `connect_timeout`
  and `read_timeout` (split the single `timeout`). `retries` in particular
  prevents a transient network blip from being recorded as a false `UNREACHABLE`
  at all, rather than dampening it after the fact. Requires certinspect >= 1.11
  (now the minimum dependency).

## [1.4.0] - 2026-07-30

### Added

- `failure_threshold` (default 1): flap dampening. A problem must be detected
  for this many consecutive cycles before it alerts (and an unreachable host
  must stay down that long), so a one-cycle network blip no longer raises a
  false alarm. Pairs well with certinspect's `--retries`. The startup digest
  still reports the current state immediately.

## [1.3.0] - 2026-07-30

### Added

- Target `groups`: group targets that share settings (e.g. a whole installation
  behind its own internal CA) under a `groups:` entry instead of repeating keys
  like `cafile` on every host. Group-level keys apply to the group's targets;
  precedence is `defaults` < group < per-target. Top-level `targets:` and
  `groups:` can coexist.

## [1.2.0] - 2026-07-30

### Added

- Untrusted-chain alerts now include certinspect's `chain_diagnosis` when
  available (e.g. `[CHAIN_MISMATCH] the server sent intermediate(s) ... that do
not sign the leaf`), so the notification says _why_ the chain failed and how
  to fix it instead of only the raw OpenSSL error. Requires certinspect >= 1.10.

### Changed

- The container image now uses a Python 3.13 base, required for the presented
  chain (`get_unverified_chain`) that powers certinspect's chain diagnosis.

## [1.1.1] - 2026-07-29

### Changed

- `report --json` now uses unambiguous keys: `total_targets` (all monitored
  targets) and `with_problems` (how many have an active problem), replacing the
  ambiguous `total`.

## [1.1.0] - 2026-07-29

### Added

- `certminder report -c <config>`: print the currently-active problems from the
  last cycle's saved state (instant, no network; `--json` for machine output),
  so you can see what is wrong on demand without waiting for a cycle or reading
  the logs. Exits 1 when any target has a problem.
- `min_severity` per notifier (`info`/`warning`/`critical`): a sink receives
  only events at or above that level — e.g. keep everything on the console but
  send only `critical` to Slack.

## [1.0.0] - 2026-07-29

### Changed

- First stable release. certminder has been running in production and its
  configuration and CLI are now considered stable, so the package is classified
  as Production/Stable and follows semantic versioning from here on. No
  functional change over 0.11.0.

## [0.11.0] - 2026-07-29

### Added

- Per-target `expect`: a list of problem kinds that are known and accepted for
  that target (e.g. `[chain_untrusted, hostname_mismatch]` for a service on a
  private CA serving a shared certificate). Expected problems raise no alert and
  are not tracked, while any _other_ problem on the same target still alerts
  normally, so a new fault is never buried under the ones you already know
  about. Only the alerts are silenced — the Prometheus per-problem metric still
  reflects the real state.

## [0.10.0] - 2026-07-29

### Added

- `renotify_after` (config duration, off by default): re-emit a still-active
  problem once this long has elapsed since its last alert, so a persistent
  fault (e.g. an expired certificate left unfixed) does not stay silent between
  restarts.
- `heartbeat` (config, on by default): print a one-line summary after each
  daemon cycle (`[hb] cycle complete: N target(s), X ok, Y with problems`) so a
  quiet daemon is visibly alive rather than looking stuck.

### Changed

- The Docker image sets `PYTHONUNBUFFERED=1` so log lines (including INFO
  `RECOVERED` events and the heartbeat) appear immediately in `docker logs` /
  journald instead of being block-buffered.

## [0.9.0] - 2026-07-29

### Added

- `startup_report` (config, on by default): on daemon (re)start the first cycle
  reports every currently-active problem once before reverting to change-only
  alerts, so a restart surfaces the current picture instead of staying silent
  until the next change. Set `startup_report: false` to keep the previous
  behaviour.

## [0.8.0] - 2026-07-29

### Added

- Prometheus: a new `certminder_certificate_problem` gauge emits one series per
  active problem (labelled `problem="..."`), so a certificate with several
  faults is fully visible to Grafana/Alertmanager instead of collapsing to the
  single `status` label. A healthy target emits no such series.

### Changed

- When a new problem appears on a certificate, the full set of its currently
  active problems is re-shown together, so a freshly-detected fault never hides
  the problems already present in the alert stream. A persistent, unchanged set
  still stays silent (notify-once).

## [0.7.0] - 2026-07-29

### Added

- Each certificate is now evaluated on every axis independently, so one with
  several faults raises **one alert per problem** instead of a single headline
  status that hides the rest — e.g. an expired certificate served on an
  untrusted chain now emits both `EXPIRED` and `CHAIN_UNTRUSTED`. Every problem
  is deduplicated on its own and clears with its own `RECOVERED` event, so
  fixing one issue is reported even while others remain.
- Two new alert kinds, surfaced from data certinspect already reports:
  `WEAK_CRYPTO` (small key or SHA-1/MD5 signature) and `CHAIN_EXPIRING` (an
  intermediate or root CA in the chain is expired or near expiry) — both
  warnings.

## [0.6.1] - 2026-07-29

### Fixed

- An expired (or not-yet-valid) certificate checked with `verify: true` is now
  reported as `EXPIRED` / `NOT_YET_VALID` instead of the generic
  `CHAIN_UNTRUSTED`. An out-of-validity leaf also fails chain verification, so
  certinspect returns the higher-precedence exit code 6, which previously
  masked the real root cause; certminder now recovers it from the certificate's
  dates. `REVOKED` still takes precedence.

## [0.6.0] - 2026-07-29

### Added

- New per-target `profile` option (`lenient`, `standard` or `strict`) that
  forwards certinspect's `--profile`, applying a named bundle of the opt-in
  policy checks in one line; a breach still surfaces as `POLICY_VIOLATION`
  (exit code 9). Any explicit policy key on the same target overrides the
  profile, and an invalid profile name is rejected at config-load time.

### Changed

- Require `certinspect>=1.9.1` (was `>=1.0.0`): the `profile` option needs it,
  and it also brings certinspect's revocation-lookup hardening (SSRF guard,
  response-size cap, OCSP-freshness check).

## [0.5.0] - 2026-07-21

### Added

- Three more opt-in per-target policy checks, forwarded to certinspect and
  surfaced as `POLICY_VIOLATION` (exit code 9): `require_sct: true`
  (Certificate Transparency SCTs), `require_must_staple: true` (OCSP
  Must-Staple), and `min_tls_version: TLSv1.2` (minimum negotiated TLS
  version).
- New `NOT_YET_VALID` status/event (critical) for certificates whose validity
  period starts in the future, distinguished from `CRITICAL` via certinspect's
  `status` field.

## [0.4.0] - 2026-07-16

### Added

- Maximum-validity policy per target: `cab_forum: true` enforces the date-aware
  CA/Browser Forum cap (398 → 200 → 100 → 47 days) via certinspect's
  `--cab-forum`, or `not_after_max: N` pins an explicit limit. A breach surfaces
  certinspect's exit code 9 as the new `POLICY_VIOLATION` status/event
  (critical). The two options are mutually exclusive.

## [0.3.0] - 2026-06-27

### Added

- Optional `timestamp` flag on the console notifier: prefixes each line with the
  local date and time, useful when the output is collected into a log.
- README: Docker and Docker Compose deployment instructions (build, single
  cycle, daemon with a persistent state volume, and a ready-to-use Compose
  file).

## [0.2.0] - 2026-06-26

### Added

- Email (SMTP) notifier with STARTTLS/implicit-TLS and optional authentication.
- Optional Prometheus textfile output (`prometheus_file`) exposing per-target
  expiry, validity and reachability gauges for the node_exporter collector.
- `once --json` prints a machine-readable summary of the cycle (per-target
  status and emitted events) to stdout.
- Deployment assets: systemd timer + oneshot service, a daemon service, a
  sample cron job, and a multi-stage `Dockerfile`.
- Project logo and GitHub Actions workflows for CI and PyPI trusted publishing.

## [0.1.0] - 2026-06-26

### Added

- Initial scaffold of certminder, the continuous TLS monitoring layer on top of
  certinspect.
- `engine`: invoke certinspect per target (`--json`) and normalise its exit
  code into a status.
- `evaluator`: pure change-detection producing deduplicated alert events
  (expiry, revocation, chain, hostname, fingerprint change, unreachable,
  recovery).
- `state`: atomic JSON store of per-target fingerprint, status and active alerts.
- `config`: YAML configuration with per-target overrides and duration parsing.
- Notifiers: console, Slack incoming webhook, generic JSON webhook.
- CLI subcommands: `once`, `run`, `check`.
- Test suite covering config, engine (mocked), evaluator and state.

[Unreleased]: https://github.com/mangrisano/certminder/compare/v2.5.0...HEAD
[2.5.0]: https://github.com/mangrisano/certminder/compare/v2.4.2...v2.5.0
[2.4.2]: https://github.com/mangrisano/certminder/compare/v2.4.1...v2.4.2
[2.4.1]: https://github.com/mangrisano/certminder/compare/v2.4.0...v2.4.1
[2.4.0]: https://github.com/mangrisano/certminder/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/mangrisano/certminder/compare/v2.2.1...v2.3.0
[2.2.1]: https://github.com/mangrisano/certminder/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/mangrisano/certminder/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/mangrisano/certminder/compare/v2.0.1...v2.1.0
[2.0.1]: https://github.com/mangrisano/certminder/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/mangrisano/certminder/compare/v1.6.0...v2.0.0
[1.6.0]: https://github.com/mangrisano/certminder/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/mangrisano/certminder/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/mangrisano/certminder/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/mangrisano/certminder/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/mangrisano/certminder/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/mangrisano/certminder/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/mangrisano/certminder/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/mangrisano/certminder/compare/v0.11.0...v1.0.0
[0.11.0]: https://github.com/mangrisano/certminder/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/mangrisano/certminder/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/mangrisano/certminder/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/mangrisano/certminder/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/mangrisano/certminder/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/mangrisano/certminder/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/mangrisano/certminder/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/mangrisano/certminder/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/mangrisano/certminder/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mangrisano/certminder/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mangrisano/certminder/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mangrisano/certminder/releases/tag/v0.1.0
