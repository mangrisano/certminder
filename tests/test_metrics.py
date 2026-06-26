"""Tests for the Prometheus textfile metrics rendering and writing."""

from __future__ import annotations

from certminder.metrics import render, write_prometheus
from certminder.models import Target
from conftest import make_result


def _result(status: str, **kwargs):
    return make_result(Target(host="example.com", port=443), status, **kwargs)


def test_render_includes_expiry_for_reachable():
    text = render([_result("VALID", days_to_expire=42)], now=1000.0)
    assert "certminder_certificate_expiry_days{" in text
    assert "} 42" in text
    assert 'host="example.com"' in text
    assert 'status="VALID"' in text


def test_render_valid_and_up_flags():
    text = render([_result("VALID", days_to_expire=10)], now=1000.0)
    assert "certminder_certificate_valid{" in text
    assert "} 1" in text
    assert "certminder_target_up{" in text


def test_render_invalid_status_sets_zero():
    text = render([_result("EXPIRED", days_to_expire=-3)], now=1000.0)
    valid_line = next(
        ln for ln in text.splitlines() if ln.startswith("certminder_certificate_valid{")
    )
    assert valid_line.endswith(" 0")


def test_render_unreachable_omits_expiry_but_sets_up_zero():
    text = render([_result("UNREACHABLE", days_to_expire=None)], now=1000.0)
    assert "certminder_certificate_expiry_days{" not in text
    up_line = next(
        ln for ln in text.splitlines() if ln.startswith("certminder_target_up{")
    )
    assert up_line.endswith(" 0")


def test_render_has_help_type_and_timestamp():
    text = render([_result("VALID")], now=1700000000.0)
    assert "# HELP certminder_certificate_expiry_days" in text
    assert "# TYPE certminder_certificate_valid gauge" in text
    assert "certminder_last_run_timestamp_seconds 1700000000" in text


def test_render_escapes_label_quotes():
    target = Target(host="example.com", port=443, label='weird "quote"')
    text = render([make_result(target, "VALID")], now=1000.0)
    assert '\\"quote\\"' in text


def test_write_prometheus_atomic(tmp_path):
    path = tmp_path / "sub" / "certminder.prom"
    write_prometheus([_result("VALID", days_to_expire=5)], path, now=1000.0)
    assert path.is_file()
    content = path.read_text()
    assert content.endswith("\n")
    assert "certminder_certificate_expiry_days{" in content
    # No leftover temp files.
    assert list(path.parent.glob("*.tmp")) == []
