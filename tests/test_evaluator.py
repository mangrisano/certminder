"""Tests for the event evaluator and its deduplication logic."""

from __future__ import annotations

from certminder.evaluator import evaluate
from certminder.models import EventKind, Severity
from certminder.state import TargetState
from conftest import make_result


def test_valid_first_sighting_emits_nothing(target):
    result = make_result(target, "VALID")
    events, state = evaluate(result, TargetState())
    assert events == []
    assert state.fingerprint == "AA:BB"
    assert state.status == "VALID"


def test_expiring_emits_warning_once(target):
    result = make_result(target, "EXPIRING", days_to_expire=12)
    events, state = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert len(events) == 1
    assert events[0].kind is EventKind.EXPIRING
    assert events[0].severity is Severity.WARNING

    # Second cycle, same problem: deduplicated.
    events2, _ = evaluate(result, state)
    assert events2 == []


def test_critical_severity(target):
    result = make_result(target, "CRITICAL", days_to_expire=3)
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert events[0].kind is EventKind.CRITICAL
    assert events[0].severity is Severity.CRITICAL


def test_not_yet_valid_emits_critical(target):
    result = make_result(target, "NOT_YET_VALID", exit_code=4, days_to_expire=200)
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert len(events) == 1
    assert events[0].kind is EventKind.NOT_YET_VALID
    assert events[0].severity is Severity.CRITICAL
    assert "not valid yet" in events[0].message


def test_policy_violation_emits_critical(target):
    result = make_result(
        target,
        "POLICY_VIOLATION",
        exit_code=9,
        raw={
            "policy_violations": ["total validity 501 days exceeds the 200-day maximum"]
        },
    )
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert len(events) == 1
    assert events[0].kind is EventKind.POLICY_VIOLATION
    assert events[0].severity is Severity.CRITICAL
    assert "200-day maximum" in events[0].message


def test_fingerprint_change_emits_event(target):
    result = make_result(target, "VALID", fingerprint="CC:DD")
    events, state = evaluate(result, TargetState(fingerprint="AA:BB"))
    kinds = {e.kind for e in events}
    assert EventKind.FINGERPRINT_CHANGED in kinds
    assert state.fingerprint == "CC:DD"


def test_recovery_emits_info(target):
    prior = TargetState(
        fingerprint="AA:BB",
        status="EXPIRING",
        active_alerts=["example.com:443|expiring"],
    )
    result = make_result(target, "VALID")
    events, _ = evaluate(result, prior)
    assert any(e.kind is EventKind.RECOVERED for e in events)


def test_unreachable_emits_once_and_keeps_fingerprint(target):
    result = make_result(
        target, "UNREACHABLE", exit_code=1, error="timeout", fingerprint=None
    )
    prior = TargetState(fingerprint="AA:BB")
    events, state = evaluate(result, prior)
    assert len(events) == 1
    assert events[0].kind is EventKind.UNREACHABLE
    assert state.fingerprint == "AA:BB"  # preserved

    # Still unreachable next cycle: no repeat.
    events2, _ = evaluate(result, state)
    assert events2 == []


def test_revoked_is_critical(target):
    result = make_result(target, "REVOKED", revocation="REVOKED")
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert events[0].kind is EventKind.REVOKED
    assert events[0].severity is Severity.CRITICAL
