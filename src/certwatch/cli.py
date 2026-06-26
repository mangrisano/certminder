"""Command-line entry point for certwatch.

Subcommands:
    once    run a single inspection cycle and exit (ideal for cron)
    run     run continuously, sleeping ``interval`` between cycles (daemon)
    check   inspect a single host ad hoc, ignoring the config's targets
"""

from __future__ import annotations

import argparse
import sys

from certwatch import __version__
from certwatch.config import Config, ConfigError, load_config
from certwatch.engine import check_target
from certwatch.models import Target
from certwatch.scheduler import run_loop, run_once


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="certwatch",
        description="Continuously monitor TLS certificates and alert on changes.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_once = sub.add_parser("once", help="run a single inspection cycle and exit")
    p_once.add_argument("-c", "--config", required=True, help="path to certwatch.yml")

    p_run = sub.add_parser("run", help="run continuously as a daemon")
    p_run.add_argument("-c", "--config", required=True, help="path to certwatch.yml")

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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "check":
        return _cmd_check(args)

    try:
        config: Config = load_config(args.config)
    except ConfigError as exc:
        print(f"certwatch: {exc}", file=sys.stderr)
        return 2

    if args.command == "once":
        events = run_once(config)
        return 1 if events else 0

    if args.command == "run":
        try:
            run_loop(config)
        except KeyboardInterrupt:  # pragma: no cover
            print("certwatch: stopped", file=sys.stderr)
        return 0

    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
