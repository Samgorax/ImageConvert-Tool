"""
engine/health_check.py
======================
Discovers and validates external tools at application start-up.
Returns a HealthReport the UI can inspect to warn the user of missing tools
before they try to perform a conversion.

Design rules:
- No hard-coded version strings or paths.
- Uses glob patterns to find the newest installed version on Windows.
- Runs quickly (subprocess calls have a 10-second timeout).
- Never raises; bad state is expressed as ``ToolInfo(found=False)``.
"""
from __future__ import annotations

import glob
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

from core.config import (
    GHOSTSCRIPT_EXECUTABLES,
    GHOSTSCRIPT_WIN_GLOBS,
    IMAGEMAGICK_WIN_GLOBS,
)

_log = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    name:    str
    found:   bool
    path:    str = ""
    version: str = ""
    notes:   str = ""


@dataclass
class HealthReport:
    imagemagick: ToolInfo = field(
        default_factory=lambda: ToolInfo("ImageMagick", False)
    )
    ghostscript: ToolInfo = field(
        default_factory=lambda: ToolInfo("Ghostscript", False)
    )

    @property
    def conversion_ok(self) -> bool:
        """Basic image conversion is possible."""
        return self.imagemagick.found

    @property
    def pdf_ok(self) -> bool:
        """PDF / PS / EPS conversion is possible (needs both tools)."""
        return self.imagemagick.found and self.ghostscript.found


# ── Internal helpers ───────────────────────────────────────────────────────────

def _first_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0] if lines else ""


def _probe_version(executable: str, version_args: list[str]) -> str:
    """Run *executable version_args* and return the first non-empty output line."""
    try:
        r = subprocess.run(
            [executable, *version_args],
            capture_output=True, text=True, timeout=10,
        )
        return _first_line(r.stdout or r.stderr)
    except Exception as exc:
        _log.debug("Version probe failed for %r: %s", executable, exc)
        return ""


def _glob_newest(patterns: list[str]) -> str | None:
    """Return the lexicographically-largest (newest) match across *patterns*, or None."""
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(glob.glob(pattern))
    return sorted(matches)[-1] if matches else None


# ── Public discovery functions ─────────────────────────────────────────────────

def find_imagemagick() -> ToolInfo:
    """Locate ImageMagick's ``magick`` executable."""
    # 1. PATH lookup (cross-platform)
    path = shutil.which("magick")

    # 2. Windows glob fallback (version-agnostic)
    if not path and sys.platform == "win32":
        path = _glob_newest(IMAGEMAGICK_WIN_GLOBS)

    if not path:
        return ToolInfo(
            "ImageMagick", False,
            notes="Install from https://imagemagick.org/ and add to PATH.",
        )

    version = _probe_version(path, ["--version"])
    _log.info("ImageMagick found: %s (%s)", path, version)
    return ToolInfo("ImageMagick", True, path=path, version=version)


def find_ghostscript() -> ToolInfo:
    """Locate a Ghostscript executable."""
    # 1. Try well-known executable names via PATH
    for name in GHOSTSCRIPT_EXECUTABLES:
        path = shutil.which(name)
        if path:
            version = _probe_version(path, ["--version"])
            _log.info("Ghostscript found: %s (%s)", path, version)
            return ToolInfo("Ghostscript", True, path=path, version=version)

    # 2. Windows glob fallback
    if sys.platform == "win32":
        path = _glob_newest(GHOSTSCRIPT_WIN_GLOBS)
        if path:
            version = _probe_version(path, ["--version"])
            _log.info("Ghostscript found via glob: %s (%s)", path, version)
            return ToolInfo("Ghostscript", True, path=path, version=version)

    return ToolInfo(
        "Ghostscript", False,
        notes=(
            "Install from https://www.ghostscript.com/ — "
            "required for PDF / PS / EPS conversion."
        ),
    )


def run_health_check() -> HealthReport:
    """Probe all required external tools and return a HealthReport."""
    return HealthReport(
        imagemagick=find_imagemagick(),
        ghostscript=find_ghostscript(),
    )
