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


def _checker(status, **fields):
    """A fake ``check`` that reports ``status`` for every target."""
    return lambda target, _bin: make_result(target, status, **fields)


def _discoverer(*prefixes):
    """A fake ``discover`` returning ``<prefix>.<domain>`` for each prefix."""
    return lambda domain, timeout, bin_path: [f"{p}.{domain}" for p in prefixes]


_VALID = _checker("VALID", days_to_expire=80)
_EXPIRED = _checker("EXPIRED", days_to_expire=-3, raw={"status": "EXPIRED"})


def test_run_once_returns_report(tmp_path):
    report = run_once(_config(tmp_path), notifiers=[], check=_VALID)
    assert len(report.results) == 1
    assert report.results[0].status == "VALID"
    assert report.events == []


def test_run_once_report_to_dict_is_json(tmp_path):
    report = run_once(_config(tmp_path), notifiers=[], check=_VALID)
    blob = json.dumps(report.to_dict())
    data = json.loads(blob)
    assert data["targets"][0]["status"] == "VALID"
    assert data["targets"][0]["days_to_expire"] == 80
    assert data["events"] == []


def test_run_once_writes_prometheus_when_configured(tmp_path):
    config = _config(tmp_path, prometheus=True)
    run_once(config, notifiers=[], check=_VALID)
    assert config.prometheus_file.is_file()
    assert "certminder_certificate_expiry_days{" in config.prometheus_file.read_text()


def test_run_once_no_prometheus_by_default(tmp_path):
    run_once(_config(tmp_path), notifiers=[], check=_checker("VALID"))
    assert not (tmp_path / "certminder.prom").exists()


def test_run_once_report_all_re_reports_active_problems(tmp_path):
    check = _checker("CHAIN_UNTRUSTED", chain_trusted=False, raw={"status": "VALID"})
    config = _config(tmp_path)
    # First cycle records the problem and alerts once.
    assert len(run_once(config, notifiers=[], check=check).events) == 1
    # A normal second cycle is deduplicated (silent).
    assert run_once(config, notifiers=[], check=check).events == []
    # report_all re-reports the still-active problem, e.g. on a fresh start.
    again = run_once(config, notifiers=[], report_all=True, check=check)
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


def test_resolve_discovered_targets_applies_source_defaults(tmp_path):
    config = _config(
        tmp_path,
        discover_sources=[
            DiscoverSource(domain="example.com", target_defaults={"verify": False})
        ],
    )
    targets = resolve_discovered_targets(config, _discoverer("a", "b"))
    assert {t.host for t in targets} == {"a.example.com", "b.example.com"}
    assert all(t.verify is False for t in targets)


def test_resolve_discovered_targets_skips_failed_source(tmp_path, capsys):
    from certminder.discovery import DiscoveryError

    def _fake(domain, timeout, bin_path):
        if domain == "bad.com":
            raise DiscoveryError("boom")
        return ["ok.good.com"]

    config = _config(
        tmp_path,
        discover_sources=[
            DiscoverSource(domain="good.com"),
            DiscoverSource(domain="bad.com"),
        ],
    )
    targets = resolve_discovered_targets(config, _fake)
    assert [t.host for t in targets] == ["ok.good.com"]
    assert "boom" in capsys.readouterr().err


def test_all_targets_dedupes_by_name(tmp_path):
    config = _config(
        tmp_path,
        targets=[Target(host="example.com", port=443)],
        discover_sources=[DiscoverSource(domain="example.com")],
    )
    discover = lambda domain, timeout, bin_path: ["example.com", "new.example.com"]  # noqa: E731
    names = {t.name for t in _all_targets(config, discover)}
    assert names == {"example.com:443", "new.example.com:443"}


def test_run_once_inspects_discovered_targets(tmp_path):
    config = _config(
        tmp_path,
        targets=[],
        discover_sources=[DiscoverSource(domain="example.com")],
    )
    report = run_once(
        config,
        notifiers=[],
        check=_checker("VALID"),
        discover=_discoverer("shadow"),
    )
    assert [r.target.host for r in report.results] == ["shadow.example.com"]


class _Recorder:
    def __init__(self):
        self.batches = []

    def send(self, events):
        self.batches.append(events)


class _Broken:
    def send(self, events):
        raise RuntimeError("bug in a notifier")


class _Flaky:
    """Fails to deliver until ``up`` is set, recording what it was sent."""

    def __init__(self):
        self.up = False
        self.batches = []

    def send(self, events):
        self.batches.append(events)
        return self.up


def test_undelivered_events_are_sent_again_next_cycle(tmp_path):
    config = _config(tmp_path)
    flaky = _Flaky()

    first = run_once(config, notifiers=[flaky], check=_EXPIRED)
    assert first.delivered is False
    assert len(first.events) == 1

    flaky.up = True
    second = run_once(config, notifiers=[flaky], check=_EXPIRED)
    assert second.delivered is True
    assert [e.kind for e in second.events] == [e.kind for e in first.events]

    # Delivered now: the alert is active and is not repeated.
    assert run_once(config, notifiers=[flaky], check=_EXPIRED).events == []


def test_a_raising_notifier_counts_as_undelivered(tmp_path, capsys):
    config = _config(tmp_path)
    assert run_once(config, notifiers=[_Broken()], check=_EXPIRED).delivered is False
    assert len(run_once(config, notifiers=[_Recorder()], check=_EXPIRED).events) == 1
    capsys.readouterr()


def test_state_of_a_removed_target_expires(tmp_path):
    from certminder.scheduler import STATE_RETENTION_SECONDS
    from certminder.state import StateStore

    clock = [1_000_000.0]

    def cycle(config):
        run_once(config, notifiers=[], check=_EXPIRED, clock=lambda: clock[0])

    old = Target(host="old.example.com", port=443)
    cycle(_config(tmp_path, targets=[old]))
    assert StateStore(tmp_path / "state.json").get(old.name).last_seen == clock[0]

    # Removed from the config: kept for the retention window, then forgotten.
    config = _config(tmp_path)
    clock[0] += STATE_RETENTION_SECONDS
    cycle(config)
    assert StateStore(tmp_path / "state.json").get(old.name).active_alerts
    clock[0] += 1
    cycle(config)
    assert StateStore(tmp_path / "state.json").get(old.name).last_seen is None


def test_a_broken_notifier_does_not_stop_the_others(tmp_path, capsys):
    recorder = _Recorder()
    report = run_once(
        _config(tmp_path), notifiers=[_Broken(), recorder], check=_EXPIRED
    )
    assert len(report.events) == 1
    assert recorder.batches == [report.events]
    assert "bug in a notifier" in capsys.readouterr().err


def test_safe_run_once_logs_and_survives_a_failed_cycle(capsys):
    from certminder.scheduler import _safe_run_once

    def explode():
        raise RuntimeError("unexpected")

    assert _safe_run_once(explode) is None
    err = capsys.readouterr().err
    assert "cycle failed" in err
    assert "RuntimeError: unexpected" in err
