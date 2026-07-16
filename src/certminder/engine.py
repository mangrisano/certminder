"""Run certinspect against a target and normalise its result.

certminder never re-implements TLS or X.509 logic: it shells out to certinspect
(one target per invocation, ``--json``) and trusts its exit code as the
authoritative status. The exit-code contract is:

    0 VALID            3 EXPIRING          4 CRITICAL / EXPIRED / INVALID DATES
    5 HOSTNAME mismatch  6 chain untrusted or REVOKED   7 pin mismatch
    9 policy violation (max validity / CA-Browser-Forum cap)
    1 runtime error (e.g. unreachable)   2 usage error
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from certminder.models import CheckResult, Target

# Exit codes that still produce a usable JSON document (the certificate was
# fetched and analysed; it simply has a problem).
_ANALYSED_CODES = {0, 3, 4, 5, 6, 7, 9}


def build_command(bin_path: str, target: Target) -> list[str]:
    """Assemble the certinspect command line for ``target``."""
    cmd = [
        bin_path,
        target.host,
        "--json",
        "--port",
        str(target.port),
        "--timeout",
        str(target.timeout),
        "--days",
        str(target.days),
        "--critical-days",
        str(target.critical_days),
    ]
    if target.verify:
        cmd.append("--verify")
    if target.starttls:
        cmd += ["--starttls", target.starttls]
    if target.cafile:
        cmd += ["--cafile", target.cafile]
    if target.capath:
        cmd += ["--capath", target.capath]
    # Opt-in maximum-validity policy: --cab-forum tracks the shrinking
    # CA/Browser Forum cap by date, --not-after-max pins an explicit limit.
    if target.cab_forum:
        cmd.append("--cab-forum")
    elif target.not_after_max is not None:
        cmd += ["--not-after-max", str(target.not_after_max)]
    return cmd


def _status_from(exit_code: int, info: dict[str, Any]) -> str:
    """Refine certinspect's exit code into a certminder status string."""
    if exit_code == 0:
        return "VALID"
    if exit_code == 3:
        return "EXPIRING"
    if exit_code == 4:
        days = info.get("days_to_expire")
        if isinstance(days, int) and days < 0:
            return "EXPIRED"
        return "CRITICAL"
    if exit_code == 5:
        return "HOSTNAME_MISMATCH"
    if exit_code == 6:
        if info.get("revocation_status") == "REVOKED":
            return "REVOKED"
        return "CHAIN_UNTRUSTED"
    if exit_code == 7:
        return "PIN_MISMATCH"
    if exit_code == 9:
        return "POLICY_VIOLATION"
    return "UNREACHABLE"


def check_target(target: Target, bin_path: str = "certinspect") -> CheckResult:
    """Inspect a single target and return a normalised :class:`CheckResult`."""
    cmd = build_command(bin_path, target)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=target.timeout + 30,
        )
    except FileNotFoundError:
        return CheckResult(
            target=target,
            reachable=False,
            status="ERROR",
            exit_code=127,
            error=f"certinspect executable not found: {bin_path!r}",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            target=target,
            reachable=False,
            status="UNREACHABLE",
            exit_code=124,
            error="certinspect timed out",
        )

    info: dict[str, Any] = {}
    if proc.returncode in _ANALYSED_CODES:
        try:
            parsed = json.loads(proc.stdout or "[]")
            if isinstance(parsed, list) and parsed:
                info = parsed[0]
        except json.JSONDecodeError:
            info = {}

    if proc.returncode not in _ANALYSED_CODES:
        return CheckResult(
            target=target,
            reachable=False,
            status="UNREACHABLE",
            exit_code=proc.returncode,
            error=(proc.stderr or proc.stdout or "").strip() or "inspection failed",
        )

    return CheckResult(
        target=target,
        reachable=True,
        status=_status_from(proc.returncode, info),
        exit_code=proc.returncode,
        days_to_expire=info.get("days_to_expire"),
        fingerprint=info.get("fingerprint_sha256"),
        revocation=info.get("revocation_status"),
        chain_trusted=info.get("chain_trusted"),
        hostname_match=info.get("hostname_match"),
        raw=info,
    )
