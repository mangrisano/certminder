"""Resolve ``${VAR}`` references in the configuration from the environment.

The environment is the real one merged over an optional ``.env`` secrets file,
so credentials can stay out of the YAML.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

_VAR_RE = re.compile(
    r"\$\$|\$\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|\$(?P<bare>[A-Za-z_][A-Za-z0-9_]*)"
)


class EnvError(ValueError):
    """A secrets file is missing or malformed, or a variable is not set."""


def load_environment(config_path: Path, secrets_file: str | None) -> dict[str, str]:
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
            raise EnvError(f"secrets_file not found: {env_path}")
    else:
        env_path = config_path.parent / ".env"
    file_vars = dotenv_values(env_path) if env_path.is_file() else {}
    for key, value in file_vars.items():
        if value is None:
            raise EnvError(f"{env_path}: {key!r} has no value (expected KEY=VALUE)")
    return {**file_vars, **os.environ}


def interpolate(value: str, env: dict[str, str]) -> str:
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
            raise EnvError(
                f"environment variable {name!r} (referenced in {value!r}) is not set"
            )
        return env[name]

    return _VAR_RE.sub(repl, value)


def interpolate_all(value: Any, env: dict[str, str]) -> Any:
    """Recursively substitute ``${VAR}``/``$VAR`` in every string, anywhere.

    Applies to the whole parsed YAML, not just notifier secrets: a target
    ``host``, a ``cafile`` path, ``state_file``, an ``expect`` entry, etc. can
    all reference ``${VAR}``. Non-string values (int, bool, None, ...) pass
    through unchanged.
    """
    if isinstance(value, str):
        return interpolate(value, env)
    if isinstance(value, dict):
        return {k: interpolate_all(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate_all(item, env) for item in value]
    return value
