"""
core/config.py
==============
Application-wide constants and path resolution.
All magic values live here; no other module may hard-code paths or numbers.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Identity ───────────────────────────────────────────────────────────────────
APP_NAME    = "Sovereign Workbench"
APP_VERSION = "2.0.0"
APP_SLUG    = "sovereign-workstation"

# ── Repository root (this file is at <root>/core/config.py) ───────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent


def _app_data_dir() -> Path:
    """Platform-appropriate writable data directory for the application."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_SLUG


APP_DATA_DIR = _app_data_dir()
DB_PATH      = APP_DATA_DIR / "workstation.db"
LOG_DIR      = APP_DATA_DIR / "logs"

# ── Conversion limits ──────────────────────────────────────────────────────────
MAX_FILE_SIZE_BYTES        = 500 * 1024 * 1024   # 500 MB hard stop
CONVERSION_TIMEOUT_SECONDS = 600                 # 10 minutes (same as legacy)

# ── External tool discovery ────────────────────────────────────────────────────
# Glob patterns tried in order on Windows when `magick` is not on PATH.
# The wildcard matches any installed version so we never hard-code "7.1.2".
IMAGEMAGICK_WIN_GLOBS: list[str] = [
    r"C:\Program Files\ImageMagick*\magick.exe",
    r"C:\Program Files (x86)\ImageMagick*\magick.exe",
]

GHOSTSCRIPT_WIN_GLOBS: list[str] = [
    r"C:\Program Files\gs\gs*\bin\gswin64c.exe",
    r"C:\Program Files (x86)\gs\gs*\bin\gswin32c.exe",
]

# Executable names tried via shutil.which (cross-platform)
GHOSTSCRIPT_EXECUTABLES: list[str] = ["gswin64c", "gswin32c", "gs"]

# ── Format constants ───────────────────────────────────────────────────────────
FORMATS: list[str] = [
    "PNG", "JPG", "JPEG", "WEBP", "GIF", "BMP", "TIFF", "TIF", "ICO",
    "SVG", "PDF", "PS",  "EPS",  "AVIF", "HEIC", "JP2", "J2K", "PNM",
    "PPM", "PGM", "PBM", "TGA",  "DDS",  "HDR",  "EXR", "PCX", "XPM",
    "MIFF", "MNG", "PAM", "PGX", "RAS",  "SUN",  "WBMP",
]

# Formats that must be rasterised with -density before conversion
VECTOR_DOC_FORMATS: frozenset[str] = frozenset({"PDF", "PS", "EPS"})

# Formats whose output benefits from a -quality flag
LOSSY_FORMATS: frozenset[str] = frozenset({"JPG", "JPEG", "WEBP", "AVIF", "HEIC"})

# Formats that may contain multiple pages or frames
MULTIPAGE_FORMATS: frozenset[str] = frozenset(
    {"PDF", "PS", "EPS", "GIF", "TIFF", "TIF", "MNG"}
)

# Formats that support an alpha (transparency) channel
TRANSPARENT_FORMATS: frozenset[str] = frozenset(
    {"PNG", "WEBP", "GIF", "TIFF", "TIF", "ICO", "AVIF"}
)

# Default conversion options (mirrors legacy defaults)
DEFAULT_QUALITY  = 95
DEFAULT_DENSITY  = 300
DEFAULT_ALL_PAGES = True
