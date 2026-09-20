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
    NOT_YET_VALID = "not_yet_valid"
    REVOKED = "revoked"
    CHAIN_UNTRUSTED = "chain_untrusted"
    HOSTNAME_MISMATCH = "hostname_mismatch"
    POLICY_VIOLATION = "policy_violation"
    WEAK_CRYPTO = "weak_crypto"
    CHAIN_EXPIRING = "chain_expiring"
    FINGERPRINT_CHANGED = "fingerprint_changed"
    UNREACHABLE = "unreachable"
    RECOVERED = "recovered"


@dataclass(frozen=True)
class Target:
    """A single certificate endpoint to watch: either a host or a local file.

    Exactly one of ``host`` or ``file`` must be set. A file target has no live
    handshake, so the host-only fields (``port``, ``starttls``,
    ``min_tls_version``, ``require_revocation_check``) do not apply to it;
    config validation rejects setting them together (see ``config.py``).
    """

    host: str | None = None
    file: str | None = None
    port: int = 443
    verify: bool = True
    days: int = 30
    critical_days: int = 15
    timeout: float = 5.0
    connect_timeout: float | None = None
    read_timeout: float | None = None
    retries: int = 0
    starttls: str | None = None
    cafile: str | None = None
    capath: str | None = None
    not_after_max: int | None = None
    cab_forum: bool = False
    require_sct: bool = False
    require_must_staple: bool = False
    require_revocation_check: bool = False
    min_tls_version: str | None = None
    profile: str | None = None
    expect: tuple[str, ...] = ()
    label: str | None = None

    def __post_init__(self) -> None:
        if (self.host is None) == (self.file is None):
            raise ValueError("a target needs exactly one of 'host' or 'file'")

    @property
    def display_host(self) -> str:
        """The host or file path this target identifies, for labels/metrics."""
        return self.host if self.host is not None else self.file

    @property
    def name(self) -> str:
        """A stable, human-readable identifier used as the state key."""
        base = f"{self.host}:{self.port}" if self.host is not None else self.file
        return f"{base} ({self.label})" if self.label else base


@dataclass(frozen=True)
class DiscoverSource:
    """A domain to expand into host targets via certinspect's CT-log discovery.

    ``target_defaults`` holds the per-target keys (e.g. ``verify``, ``profile``,
    ``cafile``, ``expect``) applied to every host discovered under ``domain`` —
    the same schema as a target, minus ``host``/``file`` (see
    ``config._build_discover_source``).
    """

    domain: str
    discover_timeout: float = 30.0
    target_defaults: dict[str, Any] = field(default_factory=dict)


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
