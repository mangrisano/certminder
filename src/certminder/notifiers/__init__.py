"""Notifier registry and base class.

A notifier receives the events produced in a cycle and delivers them somewhere
(stdout, Slack, a generic webhook). New sinks register themselves in
:data:`REGISTRY` so the configuration's ``type`` field can resolve them.
"""

from __future__ import annotations

from certminder.models import Event, EventKind, Severity
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


class _KindFilterNotifier(Notifier):
    """Wrap a notifier so it only receives events of selected kinds."""

    def __init__(self, inner: Notifier, kinds: set[EventKind]):
        self._inner = inner
        self._kinds = kinds

    def send(self, events: list[Event]) -> None:
        kept = [e for e in events if e.kind in self._kinds]
        if kept:
            self._inner.send(kept)


def build_notifier(kind: str, options: dict) -> Notifier:
    """Instantiate a notifier of ``kind`` with its options.

    Two filters are handled here for every notifier so a sink can be scoped to
    just what its audience cares about:

    * ``min_severity`` (``info``/``warning``/``critical``) drops events below
      that level (e.g. send only ``critical`` to Slack while the console keeps
      everything).
    * ``kinds`` is an allowlist of :class:`EventKind` values (e.g.
      ``[expired]``): the sink then only receives events of those kinds. Note
      that ``recovered`` is itself a kind, so include it to also be told when a
      selected problem clears.
    """
    options = dict(options)
    min_severity = options.pop("min_severity", None)
    only_kinds = options.pop("kinds", None)
    try:
        cls = REGISTRY[kind]
    except KeyError as exc:
        raise ValueError(
            f"unknown notifier type {kind!r}; choose from {sorted(REGISTRY)}"
        ) from exc
    notifier = cls(**options)
    if only_kinds is not None:
        names = [only_kinds] if isinstance(only_kinds, str) else list(only_kinds)
        try:
            allowed = {EventKind(name) for name in names}
        except ValueError as exc:
            raise ValueError(
                f"invalid kind in {names!r}; choose from {[k.value for k in EventKind]}"
            ) from exc
        notifier = _KindFilterNotifier(notifier, allowed)
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
