"""Tie everything together: inspect every target, evaluate, notify, persist."""

from __future__ import annotations

import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime

from certminder.config import Config
from certminder.discovery import DiscoveryError, discover_hostnames
from certminder.engine import check_target
from certminder.evaluator import evaluate
from certminder.metrics import write_prometheus
from certminder.models import CheckResult, DiscoverSource, Event, Status, Target
from certminder.notifiers import Notifier, build_notifier
from certminder.state import StateStore, TargetState

# How long the state of a target that is no longer checked (removed from the
# config, or a discovered host that stopped showing up) is kept. A week rides
# out a discovery source being down for a few cycles without forgetting which
# alerts were already sent.
STATE_RETENTION_SECONDS = 7 * 24 * 3600


@dataclass
class CycleReport:
    """The outcome of a single inspection cycle."""

    results: list[CheckResult] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    #: False when at least one notifier failed to deliver the events; their
    #: targets keep their previous state so the events are sent again.
    delivered: bool = True

    def to_dict(self) -> dict:
        """A JSON-serialisable summary of the cycle (for ``once --json``)."""
        return {
            "targets": [
                {
                    "target": r.target.name,
                    "host": r.target.display_host,
                    "port": r.target.port if r.target.host is not None else None,
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


def _resolve_one_source(
    source: DiscoverSource, bin_path: str
) -> tuple[DiscoverSource, list[str], str | None]:
    try:
        return (
            source,
            discover_hostnames(source.domain, source.discover_timeout, bin_path),
            None,
        )
    except DiscoveryError as err:
        return source, [], str(err)


def resolve_discovered_targets(config: Config) -> list[Target]:
    """Expand ``config.discover_sources`` into host targets for this cycle.

    Queried fresh every cycle (not cached from config-load time) so a domain's
    newly-issued or expired certificates are picked up automatically. A source
    whose query fails is skipped with a warning to stderr rather than aborting
    the whole cycle — the same soft-fail approach as an unreachable target.
    """
    if not config.discover_sources:
        return []
    workers = max(1, config.concurrency)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(
            pool.map(
                lambda s: _resolve_one_source(s, config.certinspect_bin),
                config.discover_sources,
            )
        )
    targets: list[Target] = []
    for source, hostnames, err in outcomes:
        if err is not None:
            print(f"certminder: {err}", file=sys.stderr)
            continue
        targets += [Target(host=host, **source.target_defaults) for host in hostnames]
    return targets


def _all_targets(config: Config) -> list[Target]:
    """Static targets plus this cycle's discovered ones, deduped by name.

    A discovered host that coincidentally matches a static target's name (same
    host:port) is skipped, so it is inspected once and doesn't double-count
    towards events or metrics.
    """
    targets = list(config.targets)
    known_names = {t.name for t in targets}
    for target in resolve_discovered_targets(config):
        if target.name not in known_names:
            targets.append(target)
            known_names.add(target.name)
    return targets


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
    targets = _all_targets(config)

    with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
        results = list(
            pool.map(
                lambda t: check_target(t, config.certinspect_bin),
                targets,
            )
        )

    all_events: list[Event] = []
    stored: dict[str, TargetState] = {}
    now = time.time()
    for result in results:
        name = result.target.name
        stored[name] = store.get(name)
        previous = TargetState() if report_all else stored[name]
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
        store.set(name, replace(new_state, last_seen=now))
        all_events.extend(events)

    # Deliver before persisting: if a sink fails, the targets that produced
    # events keep their previous state, so the same events come up again next
    # cycle (at-least-once) instead of being marked as notified and lost.
    delivered = _deliver(notifiers, all_events) if all_events else True
    if not delivered:
        for name in {event.target_name for event in all_events}:
            if name in stored:
                store.set(name, replace(stored[name], last_seen=now))
    store.prune(now - STATE_RETENTION_SECONDS)
    store.save()

    if config.prometheus_file is not None:
        write_prometheus(results, config.prometheus_file)

    return CycleReport(results=results, events=all_events, delivered=delivered)


def _deliver(notifiers: list[Notifier], events: list[Event]) -> bool:
    """Send ``events`` to every notifier; return True when all delivered them.

    A notifier that raises (a bug, not a delivery failure it reports itself)
    is logged and skipped so the remaining sinks still get the events.
    """
    delivered = True
    for notifier in notifiers:
        try:
            if notifier.send(events) is False:
                delivered = False
        except Exception as exc:
            print(
                f"certminder: {type(notifier).__name__} failed: {exc!r}",
                file=sys.stderr,
            )
            delivered = False
    return delivered


def _safe_run_once(
    config: Config, notifiers: list[Notifier], *, report_all: bool
) -> CycleReport | None:
    """Run one cycle, logging (not raising) any error so the daemon survives."""
    try:
        return run_once(config, notifiers, report_all=report_all)
    except Exception:
        print("certminder: cycle failed, retrying next interval", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None


def _log_heartbeat(report: CycleReport) -> None:
    """Print a one-line cycle summary so a quiet daemon is visibly alive."""
    total = len(report.results)
    healthy = sum(1 for r in report.results if r.status == Status.VALID)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"{stamp} [hb] cycle complete: {total} target(s), "
        f"{healthy} ok, {total - healthy} with problems"
    )


def run_loop(
    config: Config, notifiers: list[Notifier] | None = None
) -> None:  # pragma: no cover - long-running loop
    """Run inspection cycles forever, sleeping ``interval`` between them.

    The first cycle honours ``startup_report``: when enabled it reports every
    currently-active problem, so a (re)start surfaces the current state instead
    of waiting for the next change. When ``heartbeat`` is on, a one-line summary
    is printed after each cycle so a quiet daemon is visibly alive.
    """
    notifiers = notifiers if notifiers is not None else build_notifiers(config)
    report_all = config.startup_report
    while True:
        report = _safe_run_once(config, notifiers, report_all=report_all)
        if report is not None:
            # A failed startup cycle, or a startup digest that could not be
            # delivered, keeps the digest pending for the next cycle.
            report_all = report_all and not report.delivered
            if config.heartbeat:
                _log_heartbeat(report)
        time.sleep(config.interval)
