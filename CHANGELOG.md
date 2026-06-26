# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Email (SMTP) notifier with STARTTLS/implicit-TLS and optional authentication.
- Optional Prometheus textfile output (`prometheus_file`) exposing per-target
  expiry, validity and reachability gauges for the node_exporter collector.
- `once --json` prints a machine-readable summary of the cycle (per-target
  status and emitted events) to stdout.
- Deployment assets: systemd timer + oneshot service, a daemon service, a
  sample cron job, and a multi-stage `Dockerfile`.

## [0.1.0] - 2026-06-26

### Added

- Initial scaffold of certwatch, the continuous TLS monitoring layer on top of
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

[Unreleased]: https://github.com/mangrisano/certwatch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mangrisano/certwatch/releases/tag/v0.1.0
