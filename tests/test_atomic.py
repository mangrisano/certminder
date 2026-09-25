"""Tests for the atomic file writer."""

from __future__ import annotations

import stat

from certminder.atomic import atomic_write
from certminder.metrics import write_prometheus
from certminder.state import StateStore, TargetState


def _mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_atomic_write_is_private_by_default(tmp_path):
    path = tmp_path / "sub" / "file.txt"
    atomic_write(path, "hello")
    assert path.read_text() == "hello"
    assert _mode(path) == 0o600
    assert list(path.parent.iterdir()) == [path]  # no temp file left behind


def test_atomic_write_honours_mode(tmp_path):
    path = tmp_path / "file.txt"
    atomic_write(path, "hello", mode=0o644)
    assert _mode(path) == 0o644


def test_state_file_is_private_and_metrics_readable(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.set("a:443", TargetState(status="VALID"))
    store.save()
    assert _mode(tmp_path / "state.json") == 0o600

    write_prometheus([], tmp_path / "certminder.prom")
    assert _mode(tmp_path / "certminder.prom") == 0o644
