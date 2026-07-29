"""Command-line entry point for certminder.

Subcommands:
    once    run a single inspection cycle and exit (ideal for cron)
    run     run continuously, sleeping ``interval`` between cycles (daemon)
    report  print the current problems from the last cycle's saved state
    check   inspect a single host ad hoc, ignoring the config's targets
"""

from __future__ import annotations

import argparse
import json
import sys

from certminder import __version__
from certminder.config import Config, ConfigError, load_config
from certminder.engine import check_target
from certminder.models import Target
from certminder.scheduler import run_loop, run_once
from certminder.state import StateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="certminder",
        description="Continuously monitor TLS certificates and alert on changes.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_once = sub.add_parser("once", help="run a single inspection cycle and exit")
    p_once.add_argument("-c", "--config", required=True, help="path to certminder.yml")
    p_once.add_argument(
        "--json",
        action="store_true",
        help="print a JSON summary of the cycle to stdout",
    )

    p_run = sub.add_parser("run", help="run continuously as a daemon")
    p_run.add_argument("-c", "--config", required=True, help="path to certminder.yml")

    p_report = sub.add_parser(
        "report", help="print the current problems from the last cycle's state"
    )
    p_report.add_argument(
        "-c", "--config", required=True, help="path to certminder.yml"
    )
    p_report.add_argument(
        "--json", action="store_true", help="print a JSON report instead of text"
    )

    p_check = sub.add_parser("check", help="inspect one host ad hoc")
    p_check.add_argument("host")
    p_check.add_argument("--port", type=int, default=443)
    p_check.add_argument("--no-verify", action="store_true")
    p_check.add_argument("--starttls")
    p_check.add_argument("--bin", default="certinspect", help="certinspect path")

    return parser


def _cmd_check(args: argparse.Namespace) -> int:
    target = Target(
        host=args.host,
        port=args.port,
        verify=not args.no_verify,
        starttls=args.starttls,
    )
    result = check_target(target, args.bin)
    icon = "ok" if result.status == "VALID" else result.status
    detail = (
        f"{result.days_to_expire} day(s) left"
        if result.days_to_expire is not None
        else (result.error or "")
    )
    print(f"{target.name}: {icon} ({detail})")
    return 0 if result.status == "VALID" else 1


def _cmd_report(config: Config, as_json: bool) -> int:
    """Print the currently-active problems from the persisted state.

    Reads the last cycle's saved state (instant, no network), so it reflects
    what the daemon last saw. Exit code 1 when any target has a problem, else 0.
    """
    store = StateStore(config.state_file)
    rows = []
    for target in config.targets:
        state = store.get(target.name)
        if state.active_alerts:
            rows.append(
                {
                    "target": target.name,
                    "status": state.status,
                    "problems": sorted(
                        key.rsplit("|", 1)[-1] for key in state.active_alerts
                    ),
                }
            )

    if as_json:
        report = {
            "total_targets": len(config.targets),
            "with_problems": len(rows),
            "problems": rows,
        }
        print(json.dumps(report, indent=2))
        return 1 if rows else 0

    if not config.state_file.is_file():
        print(
            "certminder: no saved state yet — run a cycle first (`certminder once`).",
            file=sys.stderr,
        )
        return 0
    if not rows:
        print(f"All {len(config.targets)} target(s) OK.")
        return 0
    print(f"{len(rows)} of {len(config.targets)} target(s) with active problems:")
    for row in rows:
        print(f"  - {row['target']}: {', '.join(row['problems'])}")
    return 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "check":
        return _cmd_check(args)

    try:
        config: Config = load_config(args.config)
    except ConfigError as exc:
        print(f"certminder: {exc}", file=sys.stderr)
        return 2

    if args.command == "once":
        report = run_once(config)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        return 1 if report.events else 0

    if args.command == "report":
        return _cmd_report(config, args.json)

    if args.command == "run":
        try:
            run_loop(config)
        except KeyboardInterrupt:  # pragma: no cover
            print("certminder: stopped", file=sys.stderr)
        return 0

    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
