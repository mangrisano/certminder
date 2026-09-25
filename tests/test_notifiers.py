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


def test_slack_escapes_mentions_and_links():
    from certminder.notifiers.slack import SlackNotifier

    text = SlackNotifier("https://hooks.invalid/x")._format(
        [_event(message="x: <!channel> <https://evil.example|renew> & more")]
    )
    assert "<" not in text and ">" not in text
    assert "&lt;!channel&gt;" in text
    assert "&amp; more" in text


@pytest.mark.parametrize("url", ["http://hooks.slack.com/x", "file:///etc/passwd"])
def test_slack_requires_https(url):
    from certminder.notifiers.slack import SlackNotifier

    with pytest.raises(ValueError, match="https"):
        SlackNotifier(url)


def test_webhook_rejects_non_http_schemes():
    from certminder.notifiers.webhook import WebhookNotifier

    with pytest.raises(ValueError, match="http"):
        WebhookNotifier("file:///etc/passwd")


def test_webhook_warns_on_plain_http_without_printing_the_url(capsys):
    from certminder.notifiers.webhook import WebhookNotifier

    WebhookNotifier("http://alerts.internal/hook?token=s3cr3t")
    err = capsys.readouterr().err
    assert "plain http://" in err
    assert "s3cr3t" not in err
    WebhookNotifier("https://alerts.example/hook")
    assert capsys.readouterr().err == ""


def test_build_notifier_unknown_type():
    with pytest.raises(ValueError):
        build_notifier("does-not-exist", {})


def test_min_severity_filters_below_threshold(capsys):
    notifier = build_notifier("console", {"min_severity": "critical"})
    notifier.send(
        [_event(Severity.WARNING, "x: warn"), _event(Severity.CRITICAL, "x: down")]
    )
    captured = capsys.readouterr()
    assert "x: warn" not in (captured.out + captured.err)  # WARNING dropped
    assert "x: down" in captured.err  # CRITICAL delivered


def test_min_severity_invalid_value():
    with pytest.raises(ValueError):
        build_notifier("console", {"min_severity": "bogus"})


def _kind_event(kind: EventKind, message: str) -> Event:
    return Event(
        target_name="x", kind=kind, severity=Severity.CRITICAL, message=message
    )


def test_kinds_filters_to_allowlist(capsys):
    notifier = build_notifier("console", {"kinds": ["expired"]})
    notifier.send(
        [
            _kind_event(EventKind.EXPIRED, "x: expired"),
            _kind_event(EventKind.CHAIN_UNTRUSTED, "x: bad chain"),
        ]
    )
    captured = capsys.readouterr()
    assert "x: expired" in captured.err  # allowed kind delivered
    assert "x: bad chain" not in (captured.out + captured.err)  # other kind dropped


def test_kinds_accepts_a_single_string(capsys):
    notifier = build_notifier("console", {"kinds": "expired"})
    notifier.send([_kind_event(EventKind.EXPIRED, "x: expired")])
    assert "x: expired" in capsys.readouterr().err


def test_kinds_invalid_value():
    with pytest.raises(ValueError):
        build_notifier("console", {"kinds": ["bogus"]})


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


def test_email_body_orders_by_expiry_soonest_first():
    n = EmailNotifier(host="smtp", to="a@b.c", from_addr="c@d.e")

    def expiry(name: str, days: int | None) -> Event:
        return Event(
            target_name=name,
            kind=EventKind.EXPIRING,
            severity=Severity.WARNING,
            message=f"{name}: expiry",
            details={"days_to_expire": days} if days is not None else {},
        )

    events = [
        expiry("far", 40),
        expiry("chain", None),  # no expiry figure -> keeps trailing position
        expiry("expired", -3),
        expiry("soon", 5),
    ]
    lines = n._body(events).splitlines()
    order = [line.split(": ")[0].removeprefix("[warning] ") for line in lines]
    assert order == ["expired", "soon", "far", "chain"]


def test_email_order_severity_puts_worst_first():
    n = EmailNotifier(host="smtp", to="a@b.c", from_addr="c@d.e", order="severity")
    events = [
        _event(Severity.INFO, "a: recovered"),
        _event(Severity.CRITICAL, "b: down"),
        _event(Severity.WARNING, "c: soon"),
    ]
    order = [line.split(":")[0].split("] ")[1] for line in n._body(events).splitlines()]
    assert order == ["b", "c", "a"]


def test_email_order_none_keeps_detection_order():
    n = EmailNotifier(host="smtp", to="a@b.c", from_addr="c@d.e", order="none")
    events = [
        _event(Severity.WARNING, "a: soon"),
        _event(Severity.CRITICAL, "b: down"),
    ]
    order = [line.split(":")[0].split("] ")[1] for line in n._body(events).splitlines()]
    assert order == ["a", "b"]


def test_email_rejects_invalid_order():
    with pytest.raises(ValueError):
        EmailNotifier(host="smtp", to="a@b.c", from_addr="c@d.e", order="bogus")


@pytest.mark.parametrize(
    "creds", [{"username": "u", "password": "p"}, {"password": "p"}]
)
def test_email_refuses_credentials_without_tls(creds):
    with pytest.raises(ValueError, match="clear text"):
        EmailNotifier(
            host="smtp", to="a@b.c", from_addr="c@d.e", use_tls=False, **creds
        )


def test_email_allows_credentials_over_tls_or_ssl_and_plain_relay():
    creds = {"username": "u", "password": "p"}
    EmailNotifier(host="smtp", to="a@b.c", from_addr="c@d.e", **creds)
    EmailNotifier(
        host="smtp", to="a@b.c", from_addr="c@d.e", use_tls=False, use_ssl=True, **creds
    )
    # An unauthenticated relay may still run without TLS.
    EmailNotifier(host="smtp", to="a@b.c", from_addr="c@d.e", use_tls=False)


def test_email_send_swallows_errors(monkeypatch):
    n = EmailNotifier(host="smtp", to="a@b.c", from_addr="c@d.e")

    def boom(_message):
        raise OSError("connection refused")

    monkeypatch.setattr(n, "_deliver", boom)
    # Must not raise even though delivery fails; it reports the failure.
    assert n.send([_event()]) is False


def test_filters_pass_through_the_delivery_result():
    class _Failing(ConsoleNotifier):
        def send(self, events):
            return False

    from certminder.notifiers import _KindFilterNotifier, _MinSeverityNotifier

    kind_filter = _KindFilterNotifier(_Failing(), {EventKind.EXPIRING})
    assert kind_filter.send([_event()]) is False
    # Nothing to forward means nothing failed.
    assert kind_filter.send([_kind_event(EventKind.EXPIRED, "x")]) is True
    severity_filter = _MinSeverityNotifier(_Failing(), Severity.CRITICAL)
    assert severity_filter.send([_event(Severity.WARNING)]) is True
    assert severity_filter.send([_event(Severity.CRITICAL)]) is False


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
