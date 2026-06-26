"""Turn a check result plus prior state into a list of alert events.

The evaluator is pure: given the current :class:`CheckResult` and the previous
:class:`TargetState`, it returns the events to emit *this cycle* and the new
state to persist. Deduplication lives here: a problem already present in
``active_alerts`` is not re-notified until it clears, at which point a single
``RECOVERED`` event is emitted.
"""

from __future__ import annotations

from certminder.models import CheckResult, Event, EventKind, Severity
from certminder.state import TargetState

# Map a status string to the event it raises and its severity.
_STATUS_EVENTS: dict[str, tuple[EventKind, Severity]] = {
    "EXPIRING": (EventKind.EXPIRING, Severity.WARNING),
    "CRITICAL": (EventKind.CRITICAL, Severity.CRITICAL),
    "EXPIRED": (EventKind.EXPIRED, Severity.CRITICAL),
    "REVOKED": (EventKind.REVOKED, Severity.CRITICAL),
    "CHAIN_UNTRUSTED": (EventKind.CHAIN_UNTRUSTED, Severity.CRITICAL),
    "HOSTNAME_MISMATCH": (EventKind.HOSTNAME_MISMATCH, Severity.CRITICAL),
}

_PROBLEM_STATUSES = set(_STATUS_EVENTS) | {"UNREACHABLE", "ERROR"}


def _message(result: CheckResult) -> str:
    name = result.target.name
    days = result.days_to_expire
    if result.status in {"EXPIRING", "CRITICAL"}:
        return f"{name}: certificate expires in {days} day(s)"
    if result.status == "EXPIRED":
        return f"{name}: certificate expired {abs(days) if days is not None else '?'} day(s) ago"
    if result.status == "REVOKED":
        return f"{name}: certificate is REVOKED"
    if result.status == "CHAIN_UNTRUSTED":
        return f"{name}: certificate chain is not trusted"
    if result.status == "HOSTNAME_MISMATCH":
        return f"{name}: certificate does not match the hostname"
    return f"{name}: {result.status.lower()}"


def evaluate(
    result: CheckResult, previous: TargetState
) -> tuple[list[Event], TargetState]:
    """Compare ``result`` against ``previous`` and return (events, new_state)."""
    events: list[Event] = []
    name = result.target.name
    active = set(previous.active_alerts)
    new_active: set[str] = set()

    # Unreachable / executable errors.
    if not result.reachable:
        kind = EventKind.UNREACHABLE
        key = f"{name}|{kind.value}"
        new_active.add(key)
        if key not in active:
            events.append(
                Event(
                    target_name=name,
                    kind=kind,
                    severity=Severity.CRITICAL,
                    message=f"{name}: unreachable ({result.error or 'no detail'})",
                    details={"error": result.error, "exit_code": result.exit_code},
                )
            )
        # Keep the last known fingerprint; nothing new to compare.
        return events, TargetState(
            fingerprint=previous.fingerprint,
            status=result.status,
            active_alerts=sorted(new_active),
        )

    # Fingerprint change: report on every change (after the first sighting),
    # regardless of validity — an unexpected rotation is itself the signal.
    if (
        previous.fingerprint
        and result.fingerprint
        and result.fingerprint != previous.fingerprint
    ):
        events.append(
            Event(
                target_name=name,
                kind=EventKind.FINGERPRINT_CHANGED,
                severity=Severity.WARNING,
                message=f"{name}: certificate fingerprint changed",
                details={
                    "old": previous.fingerprint,
                    "new": result.fingerprint,
                },
            )
        )

    # Validity-derived problems (deduplicated via active_alerts).
    if result.status in _STATUS_EVENTS:
        kind, severity = _STATUS_EVENTS[result.status]
        key = f"{name}|{kind.value}"
        new_active.add(key)
        if key not in active:
            events.append(
                Event(
                    target_name=name,
                    kind=kind,
                    severity=severity,
                    message=_message(result),
                    details={"days_to_expire": result.days_to_expire},
                )
            )

    # Recovery: previously had an active problem, now VALID.
    cleared = active - new_active
    if result.status == "VALID" and any(
        not k.endswith(f"|{EventKind.FINGERPRINT_CHANGED.value}") for k in cleared
    ):
        events.append(
            Event(
                target_name=name,
                kind=EventKind.RECOVERED,
                severity=Severity.INFO,
                message=f"{name}: recovered, certificate is valid again",
                details={"days_to_expire": result.days_to_expire},
            )
        )

    return events, TargetState(
        fingerprint=result.fingerprint or previous.fingerprint,
        status=result.status,
        active_alerts=sorted(new_active),
    )
