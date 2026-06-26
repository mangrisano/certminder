"""POST events as JSON to a generic HTTP webhook."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from certwatch.models import Event
from certwatch.notifiers.base import Notifier


class WebhookNotifier(Notifier):
    """Deliver events as a JSON array to an arbitrary endpoint."""

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ):
        if not url:
            raise ValueError("webhook notifier requires 'url'")
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

    def send(self, events: list[Event]) -> None:
        if not events:
            return
        request = urllib.request.Request(
            self.url,
            data=self._payload(events),
            headers=self.headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                resp.read()
        except (urllib.error.URLError, OSError) as exc:
            print(f"certwatch: webhook delivery failed: {exc}", file=sys.stderr)
