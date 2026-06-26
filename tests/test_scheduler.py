"""Tests for the scheduler's cycle orchestration and report serialisation."""

from __future__ import annotations

import json

from certminder.config import Config, NotifierConfig
from certminder.models import Target
from certminder.scheduler import run_once
from tests.conftest import make_result


def _config(tmp_path, prometheus=False) -> Config:
    return Config(
        targets=[Target(host="example.com", port=443)],
        notifiers=[NotifierConfig(type="console")],
        state_file=tmp_path / "state.json",
        prometheus_file=(tmp_path / "certminder.prom") if prometheus else None,
    )


def test_run_once_returns_report(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "certminder.scheduler.check_target",
        lambda t, _bin: make_result(t, "VALID", days_to_expire=80),
    )
    report = run_once(_config(tmp_path), notifiers=[])
    assert len(report.results) == 1
    assert report.results[0].status == "VALID"
    assert report.events == []


def test_run_once_report_to_dict_is_json(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "certminder.scheduler.check_target",
        lambda t, _bin: make_result(t, "VALID", days_to_expire=80),
    )
    report = run_once(_config(tmp_path), notifiers=[])
    blob = json.dumps(report.to_dict())
    data = json.loads(blob)
    assert data["targets"][0]["status"] == "VALID"
    assert data["targets"][0]["days_to_expire"] == 80
    assert data["events"] == []


def test_run_once_writes_prometheus_when_configured(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "certminder.scheduler.check_target",
        lambda t, _bin: make_result(t, "VALID", days_to_expire=80),
    )
    config = _config(tmp_path, prometheus=True)
    run_once(config, notifiers=[])
    assert config.prometheus_file.is_file()
    assert "certminder_certificate_expiry_days{" in config.prometheus_file.read_text()


def test_run_once_no_prometheus_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "certminder.scheduler.check_target",
        lambda t, _bin: make_result(t, "VALID"),
    )
    run_once(_config(tmp_path), notifiers=[])
    assert not (tmp_path / "certminder.prom").exists()
