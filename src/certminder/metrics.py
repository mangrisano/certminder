"""Render check results as Prometheus textfile-collector metrics.

The output is meant to be pointed at by the node_exporter ``textfile``
collector (``--collector.textfile.directory``). One ``.prom`` file is rewritten
atomically at the end of every cycle so a scrape never sees a half-written file.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from certminder.models import CheckResult


def _escape_label(value: str) -> str:
    """Escape a Prometheus label value (backslash, quote, newline)."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _labels(result: CheckResult) -> str:
    target = result.target
    parts = {
        "target": target.name,
        "host": target.host,
        "port": str(target.port),
        "status": result.status,
    }
    inner = ",".join(f'{k}="{_escape_label(v)}"' for k, v in parts.items())
    return "{" + inner + "}"


def render(results: list[CheckResult], *, now: float | None = None) -> str:
    """Build the Prometheus exposition text for ``results``."""
    timestamp = time.time() if now is None else now
    lines: list[str] = [
        "# HELP certminder_certificate_expiry_days Days until the certificate expires.",
        "# TYPE certminder_certificate_expiry_days gauge",
    ]
    for result in results:
        if result.days_to_expire is not None:
            lines.append(
                f"certminder_certificate_expiry_days{_labels(result)} "
                f"{result.days_to_expire}"
            )

    lines += [
        "# HELP certminder_certificate_valid Whether the certificate is currently valid (1) or not (0).",
        "# TYPE certminder_certificate_valid gauge",
    ]
    for result in results:
        valid = 1 if result.status == "VALID" else 0
        lines.append(f"certminder_certificate_valid{_labels(result)} {valid}")

    lines += [
        "# HELP certminder_target_up Whether the target was reachable this cycle (1) or not (0).",
        "# TYPE certminder_target_up gauge",
    ]
    for result in results:
        up = 1 if result.reachable else 0
        lines.append(f"certminder_target_up{_labels(result)} {up}")

    lines += [
        "# HELP certminder_last_run_timestamp_seconds Unix time of the last completed cycle.",
        "# TYPE certminder_last_run_timestamp_seconds gauge",
        f"certminder_last_run_timestamp_seconds {timestamp:.0f}",
    ]
    return "\n".join(lines) + "\n"


def write_prometheus(
    results: list[CheckResult], path: str | Path, *, now: float | None = None
) -> None:
    """Atomically write the Prometheus metrics for ``results`` to ``path``."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render(results, now=now)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
