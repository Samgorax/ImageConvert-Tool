"""
Shared fixtures for the Sovereign Workstation test suite.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def tmp_workdir(tmp_path: Path) -> Path:
    """Return a temporary directory guaranteed to exist."""
    return tmp_path


@pytest.fixture()
def sample_png(tmp_path: Path) -> Path:
    """Return the path to a tiny (1×1) valid PNG file."""
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"                          # PNG signature
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01"        # IHDR chunk: 1×1
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00"      # 8-bit RGB
        b"\x90wS\xde"                                  # CRC
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"    # IDAT
        b"\x00\x01\x01\x00\x05\x18\xd8\n"             # compressed pixel
        b"\x00\x00\x00\x00IEND\xaeB`\x82"             # IEND
    )
    p = tmp_path / "sample.png"
    p.write_bytes(png_bytes)
    return p
