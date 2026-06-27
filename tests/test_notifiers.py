"""Tests for the notifier package: registry plus the email sink."""

from __future__ import annotations

import re

import pytest

from certminder.models import Event, EventKind, Severity
from certminder.notifiers import REGISTRY, build_notifier
from certminder.notifiers.console import ConsoleNotifier
from certminder.notifiers.email import EmailNotifier


def _event(severity: Severity = Severity.WARNING, message: str = "x: oops") -> Event:
    return Event(
        target_name="x",
        kind=EventKind.EXPIRING,
        severity=severity,
        message=message,
    )


def test_registry_exposes_email():
    assert REGISTRY["email"] is EmailNotifier


def test_build_notifier_unknown_type():
    with pytest.raises(ValueError):
        build_notifier("does-not-exist", {})


def test_console_no_timestamp_by_default(capsys):
    ConsoleNotifier().send([_event(Severity.CRITICAL, "x: down")])
    assert capsys.readouterr().err.strip() == "[crit] x: down"


def test_console_timestamp_prefixes_each_line(capsys):
    build_notifier("console", {"timestamp": True}).send(
        [_event(Severity.CRITICAL, "x: down")]
    )
    line = capsys.readouterr().err.strip()
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[crit\] x: down$", line)


def test_email_requires_core_options():
    with pytest.raises(ValueError):
        EmailNotifier(host="", to="a@b.c", from_addr="c@d.e")
    with pytest.raises(ValueError):
        EmailNotifier(host="smtp", to="", from_addr="c@d.e")
    with pytest.raises(ValueError):
        EmailNotifier(host="smtp", to="a@b.c", from_addr="")


def test_email_to_accepts_string_and_list():
    one = EmailNotifier(host="smtp", to="a@b.c", from_addr="c@d.e")
    assert one.recipients == ["a@b.c"]
    many = EmailNotifier(host="smtp", to=["a@b.c", "x@y.z"], from_addr="c@d.e")
    assert many.recipients == ["a@b.c", "x@y.z"]


def test_email_subject_reflects_worst_severity():
    n = EmailNotifier(host="smtp", to="a@b.c", from_addr="c@d.e")
    events = [
        _event(Severity.INFO),
        _event(Severity.CRITICAL),
        _event(Severity.WARNING),
    ]
    assert n._subject(events) == "[certminder] CRITICAL: 3 events"
    assert n._subject([_event(Severity.WARNING)]) == "[certminder] WARNING: 1 event"


def test_email_message_has_headers_and_body():
    n = EmailNotifier(host="smtp", to=["a@b.c", "x@y.z"], from_addr="c@d.e")
    message = n._build_message([_event(message="x: expires soon")])
    assert message["From"] == "c@d.e"
    assert message["To"] == "a@b.c, x@y.z"
    assert message["Subject"] == "[certminder] WARNING: 1 event"
    assert "x: expires soon" in message.get_content()


def test_email_send_swallows_errors(monkeypatch):
    n = EmailNotifier(host="smtp", to="a@b.c", from_addr="c@d.e")

    def boom(_message):
        raise OSError("connection refused")

    monkeypatch.setattr(n, "_deliver", boom)
    # Must not raise even though delivery fails.
    n.send([_event()])


def test_email_send_noop_on_empty(monkeypatch):
    n = EmailNotifier(host="smtp", to="a@b.c", from_addr="c@d.e")
    called = False

    def mark(_message):
        nonlocal called
        called = True

    monkeypatch.setattr(n, "_deliver", mark)
    n.send([])
    assert called is False


def test_email_deliver_uses_starttls(monkeypatch):
    events = [_event()]
    actions: list[str] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            actions.append(f"connect {host}:{port}")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, context=None):
            actions.append("starttls")

        def login(self, user, password):
            actions.append(f"login {user}")

        def send_message(self, message):
            actions.append("send")

    monkeypatch.setattr("certminder.notifiers.email.smtplib.SMTP", FakeSMTP)
    n = EmailNotifier(
        host="smtp",
        to="a@b.c",
        from_addr="c@d.e",
        username="u",
        password="p",
        use_tls=True,
    )
    n.send(events)
    assert actions == ["connect smtp:587", "starttls", "login u", "send"]


def test_email_deliver_uses_ssl(monkeypatch):
    actions: list[str] = []

    class FakeSMTPSSL:
        def __init__(self, host, port, timeout, context):
            actions.append(f"ssl-connect {host}:{port}")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def login(self, user, password):
            actions.append("login")

        def send_message(self, message):
            actions.append("send")

    monkeypatch.setattr("certminder.notifiers.email.smtplib.SMTP_SSL", FakeSMTPSSL)
    n = EmailNotifier(
        host="smtp",
        to="a@b.c",
        from_addr="c@d.e",
        port=465,
        use_ssl=True,
    )
    n.send([_event()])
    assert actions == ["ssl-connect smtp:465", "send"]
