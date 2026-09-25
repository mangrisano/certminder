"""Tests for the Target/DiscoverSource data model."""

from __future__ import annotations

import pytest

from certminder.models import Event, EventKind, Severity, Target, printable


def test_printable_escapes_control_characters():
    assert printable("a\x1b[2Jb\nc\x7f") == "a\\x1b[2Jb\\nc\\x7f"
    assert printable("café → ok") == "café → ok"


def test_event_message_cannot_carry_raw_control_characters():
    event = Event(
        target_name="x",
        kind=EventKind.CHAIN_UNTRUSTED,
        severity=Severity.CRITICAL,
        message="x: issuer CN=\x1b[32mall good\n[ok] y: fine",
    )
    assert "\x1b" not in event.message
    assert "\n" not in event.message


def test_target_needs_host_or_file():
    with pytest.raises(ValueError):
        Target()


def test_target_rejects_both_host_and_file():
    with pytest.raises(ValueError):
        Target(host="example.com", file="/tmp/cert.pem")


def test_host_target_name_and_display_host():
    t = Target(host="example.com", port=8443)
    assert t.name == "example.com:8443"
    assert t.display_host == "example.com"


def test_file_target_name_and_display_host():
    t = Target(file="/etc/certs/leaf.pem")
    assert t.name == "/etc/certs/leaf.pem"
    assert t.display_host == "/etc/certs/leaf.pem"


def test_file_target_name_with_label():
    t = Target(file="/etc/certs/leaf.pem", label="Vendored leaf")
    assert t.name == "/etc/certs/leaf.pem (Vendored leaf)"
