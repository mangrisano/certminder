"""Tests for configuration parsing and validation."""

from __future__ import annotations

import pytest

from certminder.config import ConfigError, load_config, parse_duration


@pytest.mark.parametrize(
    "text,seconds",
    [("30s", 30), ("5m", 300), ("6h", 21600), ("1d", 86400), (45, 45)],
)
def test_parse_duration(text, seconds):
    assert parse_duration(text) == seconds


def test_parse_duration_invalid():
    with pytest.raises(ConfigError):
        parse_duration("soon")


def _write(tmp_path, text):
    path = tmp_path / "certminder.yml"
    path.write_text(text)
    return path


def test_load_minimal_config(tmp_path):
    path = _write(
        tmp_path,
        """
        interval: 2h
        defaults:
          days: 20
        targets:
          - host: example.com
          - host: api.example.com
            port: 8443
            label: API
        """,
    )
    config = load_config(path)
    assert config.interval == 7200
    assert len(config.targets) == 2
    assert config.targets[0].days == 20  # inherited from defaults
    assert config.targets[1].port == 8443
    assert config.targets[1].name == "api.example.com:8443 (API)"
    # default notifier is console
    assert config.notifiers[0].type == "console"


def test_target_override_beats_default(tmp_path):
    path = _write(
        tmp_path,
        """
        defaults:
          days: 30
        targets:
          - host: example.com
            days: 7
        """,
    )
    config = load_config(path)
    assert config.targets[0].days == 7


def test_missing_targets_is_error(tmp_path):
    path = _write(tmp_path, "interval: 1h\n")
    with pytest.raises(ConfigError):
        load_config(path)


def test_unknown_target_key_is_error(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - host: example.com
            bogus: 1
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_cab_forum_target_key(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - host: example.com
            cab_forum: true
          - host: api.example.com
            not_after_max: 47
        """,
    )
    config = load_config(path)
    assert config.targets[0].cab_forum is True
    assert config.targets[1].not_after_max == 47


def test_new_policy_target_keys(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - host: example.com
            require_sct: true
            require_must_staple: true
            min_tls_version: TLSv1.2
        """,
    )
    config = load_config(path)
    target = config.targets[0]
    assert target.require_sct is True
    assert target.require_must_staple is True
    assert target.min_tls_version == "TLSv1.2"


def test_cab_forum_and_not_after_max_conflict(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - host: example.com
            cab_forum: true
            not_after_max: 47
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_missing_file_is_error(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yml")
