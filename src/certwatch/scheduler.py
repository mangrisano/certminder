"""Tie everything together: inspect every target, evaluate, notify, persist."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from certwatch.config import Config
from certwatch.engine import check_target
from certwatch.evaluator import evaluate
from certwatch.models import Event
from certwatch.notifiers import Notifier, build_notifier
from certwatch.state import StateStore


def build_notifiers(config: Config) -> list[Notifier]:
    """Instantiate the notifiers declared in the configuration."""
    return [build_notifier(n.type, n.options) for n in config.notifiers]


def run_once(config: Config, notifiers: list[Notifier] | None = None) -> list[Event]:
    """Run a single inspection cycle and return all events emitted."""
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

    if all_events:
        for notifier in notifiers:
            notifier.send(all_events)

    return all_events


def run_loop(config: Config) -> None:  # pragma: no cover - long-running loop
    """Run inspection cycles forever, sleeping ``interval`` between them."""
    notifiers = build_notifiers(config)
    while True:
        run_once(config, notifiers)
        time.sleep(config.interval)
