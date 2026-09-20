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
            require_revocation_check: true
            min_tls_version: TLSv1.2
        """,
    )
    config = load_config(path)
    target = config.targets[0]
    assert target.require_sct is True
    assert target.require_must_staple is True
    assert target.require_revocation_check is True
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


def test_profile_target_key(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - host: example.com
            profile: standard
        """,
    )
    config = load_config(path)
    assert config.targets[0].profile == "standard"


def test_invalid_profile_is_error(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - host: example.com
            profile: paranoid
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_startup_report_defaults_true_and_can_be_disabled(tmp_path):
    default = load_config(_write(tmp_path, "targets:\n  - host: example.com\n"))
    assert default.startup_report is True

    off = _write(
        tmp_path,
        """
        startup_report: false
        targets:
          - host: example.com
        """,
    )
    assert load_config(off).startup_report is False


def test_renotify_after_and_heartbeat_options(tmp_path):
    cfg = load_config(
        _write(
            tmp_path,
            """
            renotify_after: 12h
            heartbeat: false
            targets:
              - host: example.com
            """,
        )
    )
    assert cfg.renotify_after == 12 * 3600
    assert cfg.heartbeat is False

    default = load_config(_write(tmp_path, "targets:\n  - host: example.com\n"))
    assert default.renotify_after is None
    assert default.heartbeat is True


def test_expect_target_key(tmp_path):
    cfg = load_config(
        _write(
            tmp_path,
            """
            targets:
              - host: example.com
                expect: [chain_untrusted, hostname_mismatch]
            """,
        )
    )
    assert cfg.targets[0].expect == ("chain_untrusted", "hostname_mismatch")


def test_invalid_expect_kind_is_error(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - host: example.com
            expect: [bogus_problem]
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_missing_file_is_error(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yml")


def test_groups_apply_shared_settings(tmp_path):
    path = _write(
        tmp_path,
        """
        defaults:
          days: 30
        groups:
          - name: Internal PKI
            cafile: /etc/certminder/internal-ca.pem
            verify: true
            targets:
              - host: iap.internal.lan
              - host: trustapp.internal.lan
                cafile: /etc/certminder/other-ca.pem
        """,
    )
    config = load_config(path)
    by_host = {t.host: t for t in config.targets}
    # Group setting is inherited...
    assert by_host["iap.internal.lan"].cafile == "/etc/certminder/internal-ca.pem"
    assert by_host["iap.internal.lan"].days == 30  # global default still applies
    # ...but a per-target value overrides the group.
    assert by_host["trustapp.internal.lan"].cafile == "/etc/certminder/other-ca.pem"


def test_groups_and_top_level_targets_coexist(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - host: public.example.com
        groups:
          - name: Internal
            cafile: /etc/certminder/internal-ca.pem
            targets:
              - host: private.internal.lan
        """,
    )
    config = load_config(path)
    by_host = {t.host: t for t in config.targets}
    assert by_host["public.example.com"].cafile is None
    assert by_host["private.internal.lan"].cafile == "/etc/certminder/internal-ca.pem"


def test_group_without_targets_is_error(tmp_path):
    path = _write(
        tmp_path,
        """
        groups:
          - name: Empty
            cafile: /etc/certminder/internal-ca.pem
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_only_groups_no_top_level_targets_is_valid(tmp_path):
    path = _write(
        tmp_path,
        """
        groups:
          - name: Internal
            targets:
              - host: private.internal.lan
        """,
    )
    config = load_config(path)
    assert len(config.targets) == 1


def test_failure_threshold_parses(tmp_path):
    path = _write(
        tmp_path,
        """
        failure_threshold: 3
        targets:
          - host: example.com
        """,
    )
    assert load_config(path).failure_threshold == 3


def test_failure_threshold_defaults_to_one(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - host: example.com
        """,
    )
    assert load_config(path).failure_threshold == 1


def test_network_robustness_keys_accepted(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - host: example.com
            retries: 2
            connect_timeout: 3
            read_timeout: 8
        """,
    )
    t = load_config(path).targets[0]
    assert t.retries == 2
    assert t.connect_timeout == 3
    assert t.read_timeout == 8


def test_braced_var_reads_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_PASS", "s3cret")
    cfg = load_config(
        _write(
            tmp_path,
            """
            notifiers:
              - type: email
                password: ${SMTP_PASS}
            targets:
              - host: example.com
            """,
        )
    )
    assert cfg.notifiers[0].options["password"] == "s3cret"


def test_bare_var_reads_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SMTP_PASS", "s3cret")
    cfg = load_config(
        _write(
            tmp_path,
            """
            notifiers:
              - type: email
                password: $SMTP_PASS
            targets:
              - host: example.com
            """,
        )
    )
    assert cfg.notifiers[0].options["password"] == "s3cret"


def test_missing_variable_is_error(tmp_path, monkeypatch):
    monkeypatch.delenv("NO_SUCH_SECRET", raising=False)
    path = _write(
        tmp_path,
        """
        notifiers:
          - type: slack
            webhook_url: ${NO_SUCH_SECRET}
        targets:
          - host: example.com
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_var_resolves_inside_nested_headers(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBHOOK_TOKEN", "abc123")
    cfg = load_config(
        _write(
            tmp_path,
            """
            notifiers:
              - type: webhook
                url: https://example.com/hook
                headers:
                  Authorization: "Bearer ${WEBHOOK_TOKEN}"
            targets:
              - host: example.com
            """,
        )
    )
    headers = cfg.notifiers[0].options["headers"]
    assert headers["Authorization"] == "Bearer abc123"


def test_var_resolves_inside_list_items(tmp_path, monkeypatch):
    monkeypatch.setenv("OPS_EMAIL", "ops@example.com")
    cfg = load_config(
        _write(
            tmp_path,
            """
            notifiers:
              - type: email
                host: smtp.example.com
                from_addr: alerts@example.com
                to: ["${OPS_EMAIL}"]
            targets:
              - host: example.com
            """,
        )
    )
    assert cfg.notifiers[0].options["to"] == ["ops@example.com"]


def test_double_dollar_is_literal_dollar(tmp_path, monkeypatch):
    cfg = load_config(
        _write(
            tmp_path,
            """
            notifiers:
              - type: email
                password: "pa$$word"
            targets:
              - host: example.com
            """,
        )
    )
    assert cfg.notifiers[0].options["password"] == "pa$word"


def test_var_resolves_in_target_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("TARGET_HOST", "internal.example.com")
    cfg = load_config(
        _write(
            tmp_path,
            """
            targets:
              - host: ${TARGET_HOST}
                label: prod-${TARGET_HOST}
            """,
        )
    )
    assert cfg.targets[0].host == "internal.example.com"
    assert cfg.targets[0].label == "prod-internal.example.com"


def test_var_resolves_in_top_level_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    cfg = load_config(
        _write(
            tmp_path,
            """
            state_file: ${STATE_DIR}/state.json
            targets:
              - host: example.com
            """,
        )
    )
    assert cfg.state_file == (tmp_path / "state" / "state.json")


def test_secrets_file_path_resolves_against_real_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRETS_NAME", "secrets.env")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    (tmp_path / "secrets.env").write_text("SMTP_PASSWORD=explicit-secret\n")
    cfg = load_config(
        _write(
            tmp_path,
            """
            secrets_file: ${SECRETS_NAME}
            notifiers:
              - type: email
                password: ${SMTP_PASSWORD}
            targets:
              - host: example.com
            """,
        )
    )
    assert cfg.notifiers[0].options["password"] == "explicit-secret"


def test_env_file_next_to_config_supplies_variable(tmp_path, monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    (tmp_path / ".env").write_text(
        "SLACK_WEBHOOK_URL=https://hooks.example/from-file\n"
    )
    cfg = load_config(
        _write(
            tmp_path,
            """
            notifiers:
              - type: slack
                webhook_url: ${SLACK_WEBHOOK_URL}
            targets:
              - host: example.com
            """,
        )
    )
    assert cfg.notifiers[0].options["webhook_url"] == "https://hooks.example/from-file"


def test_real_environment_overrides_env_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "SLACK_WEBHOOK_URL=https://hooks.example/from-file\n"
    )
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.example/from-environment")
    cfg = load_config(
        _write(
            tmp_path,
            """
            notifiers:
              - type: slack
                webhook_url: ${SLACK_WEBHOOK_URL}
            targets:
              - host: example.com
            """,
        )
    )
    assert (
        cfg.notifiers[0].options["webhook_url"]
        == "https://hooks.example/from-environment"
    )


def test_env_file_preserves_case_and_strips_quotes(tmp_path, monkeypatch):
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    (tmp_path / ".env").write_text('SMTP_PASSWORD="pa%word"\n')
    cfg = load_config(
        _write(
            tmp_path,
            """
            notifiers:
              - type: email
                password: ${SMTP_PASSWORD}
            targets:
              - host: example.com
            """,
        )
    )
    assert cfg.notifiers[0].options["password"] == "pa%word"


def test_env_file_skips_blank_lines_and_comments(tmp_path, monkeypatch):
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    (tmp_path / ".env").write_text("# a comment\n\nSMTP_PASSWORD=s3cret\n")
    cfg = load_config(
        _write(
            tmp_path,
            """
            notifiers:
              - type: email
                password: ${SMTP_PASSWORD}
            targets:
              - host: example.com
            """,
        )
    )
    assert cfg.notifiers[0].options["password"] == "s3cret"


def test_explicit_secrets_file_relative_to_config(tmp_path, monkeypatch):
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    (tmp_path / "secrets.env").write_text("SMTP_PASSWORD=explicit-secret\n")
    cfg = load_config(
        _write(
            tmp_path,
            """
            secrets_file: secrets.env
            notifiers:
              - type: email
                password: ${SMTP_PASSWORD}
            targets:
              - host: example.com
            """,
        )
    )
    assert cfg.notifiers[0].options["password"] == "explicit-secret"


def test_missing_explicit_secrets_file_is_error(tmp_path):
    path = _write(
        tmp_path,
        """
        secrets_file: nope.env
        targets:
          - host: example.com
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_env_file_without_equals_is_error(tmp_path):
    (tmp_path / ".env").write_text("oops-no-equals\n")
    path = _write(
        tmp_path,
        """
        notifiers:
          - type: email
            password: ${SMTP_PASSWORD}
        targets:
          - host: example.com
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_file_target_key(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - file: /etc/certs/leaf.pem
            label: Vendored leaf
        """,
    )
    config = load_config(path)
    assert config.targets[0].file == "/etc/certs/leaf.pem"
    assert config.targets[0].host is None
    assert config.targets[0].name == "/etc/certs/leaf.pem (Vendored leaf)"


def test_target_needs_host_or_file(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - label: neither host nor file
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_target_rejects_host_and_file_together(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - host: example.com
            file: /etc/certs/leaf.pem
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


@pytest.mark.parametrize(
    "key,value",
    [("port", 8443), ("starttls", "smtp"), ("min_tls_version", "TLSv1.2")],
)
def test_file_target_rejects_host_only_keys(tmp_path, key, value):
    path = _write(
        tmp_path,
        f"""
        targets:
          - file: /etc/certs/leaf.pem
            {key}: {value!r}
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_file_target_rejects_require_revocation_check(tmp_path):
    path = _write(
        tmp_path,
        """
        targets:
          - file: /etc/certs/leaf.pem
            require_revocation_check: true
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_file_target_ignores_inherited_host_only_default(tmp_path):
    # A global 'defaults: {port: ...}' is meant for host targets; a file
    # target inheriting it is not a conflict (regression: it used to be).
    path = _write(
        tmp_path,
        """
        defaults:
          port: 443
        targets:
          - host: example.com
          - file: /etc/certs/leaf.pem
        """,
    )
    config = load_config(path)
    by_name = {t.name: t for t in config.targets}
    assert by_name["/etc/certs/leaf.pem"].file == "/etc/certs/leaf.pem"


def test_discover_source_parses(tmp_path):
    path = _write(
        tmp_path,
        """
        discover:
          - domain: example.com
            discover_timeout: 10
            verify: false
        targets:
          - host: static.example.com
        """,
    )
    config = load_config(path)
    assert len(config.discover_sources) == 1
    source = config.discover_sources[0]
    assert source.domain == "example.com"
    assert source.discover_timeout == 10.0
    assert source.target_defaults == {"verify": False}


def test_discover_source_inherits_global_defaults(tmp_path):
    path = _write(
        tmp_path,
        """
        defaults:
          days: 45
        discover:
          - domain: example.com
        targets:
          - host: static.example.com
        """,
    )
    config = load_config(path)
    assert config.discover_sources[0].target_defaults["days"] == 45


def test_discover_without_targets_is_valid(tmp_path):
    path = _write(
        tmp_path,
        """
        discover:
          - domain: example.com
        """,
    )
    config = load_config(path)
    assert config.targets == []
    assert len(config.discover_sources) == 1


def test_discover_missing_domain_is_error(tmp_path):
    path = _write(
        tmp_path,
        """
        discover:
          - discover_timeout: 10
        targets:
          - host: static.example.com
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_discover_unknown_key_is_error(tmp_path):
    path = _write(
        tmp_path,
        """
        discover:
          - domain: example.com
            bogus: 1
        targets:
          - host: static.example.com
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_discover_rejects_host_or_file_key(tmp_path):
    path = _write(
        tmp_path,
        """
        discover:
          - domain: example.com
            host: not-allowed.example.com
        targets:
          - host: static.example.com
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_no_targets_and_no_discover_is_error(tmp_path):
    path = _write(tmp_path, "interval: 1h\n")
    with pytest.raises(ConfigError):
        load_config(path)
