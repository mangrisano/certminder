"""Tests for the CLI report command."""

from __future__ import annotations

import json

from certminder.cli import _cmd_report
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
