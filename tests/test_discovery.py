"""Tests for the certinspect --discover-only adapter (subprocess mocked)."""

from __future__ import annotations

import json
import subprocess

import pytest

from certminder.discovery import DiscoveryError, discover_hostnames


def _fake_run(stdout="", returncode=0, stderr=""):
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=returncode, stdout=stdout, stderr=stderr
        )

    return runner


def test_discover_hostnames_drops_wildcards_and_dedupes(monkeypatch):
    records = [
        {"hostnames": ["api.example.com", "*.example.com"]},
        {"hostnames": ["api.example.com", "www.example.com"]},
    ]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(records), 0))
    hosts = discover_hostnames("example.com", 30.0)
    assert hosts == ["api.example.com", "www.example.com"]


def test_discover_hostnames_drops_names_that_are_not_hostnames(monkeypatch, capsys):
    records = [
        {
            "hostnames": [
                "ok.example.com",
                "_dmarc.example.com",
                "xn--caf-dma.example.com",
                "-v.example.com",
                "--export=/tmp/x.example.com",
                "bad name.example.com",
                "evil\x1b[2J.example.com",
                "a-.example.com",
            ]
        }
    ]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(records), 0))
    hosts = discover_hostnames("example.com", 30.0)
    assert hosts == ["_dmarc.example.com", "ok.example.com", "xn--caf-dma.example.com"]
    assert "skipped 5 name(s)" in capsys.readouterr().err


def test_discover_hostnames_uses_certinspect_bin(monkeypatch):
    seen = {}

    def runner(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]")

    monkeypatch.setattr(subprocess, "run", runner)
    discover_hostnames("example.com", 15.0, bin_path="/opt/certinspect")
    assert seen["cmd"][0] == "/opt/certinspect"
    assert "--discover" in seen["cmd"] and "example.com" in seen["cmd"]
    assert "--discover-only" in seen["cmd"]
    assert "--discover-timeout" in seen["cmd"] and "15.0" in seen["cmd"]


def test_discover_hostnames_missing_binary(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(DiscoveryError, match="not found"):
        discover_hostnames("example.com", 30.0, bin_path="nope")


def test_discover_hostnames_timeout(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="certinspect", timeout=30)

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(DiscoveryError, match="timed out"):
        discover_hostnames("example.com", 30.0)


def test_discover_hostnames_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", _fake_run("", 1, "error: discovery for example.com: boom")
    )
    with pytest.raises(DiscoveryError, match="boom"):
        discover_hostnames("example.com", 30.0)


def test_discover_hostnames_malformed_json(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run("not json", 0))
    with pytest.raises(DiscoveryError, match="could not parse"):
        discover_hostnames("example.com", 30.0)


def test_discover_hostnames_unexpected_json_shape(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps({"oops": 1}), 0))
    with pytest.raises(DiscoveryError):
        discover_hostnames("example.com", 30.0)


def test_discover_hostnames_empty_inventory(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run("[]", 0))
    assert discover_hostnames("example.com", 30.0) == []
