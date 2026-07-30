"""Load and validate the YAML configuration into typed objects."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from certminder.models import EventKind, Target

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

# Mirrors certinspect's --profile choices: a named bundle of the opt-in policy
# checks (a plain intensity ladder, not a compliance standard).
_VALID_PROFILES = {"lenient", "standard", "strict"}

# Problem kinds a target may acknowledge via ``expect`` (every alertable kind;
# fingerprint changes and recoveries cannot be suppressed this way).
_ACKNOWLEDGEABLE_PROBLEMS = {k.value for k in EventKind} - {
    EventKind.FINGERPRINT_CHANGED.value,
    EventKind.RECOVERED.value,
}


class ConfigError(ValueError):
    """Raised when the configuration file is missing or malformed."""


def parse_duration(value: str | int) -> int:
    """Convert a duration like '6h', '30m', '1d' (or an int) into seconds."""
    if isinstance(value, int):
        return value
    match = _DURATION_RE.match(str(value))
    if not match:
        raise ConfigError(
            f"invalid duration {value!r}; use a number with s/m/h/d (e.g. 6h)"
        )
    amount, unit = match.groups()
    return int(amount) * _UNIT_SECONDS[unit.lower()]


@dataclass
class NotifierConfig:
    """Raw notifier settings; interpreted by the notifiers package."""

    type: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class Config:
    """The fully parsed certminder configuration."""

    targets: list[Target]
    notifiers: list[NotifierConfig]
    certinspect_bin: str = "certinspect"
    interval: int = 21600  # 6h
    state_file: Path = Path("~/.certminder/state.json")
    concurrency: int = 8
    prometheus_file: Path | None = None
    startup_report: bool = True
    renotify_after: int | None = None
    heartbeat: bool = True


def _build_target(raw: dict[str, Any], defaults: dict[str, Any]) -> Target:
    if "host" not in raw:
        raise ConfigError(f"target is missing required 'host': {raw!r}")
    merged = {**defaults, **raw}
    allowed = {
        "host",
        "port",
        "verify",
        "days",
        "critical_days",
        "timeout",
        "starttls",
        "cafile",
        "capath",
        "not_after_max",
        "cab_forum",
        "require_sct",
        "require_must_staple",
        "min_tls_version",
        "profile",
        "expect",
        "label",
    }
    unknown = set(merged) - allowed
    if unknown:
        raise ConfigError(f"unknown target keys {sorted(unknown)} in {raw!r}")
    if merged.get("cab_forum") and merged.get("not_after_max") is not None:
        raise ConfigError(
            f"'cab_forum' and 'not_after_max' are mutually exclusive in {raw!r}"
        )
    profile = merged.get("profile")
    if profile is not None and profile not in _VALID_PROFILES:
        raise ConfigError(
            f"invalid profile {profile!r} in {raw!r}; "
            f"use one of {sorted(_VALID_PROFILES)}"
        )
    raw_expect = merged.get("expect")
    if raw_expect is not None:
        if not isinstance(raw_expect, list):
            raise ConfigError(f"'expect' must be a list of problem kinds in {raw!r}")
        unknown_kinds = set(raw_expect) - _ACKNOWLEDGEABLE_PROBLEMS
        if unknown_kinds:
            raise ConfigError(
                f"unknown 'expect' problem kind(s) {sorted(unknown_kinds)} in "
                f"{raw!r}; use one of {sorted(_ACKNOWLEDGEABLE_PROBLEMS)}"
            )
        merged["expect"] = tuple(raw_expect)
    return Target(**merged)


def load_config(path: str | Path) -> Config:
    """Read, parse and validate the configuration at ``path``."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - passthrough
        raise ConfigError(f"could not parse YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("top-level configuration must be a mapping")

    raw_targets = data.get("targets") or []
    defaults = data.get("defaults") or {}
    targets = [_build_target(t, defaults) for t in raw_targets]

    for index, group in enumerate(data.get("groups") or [], start=1):
        if not isinstance(group, dict):
            raise ConfigError(f"group #{index} must be a mapping")
        group_targets = group.get("targets")
        if not group_targets:
            raise ConfigError(f"group {group.get('name', index)!r} has no targets")
        # Group-level keys (other than name/targets) are shared defaults for the
        # group's targets: global defaults < group settings < per-target.
        group_defaults = {
            **defaults,
            **{k: v for k, v in group.items() if k not in ("name", "targets")},
        }
        targets += [_build_target(t, group_defaults) for t in group_targets]

    if not targets:
        raise ConfigError("at least one target is required")

    notifiers = []
    for entry in data.get("notifiers") or [{"type": "console"}]:
        if "type" not in entry:
            raise ConfigError(f"notifier is missing 'type': {entry!r}")
        options = {k: v for k, v in entry.items() if k != "type"}
        notifiers.append(NotifierConfig(type=entry["type"], options=options))

    return Config(
        targets=targets,
        notifiers=notifiers,
        certinspect_bin=data.get("certinspect_bin", "certinspect"),
        interval=parse_duration(data.get("interval", "6h")),
        state_file=Path(
            data.get("state_file", "~/.certminder/state.json")
        ).expanduser(),
        concurrency=int(data.get("concurrency", 8)),
        prometheus_file=(
            Path(data["prometheus_file"]).expanduser()
            if data.get("prometheus_file")
            else None
        ),
        startup_report=bool(data.get("startup_report", True)),
        renotify_after=(
            parse_duration(data["renotify_after"])
            if data.get("renotify_after")
            else None
        ),
        heartbeat=bool(data.get("heartbeat", True)),
    )
