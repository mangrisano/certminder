"""Tests for the certinspect engine adapter (subprocess mocked)."""

from __future__ import annotations

import json
import subprocess

from certwatch.engine import build_command, check_target
from certwatch.models import Target


def test_build_command_includes_flags():
    target = Target(host="example.com", port=8443, verify=True, starttls="smtp")
    cmd = build_command("certinspect", target)
    assert cmd[:2] == ["certinspect", "example.com"]
    assert "--json" in cmd
    assert "--verify" in cmd
    assert "--starttls" in cmd and "smtp" in cmd
    assert "8443" in cmd


def _fake_run(stdout, returncode):
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=returncode, stdout=stdout, stderr=""
        )

    return runner


def test_check_valid(monkeypatch):
    info = [{"days_to_expire": 90, "fingerprint_sha256": "AA:BB"}]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(info), 0))
    result = check_target(Target(host="example.com"))
    assert result.status == "VALID"
    assert result.reachable is True
    assert result.fingerprint == "AA:BB"
    assert result.days_to_expire == 90


def test_check_expiring(monkeypatch):
    info = [{"days_to_expire": 10, "fingerprint_sha256": "AA:BB"}]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(info), 3))
    result = check_target(Target(host="example.com"))
    assert result.status == "EXPIRING"


def test_check_expired(monkeypatch):
    info = [{"days_to_expire": -5, "fingerprint_sha256": "AA:BB"}]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(info), 4))
    result = check_target(Target(host="example.com"))
    assert result.status == "EXPIRED"


def test_check_revoked(monkeypatch):
    info = [{"days_to_expire": 50, "revocation_status": "REVOKED"}]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(info), 6))
    result = check_target(Target(host="example.com"))
    assert result.status == "REVOKED"


def test_check_chain_untrusted(monkeypatch):
    info = [{"days_to_expire": 50, "chain_trusted": False}]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(info), 6))
    result = check_target(Target(host="example.com"))
    assert result.status == "CHAIN_UNTRUSTED"


def test_check_unreachable(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run("", 1))
    result = check_target(Target(host="nope.invalid"))
    assert result.status == "UNREACHABLE"
    assert result.reachable is False


def test_missing_binary(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", boom)
    result = check_target(Target(host="example.com"), bin_path="nope")
    assert result.exit_code == 127
    assert "not found" in (result.error or "")
