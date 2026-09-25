"""Load and validate the YAML configuration into typed objects."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

from certminder.models import DiscoverSource, EventKind, Target

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

# Keys a target (or a discover source's shared defaults) may set. 'host' and
# 'file' identify what is being watched; a target needs exactly one, a
# discover source needs neither (its hosts come from CT logs).
_TARGET_KEYS = {
    "host",
    "file",
    "port",
    "verify",
    "days",
    "critical_days",
    "timeout",
    "connect_timeout",
    "read_timeout",
    "retries",
    "starttls",
    "cafile",
    "capath",
    "not_after_max",
    "cab_forum",
    "require_sct",
    "require_must_staple",
    "require_revocation_check",
    "min_tls_version",
    "profile",
    "expect",
    "label",
}

# Flags that need a live TLS handshake; meaningless (and rejected by
# certinspect itself) for a 'file' target.
_HOST_ONLY_KEYS = {"port", "starttls", "min_tls_version", "require_revocation_check"}

# Keys that only make sense with chain verification on (certinspect rejects
# them with --no-verify).
_NEEDS_VERIFY_KEYS = {"cafile", "capath", "require_revocation_check"}


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
    discover_sources: list[DiscoverSource] = field(default_factory=list)
    certinspect_bin: str = "certinspect"
    interval: int = 21600  # 6h
    state_file: Path = Path("~/.certminder/state.json")
    concurrency: int = 8
    prometheus_file: Path | None = None
    startup_report: bool = True
    renotify_after: int | None = None
    heartbeat: bool = True
    failure_threshold: int = 1


def _build_target(raw: dict[str, Any], defaults: dict[str, Any]) -> Target:
    merged = {**defaults, **raw}
    if ("host" in merged) == ("file" in merged):
        raise ConfigError(f"target needs exactly one of 'host' or 'file': {raw!r}")
    unknown = set(merged) - _TARGET_KEYS
    if unknown:
        raise ConfigError(f"unknown target keys {sorted(unknown)} in {raw!r}")
    if "file" in merged:
        # Checked against the target's own entry, not the merged result: a
        # global 'defaults: {port: 443}' is meant for host targets and simply
        # doesn't apply here, it isn't a conflict worth failing on.
        host_only = _HOST_ONLY_KEYS & set(raw)
        if host_only:
            raise ConfigError(
                f"{sorted(host_only)} apply to 'host' targets, not 'file', in {raw!r}"
            )
    _validate_policy_keys(merged, raw)
    return Target(**merged)


def _validate_policy_keys(merged: dict[str, Any], raw: dict[str, Any]) -> None:
    """Validate the policy/expect keys shared by targets and discover sources.

    Mutates ``merged["expect"]`` into a tuple in place, matching what
    :class:`~certminder.models.Target` (and :class:`DiscoverSource`, which
    stores it back into ``target_defaults``) expect.
    """
    if merged.get("cab_forum") and merged.get("not_after_max") is not None:
        raise ConfigError(
            f"'cab_forum' and 'not_after_max' are mutually exclusive in {raw!r}"
        )
    if merged.get("verify") is False:
        needs_verify = sorted(
            key for key in _NEEDS_VERIFY_KEYS if merged.get(key) not in (None, False)
        )
        if needs_verify:
            raise ConfigError(
                f"{needs_verify} cannot be combined with 'verify: false' in {raw!r}"
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


def _build_discover_source(
    raw: dict[str, Any], defaults: dict[str, Any]
) -> DiscoverSource:
    """Build a :class:`DiscoverSource` from a ``discover:`` entry.

    ``defaults`` (the config's top-level ``defaults:``) seeds the per-target
    settings applied to every host discovered under this domain, same as for a
    static target; any key on the entry itself overrides it.
    """
    if "domain" not in raw:
        raise ConfigError(f"discover entry is missing required 'domain': {raw!r}")
    merged = {**defaults, **raw}
    domain = merged.pop("domain")
    discover_timeout = merged.pop("discover_timeout", 30.0)
    unknown = set(merged) - (_TARGET_KEYS - {"host", "file"})
    if unknown:
        raise ConfigError(f"unknown discover keys {sorted(unknown)} in {raw!r}")
    _validate_policy_keys(merged, raw)
    return DiscoverSource(
        domain=domain,
        discover_timeout=float(discover_timeout),
        target_defaults=merged,
    )


def _load_environment(config_path: Path, secrets_file: str | None) -> dict[str, str]:
    """Merge a secrets ``.env`` file with the real environment (env wins).

    Parsing is delegated to ``python-dotenv``'s ``dotenv_values``, which reads
    (without touching the real environment) rather than mutates ``os.environ``,
    so this stays a pure merge: a variable already set in the real environment
    overrides the file, so an ``export`` wins for a single run. Without
    ``secrets_file`` a ``.env`` next to the config is read if present; an
    explicit ``secrets_file`` (a relative path resolves against the config's
    directory) must exist.
    """
    if secrets_file:
        env_path = Path(secrets_file).expanduser()
        if not env_path.is_absolute():
            env_path = config_path.parent / env_path
        if not env_path.is_file():
            raise ConfigError(f"secrets_file not found: {env_path}")
    else:
        env_path = config_path.parent / ".env"
    file_vars = dotenv_values(env_path) if env_path.is_file() else {}
    for key, value in file_vars.items():
        if value is None:
            raise ConfigError(f"{env_path}: {key!r} has no value (expected KEY=VALUE)")
    return {**file_vars, **os.environ}


_VAR_RE = re.compile(
    r"\$\$|\$\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|\$(?P<bare>[A-Za-z_][A-Za-z0-9_]*)"
)


def _interpolate(value: str, env: dict[str, str]) -> str:
    """Substitute Docker Compose-style ``${VAR}``/``$VAR`` in a string.

    ``$$`` is a literal dollar sign. Every referenced variable must be set (in
    the merged environment: the real environment, then a ``.env`` file) — there
    is no default-value fallback, so a missing secret fails loudly.
    """

    def repl(match: re.Match[str]) -> str:
        if match.group(0) == "$$":
            return "$"
        name = match.group("braced") or match.group("bare")
        if name not in env:
            raise ConfigError(
                f"environment variable {name!r} (referenced in {value!r}) is not set"
            )
        return env[name]

    return _VAR_RE.sub(repl, value)


def _interpolate_value(value: Any, env: dict[str, str]) -> Any:
    """Recursively substitute ``${VAR}``/``$VAR`` in every string, anywhere.

    Applies to the whole parsed YAML, not just notifier secrets: a target
    ``host``, a ``cafile`` path, ``state_file``, an ``expect`` entry, etc. can
    all reference ``${VAR}``. Non-string values (int, bool, None, ...) pass
    through unchanged.
    """
    if isinstance(value, str):
        return _interpolate(value, env)
    if isinstance(value, dict):
        return {k: _interpolate_value(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_value(item, env) for item in value]
    return value


def _build_group_targets(
    raw_groups: list[Any], defaults: dict[str, Any]
) -> list[Target]:
    """Build the targets contributed by the config's ``groups:`` entries.

    Group-level keys (other than ``name``/``targets``) are shared defaults for
    the group's targets: global defaults < group settings < per-target.
    """
    targets: list[Target] = []
    for index, group in enumerate(raw_groups, start=1):
        if not isinstance(group, dict):
            raise ConfigError(f"group #{index} must be a mapping")
        group_targets = group.get("targets")
        if not group_targets:
            raise ConfigError(f"group {group.get('name', index)!r} has no targets")
        group_defaults = {
            **defaults,
            **{k: v for k, v in group.items() if k not in ("name", "targets")},
        }
        targets += [_build_target(t, group_defaults) for t in group_targets]
    return targets


def _build_discover_sources(
    raw_discover: list[Any], defaults: dict[str, Any]
) -> list[DiscoverSource]:
    """Build the config's ``discover:`` entries into :class:`DiscoverSource`."""
    sources = []
    for index, entry in enumerate(raw_discover, start=1):
        if not isinstance(entry, dict):
            raise ConfigError(f"discover entry #{index} must be a mapping")
        sources.append(_build_discover_source(entry, defaults))
    return sources


def _build_notifiers(raw_notifiers: list[dict[str, Any]]) -> list[NotifierConfig]:
    """Build the config's ``notifiers:`` entries, defaulting to a console sink."""
    notifiers = []
    for entry in raw_notifiers or [{"type": "console"}]:
        if "type" not in entry:
            raise ConfigError(f"notifier is missing 'type': {entry!r}")
        options = {k: v for k, v in entry.items() if k != "type"}
        notifiers.append(NotifierConfig(type=entry["type"], options=options))
    return notifiers


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

    # secrets_file itself is resolved against the real environment only: the
    # .env file it points at doesn't exist yet to resolve it against.
    raw_secrets_file = data.get("secrets_file")
    secrets_file = (
        _interpolate(raw_secrets_file, os.environ)
        if isinstance(raw_secrets_file, str)
        else raw_secrets_file
    )
    env = _load_environment(path, secrets_file)
    data = _interpolate_value(data, env)

    defaults = data.get("defaults") or {}
    targets = [_build_target(t, defaults) for t in data.get("targets") or []]
    targets += _build_group_targets(data.get("groups") or [], defaults)
    discover_sources = _build_discover_sources(data.get("discover") or [], defaults)

    if not targets and not discover_sources:
        raise ConfigError("at least one target or discover entry is required")

    notifiers = _build_notifiers(data.get("notifiers"))

    interval = parse_duration(data.get("interval", "6h"))
    if interval <= 0:
        raise ConfigError(f"'interval' must be positive, got {interval}s")
    try:
        concurrency = int(data.get("concurrency", 8))
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"'concurrency' must be an integer, got {data['concurrency']!r}"
        ) from exc
    if concurrency < 1:
        raise ConfigError(f"'concurrency' must be at least 1, got {concurrency}")

    return Config(
        targets=targets,
        notifiers=notifiers,
        discover_sources=discover_sources,
        certinspect_bin=data.get("certinspect_bin", "certinspect"),
        interval=interval,
        state_file=Path(
            data.get("state_file", "~/.certminder/state.json")
        ).expanduser(),
        concurrency=concurrency,
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
        failure_threshold=max(1, int(data.get("failure_threshold", 1))),
    )
