"""Notifier registry and base class.

A notifier receives the events produced in a cycle and delivers them somewhere
(stdout, Slack, a generic webhook). New sinks register themselves in
:data:`REGISTRY` so the configuration's ``type`` field can resolve them.
"""

from __future__ import annotations

from certminder.models import Event, Severity
from certminder.notifiers.base import Notifier
from certminder.notifiers.console import ConsoleNotifier
from certminder.notifiers.email import EmailNotifier
from certminder.notifiers.slack import SlackNotifier
from certminder.notifiers.webhook import WebhookNotifier

REGISTRY: dict[str, type[Notifier]] = {
    "console": ConsoleNotifier,
    "email": EmailNotifier,
    "slack": SlackNotifier,
    "webhook": WebhookNotifier,
}

_SEVERITY_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}


class _MinSeverityNotifier(Notifier):
    """Wrap a notifier so it only receives events at or above a threshold."""

    def __init__(self, inner: Notifier, min_severity: Severity):
        self._inner = inner
        self._threshold = _SEVERITY_RANK[min_severity]

    def send(self, events: list[Event]) -> None:
        kept = [e for e in events if _SEVERITY_RANK[e.severity] >= self._threshold]
        if kept:
            self._inner.send(kept)


def build_notifier(kind: str, options: dict) -> Notifier:
    """Instantiate a notifier of ``kind`` with its options.

    A ``min_severity`` option (``info``/``warning``/``critical``) is handled
    here for every notifier: the sink then only receives events at or above
    that level (e.g. send only ``critical`` to Slack while the console keeps
    everything).
    """
    options = dict(options)
    min_severity = options.pop("min_severity", None)
    try:
        cls = REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(
            f"unknown notifier type {kind!r}; choose from {sorted(REGISTRY)}"
        ) from exc
    notifier = cls(**options)
    if min_severity is not None:
        try:
            level = Severity(min_severity)
        except ValueError as exc:
            raise ValueError(
                f"invalid min_severity {min_severity!r}; "
                f"choose from {[s.value for s in Severity]}"
            ) from exc
        notifier = _MinSeverityNotifier(notifier, level)
    return notifier


__all__ = ["Notifier", "REGISTRY", "build_notifier"]
