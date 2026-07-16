"""Data structures shared across certminder.

These dataclasses are deliberately small and serializable so they can be
passed to notifiers and written to the state file without ceremony.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """Ordered alert severity, low to high."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EventKind(str, Enum):
    """The kinds of change certminder reports.

    The first group derives from the certificate's own state; ``RECOVERED`` is
    emitted once when a target returns to ``VALID`` after a prior problem.
    """

    EXPIRING = "expiring"
    CRITICAL = "critical"
    EXPIRED = "expired"
    REVOKED = "revoked"
    CHAIN_UNTRUSTED = "chain_untrusted"
    HOSTNAME_MISMATCH = "hostname_mismatch"
    POLICY_VIOLATION = "policy_violation"
    FINGERPRINT_CHANGED = "fingerprint_changed"
    UNREACHABLE = "unreachable"
    RECOVERED = "recovered"


@dataclass(frozen=True)
class Target:
    """A single certificate endpoint to watch."""

    host: str
    port: int = 443
    verify: bool = True
    days: int = 30
    critical_days: int = 15
    timeout: float = 5.0
    starttls: str | None = None
    cafile: str | None = None
    capath: str | None = None
    not_after_max: int | None = None
    cab_forum: bool = False
    label: str | None = None

    @property
    def name(self) -> str:
        """A stable, human-readable identifier used as the state key."""
        base = f"{self.host}:{self.port}"
        return f"{base} ({self.label})" if self.label else base


@dataclass
class CheckResult:
    """The outcome of inspecting one target in a single cycle."""

    target: Target
    reachable: bool
    status: str
    exit_code: int
    days_to_expire: int | None = None
    fingerprint: str | None = None
    revocation: str | None = None
    chain_trusted: bool | None = None
    hostname_match: bool | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """Something worth telling a human about."""

    target_name: str
    kind: EventKind
    severity: Severity
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def key(self) -> str:
        """Identity used to deduplicate repeated alerts across cycles."""
        return f"{self.target_name}|{self.kind.value}"
