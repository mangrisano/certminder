"""Tests for the event evaluator and its deduplication logic."""

from __future__ import annotations

from certminder.evaluator import evaluate
from certminder.models import EventKind, Severity
from certminder.state import TargetState
from conftest import make_result


def test_valid_first_sighting_emits_nothing(target):
    result = make_result(target, "VALID", raw={"status": "VALID"})
    events, state = evaluate(result, TargetState())
    assert events == []
    assert state.fingerprint == "AA:BB"
    assert state.status == "VALID"
    assert state.active_alerts == []


def test_expiring_emits_warning_once(target):
    result = make_result(
        target, "EXPIRING", days_to_expire=12, raw={"status": "EXPIRING"}
    )
    events, state = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert len(events) == 1
    assert events[0].kind is EventKind.EXPIRING
    assert events[0].severity is Severity.WARNING

    # Second cycle, same problem: deduplicated.
    events2, _ = evaluate(result, state)
    assert events2 == []


def test_critical_severity(target):
    result = make_result(
        target, "CRITICAL", days_to_expire=3, raw={"status": "CRITICAL"}
    )
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert events[0].kind is EventKind.CRITICAL
    assert events[0].severity is Severity.CRITICAL


def test_not_yet_valid_emits_critical(target):
    result = make_result(
        target, "NOT_YET_VALID", days_to_expire=200, raw={"status": "NOT YET VALID"}
    )
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert len(events) == 1
    assert events[0].kind is EventKind.NOT_YET_VALID
    assert events[0].severity is Severity.CRITICAL
    assert "not valid yet" in events[0].message


def test_policy_violation_emits_critical(target):
    result = make_result(
        target,
        "POLICY_VIOLATION",
        raw={
            "status": "VALID",
            "policy_violations": [
                "total validity 501 days exceeds the 200-day maximum"
            ],
        },
    )
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert len(events) == 1
    assert events[0].kind is EventKind.POLICY_VIOLATION
    assert events[0].severity is Severity.CRITICAL
    assert "200-day maximum" in events[0].message


def test_chain_untrusted_emits_critical(target):
    result = make_result(
        target,
        "CHAIN_UNTRUSTED",
        chain_trusted=False,
        raw={"status": "VALID", "chain_error": "unable to get local issuer"},
    )
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert len(events) == 1
    assert events[0].kind is EventKind.CHAIN_UNTRUSTED
    assert "unable to get local issuer" in events[0].message


def test_revoked_is_critical(target):
    result = make_result(
        target, "REVOKED", revocation="REVOKED", raw={"status": "VALID"}
    )
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert events[0].kind is EventKind.REVOKED
    assert events[0].severity is Severity.CRITICAL


def test_hostname_mismatch_is_critical(target):
    result = make_result(
        target, "HOSTNAME_MISMATCH", hostname_match=False, raw={"status": "VALID"}
    )
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert events[0].kind is EventKind.HOSTNAME_MISMATCH
    assert events[0].severity is Severity.CRITICAL


def test_weak_crypto_emits_warning(target):
    result = make_result(
        target, "VALID", raw={"status": "VALID", "weak": ["Weak key (1024 bit)"]}
    )
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert len(events) == 1
    assert events[0].kind is EventKind.WEAK_CRYPTO
    assert events[0].severity is Severity.WARNING
    assert "1024 bit" in events[0].message


def test_chain_expiring_emits_warning(target):
    result = make_result(
        target,
        "VALID",
        raw={
            "status": "VALID",
            "chain_warnings": ["chain certificate 'Example CA' expires in 5 days"],
        },
    )
    events, _ = evaluate(result, TargetState(fingerprint="AA:BB"))
    assert len(events) == 1
    assert events[0].kind is EventKind.CHAIN_EXPIRING
    assert events[0].severity is Severity.WARNING


def test_multiple_problems_each_emit_a_separate_event(target):
    # Expired AND untrusted chain AND hostname mismatch: three distinct alerts.
    result = make_result(
        target,
        "EXPIRED",
        days_to_expire=-236,
        chain_trusted=False,
        hostname_match=False,
        raw={"status": "EXPIRED"},
    )
    events, state = evaluate(result, TargetState(fingerprint="AA:BB"))
    kinds = {e.kind for e in events}
    assert kinds == {
        EventKind.EXPIRED,
        EventKind.CHAIN_UNTRUSTED,
        EventKind.HOSTNAME_MISMATCH,
    }
    assert all(e.severity is Severity.CRITICAL for e in events)
    # All three are tracked, so an identical next cycle stays silent.
    events2, _ = evaluate(result, state)
    assert events2 == []


def test_one_problem_resolves_while_another_persists(target):
    both = make_result(
        target,
        "EXPIRED",
        days_to_expire=-236,
        chain_trusted=False,
        raw={"status": "EXPIRED"},
    )
    _, state = evaluate(both, TargetState(fingerprint="AA:BB"))

    # Chain fixed but still expired: one RECOVERED for the chain, expired stays.
    still_expired = make_result(
        target, "EXPIRED", days_to_expire=-236, raw={"status": "EXPIRED"}
    )
    events, state2 = evaluate(still_expired, state)
    assert len(events) == 1
    assert events[0].kind is EventKind.RECOVERED
    assert events[0].severity is Severity.INFO
    assert "chain is trusted again" in events[0].message
    assert any(k.endswith("|expired") for k in state2.active_alerts)


def test_fingerprint_change_emits_event(target):
    result = make_result(target, "VALID", fingerprint="CC:DD", raw={"status": "VALID"})
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
    result = make_result(target, "VALID", raw={"status": "VALID"})
    events, state = evaluate(result, prior)
    assert any(e.kind is EventKind.RECOVERED for e in events)
    assert state.active_alerts == []


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
