"""
core/exceptions.py
==================
Domain exception hierarchy.  All application code raises one of these;
UI code catches them and shows friendly messages.
"""
from __future__ import annotations


class WorkstationError(Exception):
    """Base exception for all Sovereign Workstation errors."""


# ── Engine layer ───────────────────────────────────────────────────────────────

class EngineError(WorkstationError):
    """A conversion engine encountered an unrecoverable error."""


class ToolNotFoundError(EngineError):
    """An external tool (ImageMagick, Ghostscript, …) could not be located."""

    def __init__(self, tool: str) -> None:
        self.tool = tool
        super().__init__(
            f"External tool not found: '{tool}'. "
            "Install it and ensure its directory is on PATH, then restart."
        )


class ConversionError(EngineError):
    """The conversion process ran but produced an error exit code."""

    def __init__(self, message: str, returncode: int = -1, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr     = stderr
        super().__init__(message)


class ConversionTimeoutError(EngineError):
    """The conversion process did not complete within the allowed time."""


# ── Input / path layer ─────────────────────────────────────────────────────────

class InputFileError(WorkstationError):
    """Problem with the input file: not found, too large, unreadable, etc."""


class PathTraversalError(WorkstationError):
    """A user-supplied path attempted to escape the allowed directory."""


# ── Storage layer ──────────────────────────────────────────────────────────────

class StorageError(WorkstationError):
    """Database or file-system storage failure."""


# ── Permission layer ───────────────────────────────────────────────────────────

class PermissionDeniedError(WorkstationError):
    """The requested action is blocked by the current permission policy."""
