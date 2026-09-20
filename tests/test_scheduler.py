"""Tests for the scheduler's cycle orchestration and report serialisation."""

from __future__ import annotations

import json

from certminder.config import Config, NotifierConfig
from certminder.models import DiscoverSource, Target
from certminder.scheduler import _all_targets, resolve_discovered_targets, run_once
from conftest import make_result


def _config(tmp_path, prometheus=False, **overrides) -> Config:
    defaults = dict(
        targets=[Target(host="example.com", port=443)],
        notifiers=[NotifierConfig(type="console")],
        state_file=tmp_path / "state.json",
        prometheus_file=(tmp_path / "certminder.prom") if prometheus else None,
    )
    defaults.update(overrides)
    return Config(**defaults)


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


def test_run_once_report_all_re_reports_active_problems(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "certminder.scheduler.check_target",
        lambda t, _bin: make_result(
            t, "CHAIN_UNTRUSTED", chain_trusted=False, raw={"status": "VALID"}
        ),
    )
    config = _config(tmp_path)
    # First cycle records the problem and alerts once.
    assert len(run_once(config, notifiers=[]).events) == 1
    # A normal second cycle is deduplicated (silent).
    assert run_once(config, notifiers=[]).events == []
    # report_all re-reports the still-active problem, e.g. on a fresh start.
    again = run_once(config, notifiers=[], report_all=True)
    assert len(again.events) == 1
    assert again.events[0].kind.value == "chain_untrusted"


def test_log_heartbeat_prints_summary(capsys):
    from certminder.scheduler import CycleReport, _log_heartbeat

    t = Target(host="a.com", port=443)
    report = CycleReport(
        results=[make_result(t, "VALID"), make_result(t, "EXPIRED", days_to_expire=-1)]
    )
    _log_heartbeat(report)
    out = capsys.readouterr().out
    assert "[hb]" in out
    assert "2 target(s)" in out
    assert "1 ok" in out
    assert "1 with problems" in out


def test_resolve_discovered_targets_applies_source_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "certminder.scheduler.discover_hostnames",
        lambda domain, timeout, bin_path: ["a." + domain, "b." + domain],
    )
    config = _config(
        tmp_path,
        discover_sources=[
            DiscoverSource(domain="example.com", target_defaults={"verify": False})
        ],
    )
    targets = resolve_discovered_targets(config)
    assert {t.host for t in targets} == {"a.example.com", "b.example.com"}
    assert all(t.verify is False for t in targets)


def test_resolve_discovered_targets_skips_failed_source(monkeypatch, tmp_path, capsys):
    from certminder.discovery import DiscoveryError

    def _fake(domain, timeout, bin_path):
        if domain == "bad.com":
            raise DiscoveryError("boom")
        return ["ok.good.com"]

    monkeypatch.setattr("certminder.scheduler.discover_hostnames", _fake)
    config = _config(
        tmp_path,
        discover_sources=[
            DiscoverSource(domain="good.com"),
            DiscoverSource(domain="bad.com"),
        ],
    )
    targets = resolve_discovered_targets(config)
    assert [t.host for t in targets] == ["ok.good.com"]
    assert "boom" in capsys.readouterr().err


def test_all_targets_dedupes_by_name(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "certminder.scheduler.discover_hostnames",
        lambda domain, timeout, bin_path: ["example.com", "new.example.com"],
    )
    config = _config(
        tmp_path,
        targets=[Target(host="example.com", port=443)],
        discover_sources=[DiscoverSource(domain="example.com")],
    )
    names = {t.name for t in _all_targets(config)}
    assert names == {"example.com:443", "new.example.com:443"}


def test_run_once_inspects_discovered_targets(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "certminder.scheduler.discover_hostnames",
        lambda domain, timeout, bin_path: ["shadow.example.com"],
    )
    monkeypatch.setattr(
        "certminder.scheduler.check_target",
        lambda t, _bin: make_result(t, "VALID"),
    )
    config = _config(
        tmp_path,
        targets=[],
        discover_sources=[DiscoverSource(domain="example.com")],
    )
    report = run_once(config, notifiers=[])
    assert [r.target.host for r in report.results] == ["shadow.example.com"]
