"""Send events as an email via SMTP (stdlib only)."""

from __future__ import annotations

import smtplib
import ssl
import sys
from email.message import EmailMessage

from certminder.models import Event, Severity
from certminder.notifiers.base import Notifier

# Highest-to-lowest so the subject reflects the worst event in the batch.
_SEVERITY_RANK = {
    Severity.CRITICAL: 2,
    Severity.WARNING: 1,
    Severity.INFO: 0,
}


class EmailNotifier(Notifier):
    """Deliver a single summary email per cycle through an SMTP server.

    STARTTLS (``use_tls``, the default) and implicit TLS (``use_ssl``) are both
    supported; an unauthenticated relay is allowed by omitting credentials.
    """

    def __init__(
        self,
        host: str,
        to: str | list[str],
        from_addr: str,
        port: int = 587,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        subject_prefix: str = "[certminder]",
        timeout: float = 10.0,
    ):
        if not host:
            raise ValueError("email notifier requires 'host'")
        if not to:
            raise ValueError("email notifier requires 'to'")
        if not from_addr:
            raise ValueError("email notifier requires 'from_addr'")
        self.host = host
        self.recipients = [to] if isinstance(to, str) else list(to)
        self.from_addr = from_addr
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.subject_prefix = subject_prefix
        self.timeout = timeout

    def _subject(self, events: list[Event]) -> str:
        worst = max(events, key=lambda e: _SEVERITY_RANK[e.severity]).severity
        count = len(events)
        noun = "event" if count == 1 else "events"
        return f"{self.subject_prefix} {worst.value.upper()}: {count} {noun}"

    def _body(self, events: list[Event]) -> str:
        return "\n".join(f"[{e.severity.value}] {e.message}" for e in events)

    def _build_message(self, events: list[Event]) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = self._subject(events)
        message["From"] = self.from_addr
        message["To"] = ", ".join(self.recipients)
        message.set_content(self._body(events))
        return message

    def send(self, events: list[Event]) -> None:
        if not events:
            return
        message = self._build_message(events)
        try:
            self._deliver(message)
        except (smtplib.SMTPException, OSError) as exc:
            print(f"certminder: email delivery failed: {exc}", file=sys.stderr)

    def _deliver(self, message: EmailMessage) -> None:
        if self.use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                self.host, self.port, timeout=self.timeout, context=context
            ) as server:
                self._authenticate_and_send(server, message)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                if self.use_tls:
                    server.starttls(context=ssl.create_default_context())
                self._authenticate_and_send(server, message)

    def _authenticate_and_send(
        self, server: smtplib.SMTP, message: EmailMessage
    ) -> None:
        if self.username and self.password:
            server.login(self.username, self.password)
        server.send_message(message)
