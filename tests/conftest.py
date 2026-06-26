"""Shared fixtures and helpers for the certwatch test suite."""

from __future__ import annotations

import pytest

from certwatch.models import CheckResult, Target


@pytest.fixture
def target() -> Target:
    return Target(host="example.com", port=443)


def make_result(target: Target, status: str, **kwargs) -> CheckResult:
    """Build a CheckResult with sensible defaults for tests."""
    reachable = status not in {"UNREACHABLE", "ERROR"}
    defaults = {
        "reachable": reachable,
        "status": status,
        "exit_code": 0,
        "fingerprint": "AA:BB",
        "days_to_expire": 90,
    }
    defaults.update(kwargs)
    return CheckResult(target=target, **defaults)
