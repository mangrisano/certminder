"""Run certinspect against a target and normalise its result.

certminder never re-implements TLS or X.509 logic: it shells out to certinspect
(one target per invocation, ``--json``) and trusts its exit code as the
authoritative status. The exit-code contract is:

    0 VALID            3 EXPIRING          4 CRITICAL / EXPIRED / NOT YET VALID
    5 HOSTNAME mismatch  6 chain untrusted or REVOKED   7 pin mismatch
    9 policy violation (validity cap, key size, SCT, Must-Staple, TLS version)
    1 runtime error (e.g. unreachable)   2 usage error
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from certminder.models import CheckResult, Status, Target

# Exit codes that still produce a usable JSON document (the certificate was
# fetched and analysed; it simply has a problem).
_ANALYSED_CODES = {0, 3, 4, 5, 6, 7, 9}

# certinspect bounds each OCSP/CRL/CA-issuer download to 60 s; a verified host
# check can chain up to three of them (OCSP, the CRL fallback, a fetched issuer).
_REVOCATION_FETCH_BUDGET = 3 * 60.0
# Process start-up, DNS resolution and the retry back-off.
_PROCESS_SLACK = 30.0


def subprocess_timeout(target: Target) -> float:
    """The longest a certinspect run for ``target`` can legitimately take.

    A host check does one TLS handshake, plus a second, verified one when
    ``verify`` is on, each retried up to ``retries`` times and each bounded by
    the connect and read timeouts; verification then adds the revocation
    downloads. Killing certinspect any earlier would turn a slow but healthy
    endpoint into a false UNREACHABLE.
    """
    if target.file is not None:
        return float(target.timeout) + _PROCESS_SLACK
    connect = (
        target.timeout if target.connect_timeout is None else target.connect_timeout
    )
    read = target.timeout if target.read_timeout is None else target.read_timeout
    handshakes = 2 if target.verify else 1
    budget = handshakes * (target.retries + 1) * (connect + read)
    if target.verify:
        budget += _REVOCATION_FETCH_BUDGET
    return budget + _PROCESS_SLACK


def _target_args(is_file: bool, target: Target) -> list[str]:
    """The positional/identifying args: what to inspect and how to reach it."""
    if is_file:
        return ["--file", target.display_host]
    return [target.display_host, "--port", str(target.port)]


def _output_args(target: Target) -> list[str]:
    """Output format and the validity thresholds certinspect scores against."""
    return [
        "--json",
        # certinspect >= 2.0 defaults to a nested v2 JSON envelope; certminder
        # reads the flat schema-1 array, so request it explicitly.
        "--schema",
        "1",
        "--timeout",
        str(target.timeout),
        "--days",
        str(target.days),
        "--critical-days",
        str(target.critical_days),
    ]


def _connection_args(target: Target) -> list[str]:
    """Verification and network-timing/retry flags."""
    args: list[str] = []
    # certinspect verifies by default, so turning it off needs --no-verify.
    args.append("--verify" if target.verify else "--no-verify")
    if target.connect_timeout is not None:
        args += ["--connect-timeout", str(target.connect_timeout)]
    if target.read_timeout is not None:
        args += ["--read-timeout", str(target.read_timeout)]
    if target.retries:
        args += ["--retries", str(target.retries)]
    return args


def _trust_args(is_file: bool, target: Target) -> list[str]:
    """How the chain is validated: STARTTLS and custom trust anchors."""
    args: list[str] = []
    if not is_file and target.starttls:
        args += ["--starttls", target.starttls]
    if target.cafile:
        args += ["--cafile", target.cafile]
    if target.capath:
        args += ["--capath", target.capath]
    return args


def _policy_args(is_file: bool, target: Target) -> list[str]:
    """Opt-in policy checks (all surface as exit code 9)."""
    args: list[str] = []
    # Maximum-validity policy: --cab-forum tracks the shrinking CA/Browser
    # Forum cap by date, --not-after-max pins an explicit limit.
    if target.cab_forum:
        args.append("--cab-forum")
    elif target.not_after_max is not None:
        args += ["--not-after-max", str(target.not_after_max)]
    if target.require_sct:
        args.append("--require-sct")
    if target.require_must_staple:
        args.append("--require-must-staple")
    if not is_file and target.require_revocation_check:
        args.append("--require-revocation-check")
    if not is_file and target.min_tls_version:
        args += ["--min-tls-version", target.min_tls_version]
    # A named policy profile bundles several of the checks above; certinspect
    # lets any explicit flag override it, so passing both is safe.
    if target.profile:
        args += ["--profile", target.profile]
    return args


def build_command(bin_path: str, target: Target) -> list[str]:
    """Assemble the certinspect command line for ``target``.

    A file target (``target.file`` set) has no live handshake, so the
    host-only flags (``--port``, ``--starttls``, ``--min-tls-version``,
    ``--require-revocation-check``) are omitted even if set on the target —
    config validation is expected to reject that combination earlier, but the
    builder stays defensive since certinspect itself would exit 2 on it.
    """
    is_file = target.file is not None
    return [
        bin_path,
        *_target_args(is_file, target),
        *_output_args(target),
        *_connection_args(target),
        *_trust_args(is_file, target),
        *_policy_args(is_file, target),
    ]


def _validity_status(info: dict[str, Any], fallback: Status) -> Status:
    """Return NOT_YET_VALID / EXPIRED from the certificate's own dates.

    Both a not-yet-valid and an expired leaf also break chain verification, so
    certinspect can report them under a higher-precedence exit code (e.g. 6,
    untrusted chain) that masks the real cause. Recovering the date-based root
    cause here keeps the alert pointed at the actual problem — renew or wait —
    instead of a generic chain error. ``fallback`` is returned when the
    certificate's own validity dates are fine.
    """
    if info.get("status") == "NOT YET VALID":
        return Status.NOT_YET_VALID
    days = info.get("days_to_expire")
    if isinstance(days, int) and days < 0:
        return Status.EXPIRED
    return fallback


# Exit codes whose status needs no look at the certificate details.
_STATUS_BY_CODE = {
    0: Status.VALID,
    3: Status.EXPIRING,
    5: Status.HOSTNAME_MISMATCH,
    7: Status.PIN_MISMATCH,
    9: Status.POLICY_VIOLATION,
}


def _status_from(exit_code: int, info: dict[str, Any]) -> Status:
    """Refine certinspect's exit code into a certminder status."""
    if exit_code == 4:
        return _validity_status(info, Status.CRITICAL)
    if exit_code == 6:
        if info.get("revocation_status") == "REVOKED":
            return Status.REVOKED
        return _validity_status(info, Status.CHAIN_UNTRUSTED)
    return _STATUS_BY_CODE.get(exit_code, Status.UNREACHABLE)


def check_target(target: Target, bin_path: str = "certinspect") -> CheckResult:
    """Inspect a single target and return a normalised :class:`CheckResult`."""
    cmd = build_command(bin_path, target)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=subprocess_timeout(target),
        )
    except FileNotFoundError:
        return CheckResult(
            target=target,
            reachable=False,
            status=Status.ERROR,
            exit_code=127,
            error=f"certinspect executable not found: {bin_path!r}",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            target=target,
            reachable=False,
            status=Status.UNREACHABLE,
            exit_code=124,
            error="certinspect timed out",
        )
    except OSError as err:
        return CheckResult(
            target=target,
            reachable=False,
            status=Status.ERROR,
            exit_code=126,
            error=f"could not run certinspect: {err}",
        )

    info: dict[str, Any] = {}
    if proc.returncode in _ANALYSED_CODES:
        try:
            parsed = json.loads(proc.stdout or "[]")
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                info = parsed[0]
        except json.JSONDecodeError:
            info = {}

    if proc.returncode not in _ANALYSED_CODES:
        return CheckResult(
            target=target,
            reachable=False,
            status=Status.UNREACHABLE,
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
