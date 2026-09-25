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
from dataclasses import dataclass

from certminder.models import (
    CheckResult,
    Event,
    EventKind,
    Severity,
    alert_key,
    alert_kind,
)
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


def _problem(
    result: CheckResult,
    kind: EventKind,
    severity: Severity,
    message: str,
    **details: object,
) -> Event:
    name = result.target.name
    return Event(
        target_name=name,
        kind=kind,
        severity=severity,
        message=f"{name}: {message}",
        details=details,
    )


def _validity(result: CheckResult) -> Event | None:
    """Validity, from certinspect's own (chain-independent) status field."""
    return _validity_event(result.target.name, result.raw, result.days_to_expire)


def _chain_untrusted(result: CheckResult) -> Event | None:
    if result.chain_trusted is not False:
        return None
    diagnosis = result.raw.get("chain_diagnosis")
    if diagnosis:
        detail = f" [{diagnosis['code']}] {diagnosis['detail']}"
    else:
        reason = result.raw.get("chain_error")
        detail = f" ({reason})" if reason else ""
    return _problem(
        result,
        EventKind.CHAIN_UNTRUSTED,
        Severity.CRITICAL,
        f"certificate chain is not trusted{detail}",
    )


def _revoked(result: CheckResult) -> Event | None:
    if result.revocation != "REVOKED":
        return None
    return _problem(
        result, EventKind.REVOKED, Severity.CRITICAL, "certificate is REVOKED"
    )


def _hostname_mismatch(result: CheckResult) -> Event | None:
    if result.hostname_match is not False:
        return None
    return _problem(
        result,
        EventKind.HOSTNAME_MISMATCH,
        Severity.CRITICAL,
        "certificate does not match the hostname",
    )


def _policy_violation(result: CheckResult) -> Event | None:
    violations = result.raw.get("policy_violations") or []
    if not violations:
        return None
    return _problem(
        result,
        EventKind.POLICY_VIOLATION,
        Severity.CRITICAL,
        f"certificate violates policy ({'; '.join(violations)})",
        violations=list(violations),
    )


def _weak_crypto(result: CheckResult) -> Event | None:
    """Small key, or a SHA-1/MD5 signature."""
    weak = result.raw.get("weak") or []
    if not weak:
        return None
    return _problem(
        result,
        EventKind.WEAK_CRYPTO,
        Severity.WARNING,
        f"weak cryptography ({'; '.join(weak)})",
        weak=list(weak),
    )


def _chain_expiring(result: CheckResult) -> Event | None:
    """Intermediate or root certificates that are expired or near expiry."""
    warnings = result.raw.get("chain_warnings") or []
    if not warnings:
        return None
    return _problem(
        result,
        EventKind.CHAIN_EXPIRING,
        Severity.WARNING,
        "; ".join(warnings),
        warnings=list(warnings),
    )


#: One check per problem dimension, in the order their events are reported.
#: A new kind of problem is a new function here, plus its EventKind and its
#: entry in _RESOLVED_MESSAGE.
DETECTORS: tuple[Callable[[CheckResult], Event | None], ...] = (
    _validity,
    _chain_untrusted,
    _revoked,
    _hostname_mismatch,
    _policy_violation,
    _weak_crypto,
    _chain_expiring,
)


def detect_problems(result: CheckResult) -> list[Event]:
    """Return one event per distinct problem found on the certificate.

    Every dimension certinspect reports is inspected independently, so a
    certificate with several faults (say, expired *and* an untrusted chain)
    yields one event per fault instead of a single headline status that hides
    the rest. Each event carries its own severity; the caller deduplicates.
    """
    return [event for detect in DETECTORS if (event := detect(result)) is not None]


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
    kind_value = alert_kind(key)
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


@dataclass(frozen=True)
class _Cycle:
    """What one evaluation needs to know besides the problems themselves."""

    result: CheckResult
    previous: TargetState
    now: float
    renotify_after: int | None
    failure_threshold: int

    @property
    def name(self) -> str:
        return self.result.target.name

    @property
    def expected(self) -> set[str]:
        return set(self.result.target.expect or ())

    @property
    def active(self) -> set[str]:
        return set(self.previous.active_alerts)

    def due(self, key: str) -> bool:
        """Emit this key now? True when new, or its renotify interval elapsed."""
        if key not in self.previous.active_alerts:
            return True
        last = self.previous.notified_at.get(key)
        return (
            self.renotify_after is not None
            and last is not None
            and self.now - last >= self.renotify_after
        )

    def confirm(self, key: str) -> tuple[bool, int]:
        return _confirm(key, self.active, self.previous.pending, self.failure_threshold)

    def last_notified(self, key: str) -> float:
        return self.previous.notified_at.get(key, self.now)


def _unreachable_result(cycle: _Cycle) -> tuple[list[Event], TargetState]:
    """Handle a target that could not be assessed this cycle.

    The certificate cannot be assessed, so surface only ``UNREACHABLE``,
    deduplicated (subject to renotify). Any per-problem alerts are dropped
    (unknown now) and re-raised when the host returns.
    """
    result, previous, name = cycle.result, cycle.previous, cycle.name
    events: list[Event] = []
    key = alert_key(name, EventKind.UNREACHABLE)
    confirmed, count = cycle.confirm(key)
    if not confirmed:
        # Within the flap window: stay silent, just remember the count.
        return events, TargetState(
            fingerprint=previous.fingerprint,
            status=result.status,
            pending={key: count},
        )
    if EventKind.UNREACHABLE.value not in cycle.expected and cycle.due(key):
        events.append(
            Event(
                target_name=name,
                kind=EventKind.UNREACHABLE,
                severity=Severity.CRITICAL,
                message=f"{name}: unreachable ({result.error or 'no detail'})",
                details={"error": result.error, "exit_code": result.exit_code},
            )
        )
        notified = cycle.now
    else:
        notified = cycle.last_notified(key)
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
    cycle = _Cycle(result, previous, now, renotify_after, failure_threshold)

    # Unreachable: no per-problem evaluation is possible this cycle.
    if not result.reachable:
        return _unreachable_result(cycle)

    events: list[Event] = []
    name = cycle.name
    expected = cycle.expected
    active = cycle.active

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
        confirmed, count = cycle.confirm(key)
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
        if force_full or cycle.due(key):
            events.append(by_key[key])
            notified[key] = now
        else:
            notified[key] = cycle.last_notified(key)

    events.extend(_resolved_event(name, key) for key in sorted(active - new_active))

    return events, TargetState(
        fingerprint=result.fingerprint or previous.fingerprint,
        status=result.status,
        active_alerts=sorted(new_active),
        notified_at=notified,
        pending=new_pending,
    )
