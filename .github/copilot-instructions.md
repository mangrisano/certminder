# certwatch — project memory & conventions

> Single source of truth for anyone (human or agent) working on this repo.
> Read this first. It captures the design, the certinspect contract, and the
> conventions to keep the codebase coherent.

## What this project is

certwatch is a **continuous TLS certificate monitor and alerter**. It is the
"operations" layer of a small PKI tooling suite whose engine is
[**certinspect**](https://github.com/mangrisano/certinspect) (a separate repo by
the same author, published on PyPI).

- **certinspect** answers *"what is this certificate right now?"* — a one-shot
  CLI that fetches and analyses a cert (expiry, chain, OCSP/CRL, fingerprint).
- **certwatch** answers *"tell me when a certificate is about to expire, changes,
  or breaks"* — a stateful daemon/cron that runs certinspect on a schedule,
  remembers the previous state, and sends alerts on change.

certwatch deliberately **does not re-implement any TLS/X.509 logic**. All of
that lives in certinspect. certwatch is only: scheduler + state memory +
event evaluation + notifications.

## The certinspect contract (critical — do not break)

certwatch invokes certinspect as a **subprocess, one target per invocation**,
with `--json`, and trusts the **exit code** as the authoritative status:

| exit | meaning                                   | certwatch status      |
|------|-------------------------------------------|-----------------------|
| 0    | VALID                                     | `VALID`               |
| 3    | EXPIRING (within `--days`)                | `EXPIRING`            |
| 4    | CRITICAL / EXPIRED / INVALID DATES        | `CRITICAL` or `EXPIRED` (by `days_to_expire`) |
| 5    | hostname mismatch                         | `HOSTNAME_MISMATCH`   |
| 6    | chain untrusted **or** revoked            | `CHAIN_UNTRUSTED` or `REVOKED` (by `revocation_status`) |
| 7    | pin mismatch (we don't pass `--pin`)      | `PIN_MISMATCH`        |
| 1/2/other | runtime/usage error (e.g. unreachable) | `UNREACHABLE`       |

certinspect's `--json` prints a **JSON array** of `info` dicts (one element
per target). Fields certwatch relies on: `days_to_expire`,
`fingerprint_sha256`, `revocation_status` (only with `--verify`),
`chain_trusted`, `hostname_match`. Note the JSON does **not** contain the
target name or a top-level status string — that's why we run one target at a
time and read the exit code.

All of this lives in `src/certwatch/engine.py`. If certinspect's flags or exit
codes change, update `engine.py` and `tests/test_engine.py` together.

## Architecture / module map

```
src/certwatch/
  models.py      Target, CheckResult, Event, EventKind, Severity (dataclasses)
  config.py      load_config(yaml) -> Config; parse_duration("6h"->21600)
  engine.py      check_target(Target) -> CheckResult  (calls certinspect)
  state.py       StateStore (atomic JSON), TargetState
  evaluator.py   evaluate(result, previous) -> (events, new_state)  [PURE]
  scheduler.py   run_once(config) / run_loop(config); ThreadPoolExecutor
  cli.py         subcommands: once | run | check
  notifiers/
    base.py      Notifier ABC; send(events) must NOT raise
    console.py   stdout/stderr
    slack.py     Slack incoming webhook (stdlib urllib)
    webhook.py   generic JSON POST (stdlib urllib)
    __init__.py  REGISTRY + build_notifier(type, options)
```

Data flow per cycle:
`targets → engine.check_target → evaluator.evaluate(prev state) → events →
notifiers.send + state.save`.

### Key design rules
- **evaluator.py is pure** (no I/O): given a `CheckResult` + previous
  `TargetState`, return events + new state. Keep it that way — it's the most
  tested part.
- **Deduplication** lives in the evaluator via `TargetState.active_alerts`: a
  problem already active is not re-notified until it clears, then one
  `RECOVERED` (INFO) event fires. Fingerprint changes are reported on every
  change (they are the signal itself), not deduped.
- **Notifiers must swallow delivery errors** (print to stderr, never raise) so
  one broken sink can't abort the loop.
- **Networking uses the stdlib** (`urllib`), mirroring certinspect's
  zero-heavy-deps ethos. Only third-party runtime dep is **PyYAML**.
- State writes are **atomic** (`tempfile` + `os.replace`).

## Conventions (same as certinspect)
- Python ≥ 3.10, `src/` layout, setuptools, entry point `certwatch=certwatch.cli:main`.
- **Conventional Commits**, **Keep a Changelog**, **SemVer**.
- **ruff** for lint + format (`ruff check` and `ruff format --check`).
- **pytest**; tests mock the certinspect subprocess — they never hit the network.
- Comments explain *why*, not *what*. Don't add docstrings to unchanged code.
- Git identity for this repo: `michele.angrisano@gmail.com` (so commits show on
  the mangrisano GitHub profile). Release notes/changelog in **English**.

## Common commands
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]' certinspect
ruff check . && ruff format --check .
pytest -q
certwatch check example.com            # ad hoc single host
certwatch once -c certwatch.yml        # one cycle (cron)
certwatch run  -c certwatch.yml        # daemon
```

## Roadmap / next ideas
- More notifiers: email (SMTP), Telegram, PagerDuty.
- Prometheus textfile/exporter output (certinspect already speaks Prometheus).
- systemd unit + sample cron; Dockerfile.
- `--once` JSON summary output for piping.
- Optional: import certinspect as a library instead of subprocess (it's the
  same author's code) for speed — keep the subprocess path as the default
  contract.

## Operator note
Targets, notifiers, schedule and certinspect path are all configured in YAML —
see `certwatch.example.yml`. Operators edit YAML, never code.
