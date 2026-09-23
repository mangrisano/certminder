"""Turn a check result plus prior state into a list of alert events.

The evaluator is pure: given the current :class:`CheckResult` and the previous
:class:`TargetState`, it returns the events to emit *this cycle* and the new
state to persist. Every problem certinspect reports is surfaced as its own
event, so a certificate with several faults raises one alert each. Problems are
deduplicated via ``active_alerts`` (a persistent fault is notified once), and a
single ``RECOVERED`` event is emitted per problem that clears.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from certminder.models import CheckResult, Event, EventKind, Severity
from certminder.state import TargetState


def _validity_event(name: str, info: dict, days: int | None) -> Event | None:
    """Return the event for the certificate's own validity status, if any.

    Read from certinspect's own (chain-independent) ``status`` field, kept
    separate from :func:`detect_problems` so a dated leaf's real cause (renew
    or wait) is decided in one place, independent of the other checks.
    """
    validity = info.get("status")
    if validity in {"EXPIRED", "INVALID DATES"}:
        ago = abs(days) if isinstance(days, int) else "?"
        return Event(
            target_name=name,
            kind=EventKind.EXPIRED,
            severity=Severity.CRITICAL,
            message=f"{name}: certificate expired {ago} day(s) ago",
            details={"days_to_expire": days},
        )
    if validity == "NOT YET VALID":
        return Event(
            target_name=name,
            kind=EventKind.NOT_YET_VALID,
            severity=Severity.CRITICAL,
            message=f"{name}: certificate is not valid yet",
        )
    if validity == "CRITICAL":
        return Event(
            target_name=name,
            kind=EventKind.CRITICAL,
            severity=Severity.CRITICAL,
            message=f"{name}: certificate expires in {days} day(s)",
            details={"days_to_expire": days},
        )
    if validity == "EXPIRING":
        return Event(
            target_name=name,
            kind=EventKind.EXPIRING,
            severity=Severity.WARNING,
            message=f"{name}: certificate expires in {days} day(s)",
            details={"days_to_expire": days},
        )
    return None


def detect_problems(result: CheckResult) -> list[Event]:
    """Return one event per distinct problem found on the certificate.

    Every dimension certinspect reports is inspected independently, so a
    certificate with several faults (say, expired *and* an untrusted chain)
    yields one event per fault instead of a single headline status that hides
    the rest. Each event carries its own severity; the caller deduplicates.
    """
    info = result.raw
    name = result.target.name
    days = result.days_to_expire
    problems: list[Event] = []

    def add(
        kind: EventKind, severity: Severity, message: str, **details: object
    ) -> None:
        problems.append(
            Event(
                target_name=name,
                kind=kind,
                severity=severity,
                message=f"{name}: {message}",
                details=details,
            )
        )

    # Validity, from certinspect's own (chain-independent) status field.
    validity_event = _validity_event(name, info, days)
    if validity_event is not None:
        problems.append(validity_event)

    # Chain of trust.
    if result.chain_trusted is False:
        diagnosis = info.get("chain_diagnosis")
        if diagnosis:
            detail = f" [{diagnosis['code']}] {diagnosis['detail']}"
        else:
            reason = info.get("chain_error")
            detail = f" ({reason})" if reason else ""
        add(
            EventKind.CHAIN_UNTRUSTED,
            Severity.CRITICAL,
            f"certificate chain is not trusted{detail}",
        )

    # Revocation.
    if result.revocation == "REVOKED":
        add(EventKind.REVOKED, Severity.CRITICAL, "certificate is REVOKED")

    # Hostname coverage.
    if result.hostname_match is False:
        add(
            EventKind.HOSTNAME_MISMATCH,
            Severity.CRITICAL,
            "certificate does not match the hostname",
        )

    # Opt-in policy checks.
    violations = info.get("policy_violations") or []
    if violations:
        add(
            EventKind.POLICY_VIOLATION,
            Severity.CRITICAL,
            f"certificate violates policy ({'; '.join(violations)})",
            violations=list(violations),
        )

    # Weak cryptography (small key, SHA-1/MD5 signature).
    weak = info.get("weak") or []
    if weak:
        add(
            EventKind.WEAK_CRYPTO,
            Severity.WARNING,
            f"weak cryptography ({'; '.join(weak)})",
            weak=list(weak),
        )

    # Intermediate/root chain certificates that are expired or near expiry.
    chain_warnings = info.get("chain_warnings") or []
    if chain_warnings:
        add(
            EventKind.CHAIN_EXPIRING,
            Severity.WARNING,
            "; ".join(chain_warnings),
            warnings=list(chain_warnings),
        )

    return problems


# Human-friendly resolution messages, keyed by the cleared problem's kind value.
_RESOLVED_MESSAGE: dict[str, str] = {
    EventKind.EXPIRED.value: "certificate is valid again",
    EventKind.EXPIRING.value: "certificate is no longer within the expiry warning window",
    EventKind.CRITICAL.value: "certificate expiry is no longer critical",
    EventKind.NOT_YET_VALID.value: "certificate is now within its validity period",
    EventKind.CHAIN_UNTRUSTED.value: "certificate chain is trusted again",
    EventKind.REVOKED.value: "certificate is no longer reported as revoked",
    EventKind.HOSTNAME_MISMATCH.value: "certificate matches the hostname again",
    EventKind.POLICY_VIOLATION.value: "certificate now satisfies the policy",
    EventKind.WEAK_CRYPTO.value: "weak-cryptography warning cleared",
    EventKind.CHAIN_EXPIRING.value: "chain-expiry warning cleared",
    EventKind.UNREACHABLE.value: "target is reachable again",
}


def _resolved_event(name: str, key: str) -> Event:
    """Build the INFO event announcing that one specific problem has cleared."""
    kind_value = key.rsplit("|", 1)[-1]
    message = _RESOLVED_MESSAGE.get(
        kind_value, f"{kind_value.replace('_', ' ')} cleared"
    )
    return Event(
        target_name=name,
        kind=EventKind.RECOVERED,
        severity=Severity.INFO,
        message=f"{name}: {message}",
        details={"resolved": kind_value},
    )


def _confirm(
    key: str, active: set[str], pending: dict[str, int], threshold: int
) -> tuple[bool, int]:
    """Return (confirmed, consecutive_count) for a detected problem.

    A problem already active stays active. A newly-seen problem is only
    confirmed once it has been detected ``threshold`` consecutive cycles; until
    then it stays pending (silent) with an incrementing count.
    """
    if key in active:
        return True, 0
    count = pending.get(key, 0) + 1
    return count >= threshold, count


def _unreachable_result(
    name: str,
    result: CheckResult,
    previous: TargetState,
    active: set[str],
    prev_notified: dict[str, float],
    expected: set[str],
    failure_threshold: int,
    due: Callable[[str], bool],
    now: float,
) -> tuple[list[Event], TargetState]:
    """Handle a target that could not be assessed this cycle.

    The certificate cannot be assessed, so surface only ``UNREACHABLE``,
    deduplicated (subject to renotify). Any per-problem alerts are dropped
    (unknown now) and re-raised when the host returns.
    """
    events: list[Event] = []
    key = f"{name}|{EventKind.UNREACHABLE.value}"
    confirmed, count = _confirm(key, active, previous.pending, failure_threshold)
    if not confirmed:
        # Within the flap window: stay silent, just remember the count.
        return events, TargetState(
            fingerprint=previous.fingerprint,
            status=result.status,
            pending={key: count},
        )
    if EventKind.UNREACHABLE.value not in expected and due(key):
        events.append(
            Event(
                target_name=name,
                kind=EventKind.UNREACHABLE,
                severity=Severity.CRITICAL,
                message=f"{name}: unreachable ({result.error or 'no detail'})",
                details={"error": result.error, "exit_code": result.exit_code},
            )
        )
        notified = now
    else:
        notified = prev_notified.get(key, now)
    return events, TargetState(
        fingerprint=previous.fingerprint,
        status=result.status,
        active_alerts=[key],
        notified_at={key: notified},
    )


def evaluate(
    result: CheckResult,
    previous: TargetState,
    *,
    now: float | None = None,
    renotify_after: int | None = None,
    failure_threshold: int = 1,
) -> tuple[list[Event], TargetState]:
    """Compare ``result`` against ``previous`` and return (events, new_state).

    Emits one event per newly-appeared problem, one INFO event per problem that
    has just cleared, and a fingerprint-change event on rotation. Every problem
    is tracked in ``active_alerts`` so a persistent fault is notified once, not
    every cycle. When ``renotify_after`` (seconds) is set, a still-active
    problem is re-emitted once that long has elapsed since it was last notified,
    so a persistent fault does not stay silent forever. With
    ``failure_threshold`` > 1 a problem must be detected that many consecutive
    cycles before it alerts, so a one-cycle blip is dampened.
    """
    now = time.time() if now is None else now
    events: list[Event] = []
    name = result.target.name
    expected = set(result.target.expect or ())
    active = set(previous.active_alerts)
    prev_notified = previous.notified_at

    def _due(key: str) -> bool:
        """Emit this key now? True when new, or its renotify interval elapsed."""
        if key not in active:
            return True
        last = prev_notified.get(key)
        return (
            renotify_after is not None
            and last is not None
            and now - last >= renotify_after
        )

    # Unreachable: no per-problem evaluation is possible this cycle.
    if not result.reachable:
        return _unreachable_result(
            name,
            result,
            previous,
            active,
            prev_notified,
            expected,
            failure_threshold,
            _due,
            now,
        )

    # Fingerprint change: report every rotation (transient, not tracked).
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
                details={"old": previous.fingerprint, "new": result.fingerprint},
            )
        )

    problems = [
        event for event in detect_problems(result) if event.kind.value not in expected
    ]
    by_key = {event.key(): event for event in problems}

    # A detected problem is only promoted to an active alert once it has
    # persisted for ``failure_threshold`` consecutive cycles; until then it is
    # tracked as pending and stays silent, so a one-cycle blip never alerts.
    new_active: set[str] = set()
    new_pending: dict[str, int] = {}
    for key in by_key:
        confirmed, count = _confirm(key, active, previous.pending, failure_threshold)
        if confirmed:
            new_active.add(key)
        else:
            new_pending[key] = count

    # A newly-confirmed problem re-shows the FULL current set, so a fresh fault
    # never hides the ones already present. Otherwise each still-active problem
    # is re-emitted only when its renotify interval has elapsed. Resolutions are
    # per problem.
    force_full = bool(new_active - active)
    notified: dict[str, float] = {}
    for key in sorted(new_active):
        if force_full or _due(key):
            events.append(by_key[key])
            notified[key] = now
        else:
            notified[key] = prev_notified.get(key, now)

    events.extend(_resolved_event(name, key) for key in sorted(active - new_active))

    return events, TargetState(
        fingerprint=result.fingerprint or previous.fingerprint,
        status=result.status,
        active_alerts=sorted(new_active),
        notified_at=notified,
        pending=new_pending,
    )
