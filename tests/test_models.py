"""Tests for the Target/DiscoverSource data model."""

from __future__ import annotations

import pytest

from certminder.models import Target


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
