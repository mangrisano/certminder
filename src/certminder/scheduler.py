"""Tie everything together: inspect every target, evaluate, notify, persist."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

from certminder.config import Config
from certminder.engine import check_target
from certminder.evaluator import evaluate
from certminder.metrics import write_prometheus
from certminder.models import CheckResult, Event
from certminder.notifiers import Notifier, build_notifier
from certminder.state import StateStore, TargetState


@dataclass
class CycleReport:
    """The outcome of a single inspection cycle."""

    results: list[CheckResult] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    def to_dict(self) -> dict:
        """A JSON-serialisable summary of the cycle (for ``once --json``)."""
        return {
            "targets": [
                {
                    "target": r.target.name,
                    "host": r.target.host,
                    "port": r.target.port,
                    "status": r.status,
                    "reachable": r.reachable,
                    "days_to_expire": r.days_to_expire,
                    "fingerprint": r.fingerprint,
                    "exit_code": r.exit_code,
                    "error": r.error,
                }
                for r in self.results
            ],
            "events": [
                {
                    "target": e.target_name,
                    "kind": e.kind.value,
                    "severity": e.severity.value,
                    "message": e.message,
                    "details": e.details,
                }
                for e in self.events
            ],
        }


def build_notifiers(config: Config) -> list[Notifier]:
    """Instantiate the notifiers declared in the configuration."""
    return [build_notifier(n.type, n.options) for n in config.notifiers]


def run_once(
    config: Config,
    notifiers: list[Notifier] | None = None,
    *,
    report_all: bool = False,
) -> CycleReport:
    """Run a single inspection cycle and return its results and events.

    With ``report_all`` set, every currently-active problem is reported as if
    first seen (the stored state is ignored for event generation, but still
    updated), so a fresh start can surface the complete current picture instead
    of staying silent until something changes.
    """
    notifiers = notifiers if notifiers is not None else build_notifiers(config)
    store = StateStore(config.state_file)

    with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
        results = list(
            pool.map(
                lambda t: check_target(t, config.certinspect_bin),
                config.targets,
            )
        )

    all_events: list[Event] = []
    now = time.time()
    for result in results:
        previous = TargetState() if report_all else store.get(result.target.name)
        # On a startup digest we re-show everything, so confirm immediately;
        # flap dampening only applies to ongoing change-driven cycles.
        threshold = 1 if report_all else config.failure_threshold
        events, new_state = evaluate(
            result,
            previous,
            now=now,
            renotify_after=config.renotify_after,
            failure_threshold=threshold,
        )
        store.set(result.target.name, new_state)
        all_events.extend(events)

    store.save()

    if config.prometheus_file is not None:
        write_prometheus(results, config.prometheus_file)

    if all_events:
        for notifier in notifiers:
            notifier.send(all_events)

    return CycleReport(results=results, events=all_events)


def _log_heartbeat(report: CycleReport) -> None:
    """Print a one-line cycle summary so a quiet daemon is visibly alive."""
    total = len(report.results)
    healthy = sum(1 for r in report.results if r.status == "VALID")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"{stamp} [hb] cycle complete: {total} target(s), "
        f"{healthy} ok, {total - healthy} with problems"
    )


def run_loop(config: Config) -> None:  # pragma: no cover - long-running loop
    """Run inspection cycles forever, sleeping ``interval`` between them.

    The first cycle honours ``startup_report``: when enabled it reports every
    currently-active problem, so a (re)start surfaces the current state instead
    of waiting for the next change. When ``heartbeat`` is on, a one-line summary
    is printed after each cycle so a quiet daemon is visibly alive.
    """
    notifiers = build_notifiers(config)
    report_all = config.startup_report
    while True:
        report = run_once(config, notifiers, report_all=report_all)
        report_all = False
        if config.heartbeat:
            _log_heartbeat(report)
        time.sleep(config.interval)
