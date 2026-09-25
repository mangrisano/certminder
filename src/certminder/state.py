"""Persist what we knew about each target between runs.

The state file is a small JSON document keyed by target name. For each target
we remember the last fingerprint and status (to detect *changes*) and the set
of currently-active alert keys (so we notify once per condition, not every
cycle).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from certminder.atomic import atomic_write


@dataclass
class TargetState:
    """What we remembered about a single target after the previous cycle."""

    fingerprint: str | None = None
    status: str | None = None
    active_alerts: list[str] = field(default_factory=list)
    notified_at: dict[str, float] = field(default_factory=dict)
    pending: dict[str, int] = field(default_factory=dict)
    #: When the target was last checked (epoch seconds); None for state written
    #: by a certminder older than 2.5.
    last_seen: float | None = None

    def to_dict(self) -> dict:
        return {
            "fingerprint": self.fingerprint,
            "status": self.status,
            "active_alerts": sorted(self.active_alerts),
            "notified_at": self.notified_at,
            "pending": self.pending,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TargetState:
        last_seen = data.get("last_seen")
        return cls(
            fingerprint=data.get("fingerprint"),
            status=data.get("status"),
            active_alerts=list(data.get("active_alerts", [])),
            notified_at=dict(data.get("notified_at", {})),
            pending=dict(data.get("pending", {})),
            last_seen=None if last_seen is None else float(last_seen),
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
        if not isinstance(data, dict):
            print(
                f"certminder: ignoring malformed state file {self.path}",
                file=sys.stderr,
            )
            return
        for name, entry in data.items():
            try:
                self._states[name] = TargetState.from_dict(entry)
            except (AttributeError, TypeError, ValueError):
                print(
                    f"certminder: ignoring malformed state for {name!r}",
                    file=sys.stderr,
                )

    def get(self, name: str) -> TargetState:
        """Return the stored state for ``name`` (empty if never seen)."""
        return self._states.get(name, TargetState())

    def set(self, name: str, state: TargetState) -> None:
        """Update the in-memory state for ``name``."""
        self._states[name] = state

    def prune(self, cutoff: float) -> None:
        """Forget targets not checked since ``cutoff`` (epoch seconds).

        A target removed from the config, or a discovered host that no longer
        shows up, would otherwise stay in the file forever. Entries without a
        ``last_seen`` (written before it existed) that were not refreshed by the
        current cycle are dropped too.
        """
        self._states = {
            name: state
            for name, state in self._states.items()
            if state.last_seen is not None and state.last_seen >= cutoff
        }

    def last_cycle(self) -> dict[str, TargetState] | None:
        """The targets checked by the most recent cycle, by name.

        Every target of a cycle is stamped with the same ``last_seen``, so they
        are the entries sharing the latest one. None when no entry has a
        ``last_seen`` yet (no cycle has run, or the state predates it).
        """
        seen = [s.last_seen for s in self._states.values() if s.last_seen is not None]
        if not seen:
            return None
        latest = max(seen)
        return {
            name: state
            for name, state in self._states.items()
            if state.last_seen == latest
        }

    def save(self) -> None:
        """Atomically write the state to disk."""
        payload = {name: st.to_dict() for name, st in self._states.items()}
        atomic_write(self.path, json.dumps(payload, indent=2, sort_keys=True))
