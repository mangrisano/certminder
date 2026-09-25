"""POST events as JSON to a generic HTTP webhook."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from certminder.models import Event
from certminder.notifiers.base import RemoteNotifier


class WebhookNotifier(RemoteNotifier):
    """Deliver events as a JSON array to an arbitrary endpoint."""

    name = "webhook"
    delivery_errors = (urllib.error.URLError, OSError)

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ):
        if not url:
            raise ValueError("webhook notifier requires 'url'")
        scheme = urllib.parse.urlsplit(url).scheme.lower()
        if scheme not in ("http", "https"):
            raise ValueError("webhook notifier 'url' must be an http(s) URL")
        if scheme == "http":
            # The URL itself is not printed: it may carry a token.
            print(
                "certminder: warning: the webhook notifier uses plain http://, "
                "so events and headers are sent unencrypted",
                file=sys.stderr,
            )
        self.url = url
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.timeout = timeout

    def _payload(self, events: list[Event]) -> bytes:
        return json.dumps(
            [
                {
                    "target": e.target_name,
                    "kind": e.kind.value,
                    "severity": e.severity.value,
                    "message": e.message,
                    "details": e.details,
                }
                for e in events
            ]
        ).encode()

    def _deliver(self, events: list[Event]) -> None:
        request = urllib.request.Request(
            self.url,
            data=self._payload(events),
            headers=self.headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as resp:
            resp.read()
