"""
engine/base.py
==============
Abstract interface all conversion engine adapters must satisfy.
The UI and worker threads talk to this interface only —
they never import a concrete adapter directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from engine.job import ConversionJob, ConversionResult


class BaseConversionEngine(ABC):
    """
    Contract for a conversion engine.

    Rules:
    - ``convert()`` is called from a QThread worker — it MUST NOT touch the UI.
    - Progress is reported via the optional *progress_callback* (0-100 int).
    - Raise ``EngineError`` subclasses on hard failures.
    - Return ``ConversionResult(success=False)`` on soft (recoverable) failures.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True iff the underlying tool is locatable and runnable."""

    @abstractmethod
    def get_version(self) -> str:
        """Return tool version string, or '' if unavailable."""

    @abstractmethod
    def convert(
        self,
        job: ConversionJob,
        progress_callback: Callable[[int], None] | None = None,
    ) -> ConversionResult:
        """Execute the conversion described by *job*."""
