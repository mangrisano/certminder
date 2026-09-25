"""Base class shared by all notifiers."""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod

from certminder.models import Event


class Notifier(ABC):
    """Deliver a batch of events to some destination."""

    @abstractmethod
    def send(self, events: list[Event]) -> bool | None:
        """Deliver ``events`` and return ``False`` if they were not delivered.

        Implementations must not raise on delivery failure; they should report
        the error and return ``False`` so the events are retried on the next
        cycle. ``True`` or ``None`` means delivered."""


class RemoteNotifier(Notifier):
    """A :class:`Notifier` that delivers over the network or SMTP.

    Subclasses implement :meth:`_deliver` and declare which exceptions their
    transport raises on failure in :attr:`delivery_errors`; this base class
    reports any such failure to stderr so one broken sink never aborts the
    watch loop, without every subclass repeating the same ``try/except``.
    """

    #: The name used in the "X delivery failed" message, e.g. "slack".
    name: str
    #: Exception type(s) the transport raises on a delivery failure.
    delivery_errors: type[BaseException] | tuple[type[BaseException], ...] = OSError

    def _deliver(self, events: list[Event]) -> None:
        """Send ``events`` over the transport. Raise on failure."""
        raise NotImplementedError

    def send(self, events: list[Event]) -> bool:
        if not events:
            return True
        try:
            self._deliver(events)
        except self.delivery_errors as exc:
            print(f"certminder: {self.name} delivery failed: {exc}", file=sys.stderr)
            return False
        return True
