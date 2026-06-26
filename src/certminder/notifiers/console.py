"""Print events to stdout. The default, dependency-free sink."""

from __future__ import annotations

import sys

from certminder.models import Event, Severity
from certminder.notifiers.base import Notifier

_ICON = {
    Severity.INFO: "[ok]",
    Severity.WARNING: "[warn]",
    Severity.CRITICAL: "[crit]",
}


class ConsoleNotifier(Notifier):
    """Write one line per event to stdout (or stderr for problems)."""

    def send(self, events: list[Event]) -> None:
        for event in events:
            stream = sys.stdout if event.severity is Severity.INFO else sys.stderr
            print(f"{_ICON[event.severity]} {event.message}", file=stream)
