"""Persist what we knew about each target between runs.

The state file is a small JSON document keyed by target name. For each target
we remember the last fingerprint and status (to detect *changes*) and the set
of currently-active alert keys (so we notify once per condition, not every
cycle).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TargetState:
    """What we remembered about a single target after the previous cycle."""

    fingerprint: str | None = None
    status: str | None = None
    active_alerts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "fingerprint": self.fingerprint,
            "status": self.status,
            "active_alerts": sorted(self.active_alerts),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TargetState":
        return cls(
            fingerprint=data.get("fingerprint"),
            status=data.get("status"),
            active_alerts=list(data.get("active_alerts", [])),
        )


class StateStore:
    """A tiny atomic JSON store for per-target state."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self._states: dict[str, TargetState] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        self._states = {
            name: TargetState.from_dict(entry) for name, entry in data.items()
        }

    def get(self, name: str) -> TargetState:
        """Return the stored state for ``name`` (empty if never seen)."""
        return self._states.get(name, TargetState())

    def set(self, name: str, state: TargetState) -> None:
        """Update the in-memory state for ``name``."""
        self._states[name] = state

    def save(self) -> None:
        """Atomically write the state to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: st.to_dict() for name, st in self._states.items()}
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
