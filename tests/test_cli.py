"""Tests for the CLI report and check commands."""

from __future__ import annotations

import json
import subprocess

from certminder.cli import _cmd_report, main
from certminder.config import Config, NotifierConfig
from certminder.models import Target
from certminder.state import StateStore, TargetState


def _config(tmp_path, targets):
    return Config(
        targets=targets,
        notifiers=[NotifierConfig(type="console")],
        state_file=tmp_path / "state.json",
    )


def test_report_lists_active_problems(tmp_path, capsys):
    t = Target(host="bad.com", port=443)
    config = _config(tmp_path, [t])
    store = StateStore(config.state_file)
    store.set(
        t.name,
        TargetState(
            status="EXPIRED",
            active_alerts=[f"{t.name}|expired", f"{t.name}|chain_untrusted"],
        ),
    )
    store.save()

    code = _cmd_report(config, as_json=False)
    out = capsys.readouterr().out
    assert code == 1
    assert "bad.com:443" in out
    assert "expired" in out and "chain_untrusted" in out


def test_report_all_ok(tmp_path, capsys):
    t = Target(host="good.com", port=443)
    config = _config(tmp_path, [t])
    store = StateStore(config.state_file)
    store.set(t.name, TargetState(status="VALID"))
    store.save()

    code = _cmd_report(config, as_json=False)
    assert code == 0
    assert "OK" in capsys.readouterr().out


def test_report_json(tmp_path, capsys):
    t = Target(host="bad.com", port=443)
    config = _config(tmp_path, [t])
    store = StateStore(config.state_file)
    store.set(
        t.name, TargetState(status="EXPIRED", active_alerts=[f"{t.name}|expired"])
    )
    store.save()

    code = _cmd_report(config, as_json=True)
    data = json.loads(capsys.readouterr().out)
    assert code == 1
    assert data["total_targets"] == 1
    assert data["with_problems"] == 1
    assert data["problems"][0]["problems"] == ["expired"]


def _fake_run(stdout, returncode):
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=returncode, stdout=stdout, stderr=""
        )

    return runner


def test_check_host(monkeypatch, capsys):
    info = [{"days_to_expire": 42, "fingerprint_sha256": "AA:BB"}]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(info), 0))
    code = main(["check", "example.com"])
    out = capsys.readouterr().out
    assert code == 0
    assert "example.com:443: ok (42 day(s) left)" in out


def test_check_file(monkeypatch, capsys):
    info = [{"days_to_expire": 10, "fingerprint_sha256": "AA:BB"}]
    monkeypatch.setattr(subprocess, "run", _fake_run(json.dumps(info), 0))
    code = main(["check", "--file", "/etc/certs/leaf.pem"])
    out = capsys.readouterr().out
    assert code == 0
    assert "/etc/certs/leaf.pem: ok (10 day(s) left)" in out


def test_check_requires_exactly_one_of_host_or_file(capsys):
    assert main(["check"]) == 2
    assert "exactly one" in capsys.readouterr().err

    assert main(["check", "example.com", "--file", "/etc/certs/leaf.pem"]) == 2
    assert "exactly one" in capsys.readouterr().err
