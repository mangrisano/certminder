"""Load and validate the YAML configuration into typed objects."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from certminder.models import Target

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


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
        "label",
    }
    unknown = set(merged) - allowed
    if unknown:
        raise ConfigError(f"unknown target keys {sorted(unknown)} in {raw!r}")
    if merged.get("cab_forum") and merged.get("not_after_max") is not None:
        raise ConfigError(
            f"'cab_forum' and 'not_after_max' are mutually exclusive in {raw!r}"
        )
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
    if not raw_targets:
        raise ConfigError("at least one target is required")

    defaults = data.get("defaults") or {}
    targets = [_build_target(t, defaults) for t in raw_targets]

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
    )
