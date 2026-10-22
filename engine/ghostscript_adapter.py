"""
engine/ghostscript_adapter.py
=============================
Thin wrapper for Ghostscript — used for PDF/A output and advanced PDF work.
Phase 1: provides version detection and availability check only.
Full PDF/A conversion is planned for Phase 2.
"""
from __future__ import annotations

from engine.health_check import find_ghostscript


class GhostscriptAdapter:
    """
    Lightweight Ghostscript adapter.

    Phase 1 exposes only availability / version; the ImageMagick adapter
    delegates PDF work to ImageMagick which itself calls Ghostscript as a
    delegate.  A standalone GS workflow is reserved for Phase 2 (PDF/A,
    searchable PDF via OCR).
    """

    def __init__(self) -> None:
        self._tool = find_ghostscript()

    def is_available(self) -> bool:
        return self._tool.found

    def get_version(self) -> str:
        return self._tool.version

    @property
    def executable(self) -> str | None:
        return self._tool.path if self._tool.found else None
