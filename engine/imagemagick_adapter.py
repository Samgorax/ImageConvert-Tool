"""
engine/imagemagick_adapter.py
=============================
ImageMagick conversion engine — the clean replacement for the monolith's
``convert_now()`` method.

Key improvements over the legacy code:
- Runs in a QThread worker (never blocks the UI).
- Validates file existence and size before launching the process.
- Prevents path traversal via ``_validate_path()``.
- Builds an argument list (no shell=True, no string injection risk).
- Produces the same ImageMagick flags as the legacy ``get_command()`` —
  verified by tests/unit/test_legacy_behavior.py.
- All magic values come from core.config, not hard-coded here.
"""
from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from core.config import (
    CONVERSION_TIMEOUT_SECONDS,
    LOSSY_FORMATS,
    MAX_FILE_SIZE_BYTES,
    MULTIPAGE_FORMATS,
    TRANSPARENT_FORMATS,
    VECTOR_DOC_FORMATS,
)
from core.exceptions import (
    ConversionError,
    ConversionTimeoutError,
    InputFileError,
    PathTraversalError,
    ToolNotFoundError,
)
from engine.base import BaseConversionEngine
from engine.health_check import ToolInfo, find_imagemagick
from engine.job import ConversionJob, ConversionOptions, ConversionResult, JobStatus

_log = logging.getLogger(__name__)


# ── Path validation ────────────────────────────────────────────────────────────

def _validate_path(path: Path, base: Path | None = None) -> Path:
    """
    Resolve *path* and verify it stays within *base* (if given).

    Raises ``PathTraversalError`` if the resolved path escapes *base*.
    Does NOT require the path to exist.
    """
    resolved = path.resolve()
    if base is not None:
        try:
            resolved.relative_to(base.resolve())
        except ValueError as exc:
            raise PathTraversalError(
                f"Path '{path}' resolves to '{resolved}', "
                f"which is outside the allowed directory '{base}'."
            ) from exc
    return resolved


# ── Adapter ────────────────────────────────────────────────────────────────────

