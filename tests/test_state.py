"""Tests for the JSON state store."""

from __future__ import annotations

from certwatch.state import StateStore, TargetState


def test_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.set(
        "example.com:443",
        TargetState(
            fingerprint="AA:BB",
            status="VALID",
            active_alerts=["example.com:443|expiring"],
        ),
    )
    store.save()
    assert path.is_file()

    reloaded = StateStore(path)
    state = reloaded.get("example.com:443")
    assert state.fingerprint == "AA:BB"
    assert state.status == "VALID"
    assert state.active_alerts == ["example.com:443|expiring"]


def test_unknown_target_returns_empty_state(tmp_path):
    store = StateStore(tmp_path / "state.json")
    state = store.get("never.seen:443")
    assert state.fingerprint is None
    assert state.active_alerts == []


def test_corrupt_state_file_is_ignored(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ not json")
    store = StateStore(path)  # must not raise
    assert store.get("x:443").fingerprint is None
