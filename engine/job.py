"""
engine/job.py
=============
ConversionJob and ConversionResult dataclasses — the data contract
between the UI, the engine adapters, and the storage layer.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from pathlib import Path


class JobStatus(Enum):
    QUEUED    = auto()
    RUNNING   = auto()
    COMPLETED = auto()
    FAILED    = auto()
    CANCELLED = auto()


@dataclass
class ConversionOptions:
    """Knobs the user can adjust per conversion.  Defaults mirror legacy tool."""
    quality:        int  = 95     # JPG / WEBP / AVIF / HEIC output quality (1-100)
    density:        int  = 300    # Rasterisation DPI for PDF / PS / EPS input
    all_pages:      bool = True   # Split multipage documents into numbered files
    strip_metadata: bool = False  # Remove EXIF / IPTC / XMP
    flatten_alpha:  bool = True   # Composite transparent pixels onto white for lossy output


@dataclass
class ConversionJob:
    input_path:    Path
    output_path:   Path
    input_format:  str
    output_format: str
    options:       ConversionOptions = field(default_factory=ConversionOptions)
    job_id:        str               = field(default_factory=lambda: str(uuid.uuid4()))
    created_at:    datetime          = field(
        default_factory=lambda: datetime.now(UTC)
    )
    status:           JobStatus = field(default=JobStatus.QUEUED, init=False)
    duration_seconds: float     = field(default=0.0,              init=False)
    error_message:    str       = field(default="",               init=False)

    def __post_init__(self) -> None:
        self.input_format  = self.input_format.upper()
        self.output_format = self.output_format.upper()

    @property
    def is_same_format(self) -> bool:
        return self.input_format == self.output_format


@dataclass
class ConversionResult:
    job_id:           str
    success:          bool
    output_path:      Path | None
    duration_seconds: float
    error_message:    str = ""
    stdout:           str = ""
    stderr:           str = ""
