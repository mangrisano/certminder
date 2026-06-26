"""Tie everything together: inspect every target, evaluate, notify, persist."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from certwatch.config import Config
from certwatch.engine import check_target
from certwatch.evaluator import evaluate
from certwatch.metrics import write_prometheus
from certwatch.models import CheckResult, Event
from certwatch.notifiers import Notifier, build_notifier
from certwatch.state import StateStore


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


def run_once(config: Config, notifiers: list[Notifier] | None = None) -> CycleReport:
    """Run a single inspection cycle and return its results and events."""
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
    for result in results:
        previous = store.get(result.target.name)
        events, new_state = evaluate(result, previous)
        store.set(result.target.name, new_state)
        all_events.extend(events)

    store.save()

    if config.prometheus_file is not None:
        write_prometheus(results, config.prometheus_file)

    if all_events:
        for notifier in notifiers:
            notifier.send(all_events)

    return CycleReport(results=results, events=all_events)


def run_loop(config: Config) -> None:  # pragma: no cover - long-running loop
    """Run inspection cycles forever, sleeping ``interval`` between them."""
    notifiers = build_notifiers(config)
    while True:
        run_once(config, notifiers)
        time.sleep(config.interval)
