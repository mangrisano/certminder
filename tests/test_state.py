"""Tests for the JSON state store."""

from __future__ import annotations

import json

import pytest

from certminder.state import StateStore, TargetState


@pytest.mark.parametrize("content", ["[]", '"text"', "42"])
def test_non_object_state_file_is_ignored(tmp_path, capsys, content):
    path = tmp_path / "state.json"
    path.write_text(content)
    store = StateStore(path)
    assert store.get("example.com:443") == TargetState()
    assert "malformed state file" in capsys.readouterr().err


def test_last_seen_roundtrips_and_is_optional(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"a:443": {"status": "VALID"}}))
    assert StateStore(path).get("a:443").last_seen is None
    store = StateStore(path)
    store.set("a:443", TargetState(status="VALID", last_seen=123.5))
    store.save()
    assert StateStore(path).get("a:443").last_seen == 123.5


def test_prune_drops_entries_not_seen_since_cutoff(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.set("fresh:443", TargetState(last_seen=100.0))
    store.set("stale:443", TargetState(last_seen=10.0))
    store.set("legacy:443", TargetState())
    store.prune(50.0)
    assert store.get("fresh:443").last_seen == 100.0
    assert store.get("stale:443") == TargetState()
    assert store.get("legacy:443") == TargetState()


def test_last_cycle_returns_the_most_recent_targets(tmp_path):
    store = StateStore(tmp_path / "state.json")
    assert store.last_cycle() is None
    store.set("legacy:443", TargetState())
    assert store.last_cycle() is None
    store.set("a:443", TargetState(last_seen=200.0))
    store.set("b:443", TargetState(last_seen=200.0))
    store.set("old:443", TargetState(last_seen=100.0))
    assert sorted(store.last_cycle()) == ["a:443", "b:443"]


def test_malformed_entry_is_skipped_others_kept(tmp_path, capsys):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "bad:443": "not an object",
                "ok:443": {"status": "VALID", "active_alerts": ["ok:443|expiring"]},
            }
        )
    )
    store = StateStore(path)
    assert store.get("ok:443").active_alerts == ["ok:443|expiring"]
    assert store.get("bad:443") == TargetState()
    assert "'bad:443'" in capsys.readouterr().err


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


def test_roundtrip_preserves_notified_at(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.set(
        "example.com:443",
        TargetState(
            active_alerts=["example.com:443|expired"],
            notified_at={"example.com:443|expired": 1234.0},
        ),
    )
    store.save()
    state = StateStore(path).get("example.com:443")
    assert state.notified_at == {"example.com:443|expired": 1234.0}


def test_roundtrip_preserves_pending(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.set(
        "example.com:443",
        TargetState(pending={"example.com:443|unreachable": 1}),
    )
    store.save()
    state = StateStore(path).get("example.com:443")
    assert state.pending == {"example.com:443|unreachable": 1}


def test_corrupt_state_file_is_ignored(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ not json")
    store = StateStore(path)  # must not raise
    assert store.get("x:443").fingerprint is None
