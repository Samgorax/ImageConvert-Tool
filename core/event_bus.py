"""
core/event_bus.py
=================
Lightweight in-process publish/subscribe bus used to decouple layers
without importing PySide6 signals into non-UI code.

Usage::

    from core.event_bus import bus

    bus.subscribe("job.completed", on_job_done)
    bus.publish("job.completed", job=result)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

_log = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable[..., None]) -> None:
        """Register *handler* for *event*."""
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable[..., None]) -> None:
        """Remove *handler* from *event*.  No-op if not registered."""
        try:
            self._handlers[event].remove(handler)
        except ValueError:
            pass

    def publish(self, event: str, **kwargs: Any) -> None:
        """Dispatch *event* to all handlers.  Handler exceptions are logged, not re-raised."""
        for handler in list(self._handlers[event]):
            try:
                handler(**kwargs)
            except Exception:
                _log.exception("Event handler %r raised for event %r", handler, event)


# Module-level singleton — import and use directly
bus = EventBus()
