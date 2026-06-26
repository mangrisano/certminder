"""Base class shared by all notifiers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from certwatch.models import Event


class Notifier(ABC):
    """Deliver a batch of events to some destination."""

    @abstractmethod
    def send(self, events: list[Event]) -> None:
        """Deliver ``events``. Implementations must not raise on delivery
        failure; they should swallow and report errors so one broken sink does
        not abort the watch loop."""
