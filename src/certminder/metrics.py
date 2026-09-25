"""Render check results as Prometheus textfile-collector metrics.

The output is meant to be pointed at by the node_exporter ``textfile``
collector (``--collector.textfile.directory``). One ``.prom`` file is rewritten
atomically at the end of every cycle so a scrape never sees a half-written file.
"""

from __future__ import annotations

import time
from pathlib import Path

from certminder.atomic import atomic_write
from certminder.evaluator import detect_problems
from certminder.models import CheckResult, Status


def _escape_label(value: str) -> str:
    """Escape a Prometheus label value (backslash, quote, newline)."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _render_labels(**parts: str) -> str:
    inner = ",".join(f'{k}="{_escape_label(v)}"' for k, v in parts.items())
    return "{" + inner + "}"


def _target_labels(result: CheckResult, **extra: str) -> dict[str, str]:
    target = result.target
    return {
        "target": target.name,
        "host": target.display_host,
        "port": str(target.port) if target.host is not None else "",
        **extra,
    }


def _labels(result: CheckResult) -> str:
    return _render_labels(**_target_labels(result, status=result.status))


def _problem_labels(result: CheckResult, problem: str) -> str:
    return _render_labels(**_target_labels(result, problem=problem))


def _problem_kinds(result: CheckResult) -> list[str]:
    """Return the kind value of every active problem on ``result``.

    Mirrors the evaluator, so a certificate with several faults produces one
    series per fault instead of collapsing to a single headline status.
    """
    if not result.reachable:
        return ["unreachable"]
    return [event.kind.value for event in detect_problems(result)]


def render(results: list[CheckResult], *, now: float | None = None) -> str:
    """Build the Prometheus exposition text for ``results``."""
    timestamp = time.time() if now is None else now
    lines: list[str] = [
        "# HELP certminder_certificate_expiry_days Days until the certificate expires.",
        "# TYPE certminder_certificate_expiry_days gauge",
    ]
    lines.extend(
        f"certminder_certificate_expiry_days{_labels(result)} {result.days_to_expire}"
        for result in results
        if result.days_to_expire is not None
    )

    lines += [
        "# HELP certminder_certificate_valid Whether the certificate is currently valid (1) or not (0).",
        "# TYPE certminder_certificate_valid gauge",
    ]
    for result in results:
        valid = 1 if result.status == Status.VALID else 0
        lines.append(f"certminder_certificate_valid{_labels(result)} {valid}")

    lines += [
        "# HELP certminder_target_up Whether the target was reachable this cycle (1) or not (0).",
        "# TYPE certminder_target_up gauge",
    ]
    for result in results:
        up = 1 if result.reachable else 0
        lines.append(f"certminder_target_up{_labels(result)} {up}")

    lines += [
        "# HELP certminder_certificate_problem An active problem on the certificate (one series per problem).",
        "# TYPE certminder_certificate_problem gauge",
    ]
    for result in results:
        for problem in _problem_kinds(result):
            lines.append(
                f"certminder_certificate_problem{_problem_labels(result, problem)} 1"
            )

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
    # World-readable: the node_exporter textfile collector usually runs as
    # another user. The metrics carry nothing secret.
    atomic_write(path, render(results, now=now), mode=0o644)
