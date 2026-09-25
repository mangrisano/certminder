"""Expand a domain into host targets via certinspect's CT-log discovery.

certminder never re-implements Certificate Transparency lookups: it shells out
to ``certinspect --discover DOMAIN --discover-only --json`` (one domain per
invocation, mirroring how ``engine.py`` calls certinspect for a single target)
and turns the returned certificate inventory into a sorted list of concrete
(non-wildcard) hostnames, ready to become :class:`~certminder.models.Target`
instances.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Any

# Letters, digits, '-' and '_' per label; no label starts or ends with '-'. A
# CT-logged name is untrusted input, and one starting with '-' would reach
# certinspect as a command-line option.
_HOSTNAME_RE = re.compile(
    r"(?=.{1,253}$)(?!-)[a-z0-9_-]{1,63}(?<!-)(?:\.(?!-)[a-z0-9_-]{1,63}(?<!-))*",
    re.IGNORECASE,
)


class DiscoveryError(RuntimeError):
    """Raised when a --discover-only query fails or returns unusable output."""


def _extract_hostnames(records: list[dict[str, Any]]) -> tuple[list[str], int]:
    """Return the sorted, deduplicated concrete hostnames in ``records``.

    Each record's ``hostnames`` list may include wildcards (``*.example.com``);
    those name no single host to connect to and are dropped, matching
    certinspect's own ``--discover`` (non-``--discover-only``) behaviour. Names
    that are not valid hostnames are dropped too; their count is returned.
    """
    names: set[str] = set()
    invalid: set[str] = set()
    for record in records:
        for name in record.get("hostnames") or []:
            if not isinstance(name, str) or "*" in name:
                continue
            if _HOSTNAME_RE.fullmatch(name):
                names.add(name)
            else:
                invalid.add(name)
    return sorted(names), len(invalid)


def discover_hostnames(
    domain: str, timeout: float, bin_path: str = "certinspect"
) -> list[str]:
    """Return the concrete hostnames CT logs have seen for ``domain``.

    Raises :class:`DiscoveryError` when certinspect is missing, times out, exits
    non-zero, or returns output that cannot be parsed as its `--discover-only
    --json` inventory.
    """
    cmd = [
        bin_path,
        "--discover",
        domain,
        "--discover-only",
        "--json",
        "--discover-timeout",
        str(timeout),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
    except FileNotFoundError as err:
        raise DiscoveryError(f"certinspect executable not found: {bin_path!r}") from err
    except subprocess.TimeoutExpired as err:
        raise DiscoveryError(f"discovery for {domain} timed out") from err

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise DiscoveryError(
            f"discovery for {domain} failed: {detail or 'exit code ' + str(proc.returncode)}"
        )

    try:
        records = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as err:
        raise DiscoveryError(
            f"could not parse discovery output for {domain}: {err}"
        ) from err
    if not isinstance(records, list):
        raise DiscoveryError(f"unexpected discovery output for {domain}")

    hostnames, invalid = _extract_hostnames(records)
    if invalid:
        print(
            f"certminder: discovery for {domain} skipped {invalid} "
            "name(s) that are not valid hostnames",
            file=sys.stderr,
        )
    return hostnames
