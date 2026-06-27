"""Print events to stdout. The default, dependency-free sink."""

from __future__ import annotations

import sys
from datetime import datetime

from certminder.models import Event, Severity
from certminder.notifiers.base import Notifier

_ICON = {
    Severity.INFO: "[ok]",
    Severity.WARNING: "[warn]",
    Severity.CRITICAL: "[crit]",
}


class ConsoleNotifier(Notifier):
    """Write one line per event to stdout (or stderr for problems).

    When ``timestamp`` is true each line is prefixed with the local date and
    time, which is useful when the output is collected into a log.
    """

    def __init__(self, timestamp: bool = False):
        self.timestamp = timestamp

    def send(self, events: list[Event]) -> None:
        for event in events:
            stream = sys.stdout if event.severity is Severity.INFO else sys.stderr
            prefix = ""
            if self.timestamp:
                prefix = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " "
            print(f"{prefix}{_ICON[event.severity]} {event.message}", file=stream)