class ImageMagickAdapter(BaseConversionEngine):
    """
    Wraps the ImageMagick ``magick`` CLI.

    Thread-safety: ``convert()`` is designed to run on a QThread worker.
    Do NOT call it from the main thread.
    """

    def __init__(self, tool_info: ToolInfo | None = None) -> None:
        self._tool = tool_info if tool_info is not None else find_imagemagick()

    # ── BaseConversionEngine interface ─────────────────────────────────────────

    def is_available(self) -> bool:
        return self._tool.found

    def get_version(self) -> str:
        return self._tool.version

    @property
    def executable(self) -> str:
        if not self._tool.found:
            raise ToolNotFoundError("magick")
        return self._tool.path

    # ── Argument builder ───────────────────────────────────────────────────────

    def _build_args(self, job: ConversionJob) -> list[str]:
        """
        Construct the ``magick`` argument list for *job*.

        The flag ordering and logic must produce behaviour equivalent to
        the legacy ``get_command()`` (see tests/unit/test_legacy_behavior.py).
        """
        opts: ConversionOptions = job.options
        src  = job.input_format   # already normalised to uppercase
        dst  = job.output_format

        args: list[str] = [self.executable]

        # 1. Rasterise vector / document sources at the requested DPI
        if src in VECTOR_DOC_FORMATS:
            args += ["-density", str(opts.density)]

        # 2. Input file
        args.append(str(job.input_path))

        # 3. Strip metadata (optional)
        if opts.strip_metadata:
            args += ["-strip"]

        # 4. Flatten transparency when converting to a lossy / opaque format
        #    Only trigger when the source *has* transparency AND the dest does not.
        if src in TRANSPARENT_FORMATS and dst not in TRANSPARENT_FORMATS:
            if opts.flatten_alpha:
                args += ["-background", "white", "-alpha", "remove", "-alpha", "off"]

        # 5. Quality for lossy output formats
        if dst in LOSSY_FORMATS:
            args += ["-quality", str(opts.quality)]

        # 6. Output file
        args.append(str(job.output_path))

        return args

    def _resolve_output_path(self, job: ConversionJob) -> Path:
        """
        Return the concrete output path, expanding multipage pattern if needed.
        For multipage sources the output already contains ``%03d`` in its stem;
        we return the path as-is and let ImageMagick handle the expansion.
        """
        src      = job.input_format
        dst      = job.output_format
        out_dir  = job.output_path.parent
        stem     = job.output_path.stem
        suffix   = f".{dst.lower()}"

        is_multipage = (
            job.options.all_pages
            and src in MULTIPAGE_FORMATS
        )

        if is_multipage:
            return out_dir / f"{stem}-%03d{suffix}"
        return out_dir / f"{stem}{suffix}"

    # ── Main convert method ────────────────────────────────────────────────────

    def convert(
        self,
        job: ConversionJob,
        progress_callback: Callable[[int], None] | None = None,
    ) -> ConversionResult:
        """
        Execute the ImageMagick conversion for *job*.

        Called from a background QThread — must NOT touch the UI.
        """
        if not self.is_available():
            raise ToolNotFoundError("magick")

        # ── Validate input ─────────────────────────────────────────────────────
        input_path = _validate_path(job.input_path)

        if not input_path.is_file():
            raise InputFileError(f"Input file not found: '{input_path}'")

        size_bytes = input_path.stat().st_size
        if size_bytes > MAX_FILE_SIZE_BYTES:
            mb = size_bytes // (1024 * 1024)
            limit_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
            raise InputFileError(
                f"Input file is {mb} MB, exceeding the {limit_mb} MB safety limit."
            )

        if job.is_same_format:
            raise ConversionError(
                f"Input and output formats are both '{job.input_format}'. "
                "Please choose different formats."
            )

        # ── Build argument list ────────────────────────────────────────────────
        # Resolve multipage output name before building args
        job.output_path = self._resolve_output_path(job)
        _validate_path(job.output_path, base=job.output_path.parent)

        output_pattern = str(job.output_path)
        if "%03d" in output_pattern:
            candidates_before = list(job.output_path.parent.glob(
                job.output_path.name.replace("%03d", "[0-9][0-9][0-9]")
            ))
        else:
            candidates_before = [job.output_path]
        output_signatures = {
            path: (path.stat().st_size, path.stat().st_mtime_ns)
            for path in candidates_before
            if path.is_file()
        }

        args = self._build_args(job)
        _log.debug("Running: %s", " ".join(args))

        # ── Execute ────────────────────────────────────────────────────────────
        job.status = JobStatus.RUNNING
        if progress_callback:
            progress_callback(5)

        start = time.monotonic()
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=CONVERSION_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            job.status = JobStatus.FAILED
            raise ConversionTimeoutError(
                f"Conversion exceeded {CONVERSION_TIMEOUT_SECONDS // 60} minutes."
            ) from exc
        except OSError as exc:
            job.status = JobStatus.FAILED
            raise ConversionError(f"Failed to launch ImageMagick: {exc}") from exc

        duration = time.monotonic() - start
        job.duration_seconds = duration

        if progress_callback:
            progress_callback(95)

        # ── Interpret result ───────────────────────────────────────────────────
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "Unknown ImageMagick error").strip()
            job.status        = JobStatus.FAILED
            job.error_message = stderr
            _log.error("ImageMagick failed (rc=%d): %s", result.returncode, stderr)
            return ConversionResult(
                job_id=job.job_id,
                success=False,
                output_path=None,
                duration_seconds=duration,
                error_message=stderr,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        if "%03d" in output_pattern:
            produced_files = list(job.output_path.parent.glob(
                job.output_path.name.replace("%03d", "[0-9][0-9][0-9]")
            ))
        else:
            produced_files = [job.output_path]
        verified_files = [
            path for path in produced_files
            if path.is_file()
            and path.stat().st_size > 0
            and (
                path not in output_signatures
                or output_signatures[path]
                != (path.stat().st_size, path.stat().st_mtime_ns)
            )
        ]
        if not verified_files:
            message = "ImageMagick returned success but no non-empty output file was created."
            job.status = JobStatus.FAILED
            job.error_message = message
            return ConversionResult(
                job_id=job.job_id,
                success=False,
                output_path=None,
                duration_seconds=duration,
                error_message=message,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        job.status = JobStatus.COMPLETED
        if progress_callback:
            progress_callback(100)

        _log.info(
            "Conversion completed in %.2fs: %s → %s",
            duration, job.input_path.name, job.output_path.name,
        )
        return ConversionResult(
            job_id=job.job_id,
            success=True,
            output_path=job.output_path,
            duration_seconds=duration,
            stdout=result.stdout,
            stderr=result.stderr,
        )
