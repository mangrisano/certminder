"""Notifier registry and base class.

A notifier receives the events produced in a cycle and delivers them somewhere
(stdout, Slack, a generic webhook). New sinks register themselves in
:data:`REGISTRY` so the configuration's ``type`` field can resolve them.
"""

from __future__ import annotations

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


def build_notifier(kind: str, options: dict) -> Notifier:
    """Instantiate a notifier of ``kind`` with its options."""
    try:
        cls = REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(
            f"unknown notifier type {kind!r}; choose from {sorted(REGISTRY)}"
        ) from exc
    return cls(**options)


__all__ = ["Notifier", "REGISTRY", "build_notifier"]
