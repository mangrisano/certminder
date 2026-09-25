"""Send events as an email via SMTP (stdlib only)."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from certminder.models import Event, Severity
from certminder.notifiers.base import RemoteNotifier

# Highest-to-lowest so the subject reflects the worst event in the batch.
_SEVERITY_RANK = {
    Severity.CRITICAL: 2,
    Severity.WARNING: 1,
    Severity.INFO: 0,
}


class EmailNotifier(RemoteNotifier):
    """Deliver a single summary email per cycle through an SMTP server.

    STARTTLS (``use_tls``, the default) and implicit TLS (``use_ssl``) are both
    supported; an unauthenticated relay is allowed by omitting credentials.
    """

    name = "email"
    delivery_errors = (smtplib.SMTPException, OSError)

    # How the body lines are ordered; configured via the ``order`` option.
    ORDERS = ("expiry", "severity", "none")

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
        order: str = "expiry",
    ):
        if not host:
            raise ValueError("email notifier requires 'host'")
        if not to:
            raise ValueError("email notifier requires 'to'")
        if not from_addr:
            raise ValueError("email notifier requires 'from_addr'")
        if order not in self.ORDERS:
            raise ValueError(
                f"email notifier 'order' must be one of {list(self.ORDERS)}, "
                f"got {order!r}"
            )
        if (username or password) and not (use_tls or use_ssl):
            raise ValueError(
                "email notifier would send its credentials in clear text: "
                "enable 'use_tls' or 'use_ssl', or drop 'username'/'password'"
            )
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
        self.order = order

    def _subject(self, events: list[Event]) -> str:
        worst = max(events, key=lambda e: _SEVERITY_RANK[e.severity]).severity
        count = len(events)
        noun = "event" if count == 1 else "events"
        return f"{self.subject_prefix} {worst.value.upper()}: {count} {noun}"

    @staticmethod
    def _expiry_order(event: Event) -> tuple[int, int]:
        """Sort key placing the soonest-expiring certificates first.

        Expiry events carry ``days_to_expire``; they sort by it ascending, so an
        already-expired cert (negative) ranks above one due in a few days. Events
        without an expiry figure keep their original position, after the rest.
        """
        days = event.details.get("days_to_expire")
        if isinstance(days, int):
            return (0, days)
        return (1, 0)

    def _ordered(self, events: list[Event]) -> list[Event]:
        """Order the events for the body per the configured ``order``."""
        if self.order == "expiry":
            return sorted(events, key=self._expiry_order)
        if self.order == "severity":
            return sorted(events, key=lambda e: -_SEVERITY_RANK[e.severity])
        return list(events)

    def _body(self, events: list[Event]) -> str:
        ordered = self._ordered(events)
        return "\n".join(f"[{e.severity.value}] {e.message}" for e in ordered)

    def _build_message(self, events: list[Event]) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = self._subject(events)
        message["From"] = self.from_addr
        message["To"] = ", ".join(self.recipients)
        message.set_content(self._body(events))
        return message

    def _deliver(self, events: list[Event]) -> None:
        message = self._build_message(events)
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
