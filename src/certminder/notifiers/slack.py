"""Post events to a Slack Incoming Webhook."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from certminder.models import Event, Severity
from certminder.notifiers.base import RemoteNotifier

_EMOJI = {
    Severity.INFO: ":white_check_mark:",
    Severity.WARNING: ":warning:",
    Severity.CRITICAL: ":rotating_light:",
}


class SlackNotifier(RemoteNotifier):
    """Send a single Slack message summarising the cycle's events."""

    name = "slack"
    delivery_errors = (urllib.error.URLError, OSError)

    def __init__(self, webhook_url: str, timeout: float = 10.0):
        if not webhook_url:
            raise ValueError("slack notifier requires 'webhook_url'")
        self.webhook_url = webhook_url
        self.timeout = timeout

    def _format(self, events: list[Event]) -> str:
        return "\n".join(f"{_EMOJI[e.severity]} {e.message}" for e in events)

    def _deliver(self, events: list[Event]) -> None:
        payload = json.dumps({"text": self._format(events)}).encode()
        request = urllib.request.Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as resp:
            resp.read()
