"""
test_imagemagick_adapter.py
============================
Unit tests for ``engine.imagemagick_adapter``.

Strategy:
- ``_build_args()`` is tested in isolation with a mocked ``executable`` path.
- ``convert()`` is tested with a mocked ``subprocess.run`` so no real
  ImageMagick installation is required.
- All flag combinations validated here must also be covered by the legacy
  baseline in test_legacy_behavior.py.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.exceptions import (
    ConversionError,
    InputFileError,
    PathTraversalError,
    ToolNotFoundError,
)
from engine.imagemagick_adapter import ImageMagickAdapter, _validate_path
from engine.job import ConversionJob, ConversionOptions, JobStatus

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_adapter(available: bool = True, exe: str = "magick") -> ImageMagickAdapter:
    """Return an adapter with a mocked health-check result."""
    tool_info = MagicMock()
    tool_info.found   = available
    tool_info.path    = exe
    tool_info.version = "ImageMagick 7.x.x"
    adapter = ImageMagickAdapter.__new__(ImageMagickAdapter)
    adapter._tool = tool_info
    return adapter


def make_job(
    src_format: str = "PNG",
    dst_format: str = "JPG",
    tmp_path: Path | None = None,
    **option_kwargs,
) -> ConversionJob:
    base = tmp_path or Path("/tmp/test")
    opts = ConversionOptions(**option_kwargs)
    return ConversionJob(
        input_path=base / f"input.{src_format.lower()}",
        output_path=base / f"output.{dst_format.lower()}",
        input_format=src_format,
        output_format=dst_format,
        options=opts,
    )


# ── _validate_path ─────────────────────────────────────────────────────────────

class TestValidatePath:
    def test_valid_child_path_accepted(self, tmp_path):
        p = tmp_path / "output.png"
        result = _validate_path(p, base=tmp_path)
        assert result == p.resolve()

    def test_traversal_rejected(self, tmp_path):
        evil = tmp_path / "a" / ".." / ".." / "etc" / "shadow"
        with pytest.raises(PathTraversalError):
            _validate_path(evil, base=tmp_path)

    def test_no_base_always_accepted(self, tmp_path):
        p = tmp_path / "anywhere.png"
        result = _validate_path(p, base=None)
        assert result == p.resolve()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows paths only")
    def test_absolute_outside_base_rejected_windows(self, tmp_path):
        outside = Path(r"C:\Windows\System32\evil.exe")
        with pytest.raises(PathTraversalError):
            _validate_path(outside, base=tmp_path)


# ── _build_args ────────────────────────────────────────────────────────────────

class TestBuildArgs:
    """
    Validates that _build_args() produces the correct flag sequence.
    Each case corresponds to a test in test_legacy_behavior.py.
    """

    def _args(self, adapter, job) -> list[str]:
        return adapter._build_args(job)

    def test_executable_is_first_arg(self, tmp_path):
        adapter = make_adapter(exe="magick")
        job = make_job("PNG", "BMP", tmp_path)
        assert self._args(adapter, job)[0] == "magick"

    def test_png_to_jpg_has_alpha_remove(self, tmp_path):
        adapter = make_adapter()
        job = make_job("PNG", "JPG", tmp_path)
        args = self._args(adapter, job)
        assert "-alpha" in args
        assert "remove" in args

    def test_png_to_jpg_has_alpha_off(self, tmp_path):
        adapter = make_adapter()
        job = make_job("PNG", "JPG", tmp_path)
        args = self._args(adapter, job)
        idx = args.index("-alpha")
        # Second alpha pair must be "off"
        second_idx = args.index("-alpha", idx + 1)
        assert args[second_idx + 1] == "off"

    def test_png_to_jpg_has_white_background(self, tmp_path):
        adapter = make_adapter()
        job = make_job("PNG", "JPG", tmp_path)
        args = self._args(adapter, job)
        assert "-background" in args
        assert "white" in args

    def test_lossy_output_has_quality_flag(self, tmp_path):
        for fmt in ("JPG", "JPEG", "WEBP", "AVIF", "HEIC"):
            adapter = make_adapter()
            job = make_job("PNG", fmt, tmp_path, quality=80)
            args = self._args(adapter, job)
            assert "-quality" in args, f"Missing -quality for {fmt}"
            qi = args.index("-quality")
            assert args[qi + 1] == "80", f"Wrong quality value for {fmt}"

    def test_non_lossy_output_no_quality(self, tmp_path):
        for fmt in ("TIFF", "BMP", "PNG", "GIF"):
            adapter = make_adapter()
            job = make_job("JPG", fmt, tmp_path)
            args = self._args(adapter, job)
            assert "-quality" not in args, f"Unexpected -quality for {fmt}"

    def test_vector_source_has_density(self, tmp_path):
        for fmt in ("PDF", "PS", "EPS"):
            adapter = make_adapter()
            job = make_job(fmt, "PNG", tmp_path, density=150)
            args = self._args(adapter, job)
            assert "-density" in args, f"Missing -density for {fmt}"
            di = args.index("-density")
            assert args[di + 1] == "150"

    def test_density_precedes_input_file(self, tmp_path):
        adapter = make_adapter()
        job = make_job("PDF", "PNG", tmp_path)
        args = self._args(adapter, job)
        density_idx = args.index("-density")
        # Input file path contains "input"
        input_idx = next(i for i, a in enumerate(args) if "input" in a.lower())
        assert density_idx < input_idx

    def test_raster_source_no_density(self, tmp_path):
        for fmt in ("PNG", "JPG", "BMP"):
            adapter = make_adapter()
            job = make_job(fmt, "PDF", tmp_path)
            args = self._args(adapter, job)
            assert "-density" not in args, f"Unexpected -density for {fmt}"

    def test_strip_metadata_flag(self, tmp_path):
        adapter = make_adapter()
        job = make_job("PNG", "JPG", tmp_path, strip_metadata=True)
        assert "-strip" in self._args(adapter, job)

    def test_no_strip_by_default(self, tmp_path):
        adapter = make_adapter()
        job = make_job("PNG", "JPG", tmp_path)
        assert "-strip" not in self._args(adapter, job)

    def test_webp_to_jpg_no_alpha_flags(self, tmp_path):
        # WEBP has transparency but the flag only fires for PNG→JPG in legacy
        # The new adapter fires on any transparent→non-transparent conversion
        adapter = make_adapter()
        job = make_job("WEBP", "JPG", tmp_path, flatten_alpha=True)
        args = self._args(adapter, job)
        # WEBP is in TRANSPARENT_FORMATS, JPG is not → alpha flags ARE expected
        assert "-alpha" in args   # new adapter is more correct than legacy

    def test_flatten_alpha_false_skips_flags(self, tmp_path):
        adapter = make_adapter()
        job = make_job("PNG", "JPG", tmp_path, flatten_alpha=False)
        args = self._args(adapter, job)
        assert "-alpha" not in args


# ── _resolve_output_path ───────────────────────────────────────────────────────

class TestResolveOutputPath:
    def test_non_multipage_source_no_pattern(self, tmp_path):
        adapter = make_adapter()
        job = make_job("PNG", "BMP", tmp_path)
        resolved = adapter._resolve_output_path(job)
        assert "%03d" not in str(resolved)

    def test_pdf_multipage_on_has_pattern(self, tmp_path):
        adapter = make_adapter()
        job = make_job("PDF", "PNG", tmp_path, all_pages=True)
        resolved = adapter._resolve_output_path(job)
        assert "%03d" in str(resolved)

    def test_gif_multipage_on_has_pattern(self, tmp_path):
        adapter = make_adapter()
        job = make_job("GIF", "PNG", tmp_path, all_pages=True)
        resolved = adapter._resolve_output_path(job)
        assert "%03d" in str(resolved)

    def test_multipage_off_no_pattern(self, tmp_path):
        adapter = make_adapter()
        job = make_job("PDF", "PNG", tmp_path, all_pages=False)
        resolved = adapter._resolve_output_path(job)
        assert "%03d" not in str(resolved)


# ── convert() — mocked subprocess ─────────────────────────────────────────────

class TestConvert:
    def _run_convert(self, adapter, job, returncode=0, stderr="", stdout=""):
        mock_result = MagicMock()
        mock_result.returncode = returncode
        mock_result.stderr     = stderr
        mock_result.stdout     = stdout

        def run_and_write_output(*_args, **_kwargs):
            if returncode == 0:
                output = job.output_path
                if "%03d" in output.name:
                    output = output.with_name(output.name.replace("%03d", "000"))
                output.write_bytes(b"verified conversion output")
            return mock_result

        with patch("engine.imagemagick_adapter.subprocess.run", side_effect=run_and_write_output):
            return adapter.convert(job)

    def test_successful_conversion_returns_success_true(self, tmp_path, sample_png):
        adapter = make_adapter()
        job = ConversionJob(
            input_path=sample_png,
            output_path=tmp_path / "output.jpg",
            input_format="PNG",
            output_format="JPG",
        )
        result = self._run_convert(adapter, job)
        assert result.success is True

    def test_successful_conversion_updates_job_status(self, tmp_path, sample_png):
        adapter = make_adapter()
        job = ConversionJob(
            input_path=sample_png,
            output_path=tmp_path / "output.bmp",
            input_format="PNG",
            output_format="BMP",
        )
        self._run_convert(adapter, job)
        assert job.status == JobStatus.COMPLETED

    def test_failed_conversion_returns_success_false(self, tmp_path, sample_png):
        adapter = make_adapter()
        job = ConversionJob(
            input_path=sample_png,
            output_path=tmp_path / "output.jpg",
            input_format="PNG",
            output_format="JPG",
        )
        result = self._run_convert(adapter, job, returncode=1, stderr="delegate error")
        assert result.success is False
        assert "delegate error" in result.error_message

    def test_failed_conversion_sets_job_status_failed(self, tmp_path, sample_png):
        adapter = make_adapter()
        job = ConversionJob(
            input_path=sample_png,
            output_path=tmp_path / "output.jpg",
            input_format="PNG",
            output_format="JPG",
        )
        self._run_convert(adapter, job, returncode=1, stderr="oops")
        assert job.status == JobStatus.FAILED

    def test_missing_input_file_raises(self, tmp_path):
        adapter = make_adapter()
        job = ConversionJob(
            input_path=tmp_path / "nonexistent.png",
            output_path=tmp_path / "out.jpg",
            input_format="PNG",
            output_format="JPG",
        )
        with pytest.raises(InputFileError):
            adapter.convert(job)

    def test_same_format_raises_conversion_error(self, tmp_path, sample_png):
        adapter = make_adapter()
        job = ConversionJob(
            input_path=sample_png,
            output_path=tmp_path / "out.png",
            input_format="PNG",
            output_format="PNG",
        )
        with pytest.raises(ConversionError):
            adapter.convert(job)

    def test_unavailable_adapter_raises_tool_not_found(self, tmp_path, sample_png):
        adapter = make_adapter(available=False)
        job = ConversionJob(
            input_path=sample_png,
            output_path=tmp_path / "out.jpg",
            input_format="PNG",
            output_format="JPG",
        )
        with pytest.raises(ToolNotFoundError):
            adapter.convert(job)

    def test_progress_callback_is_called(self, tmp_path, sample_png):
        adapter = make_adapter()
        job = ConversionJob(
            input_path=sample_png,
            output_path=tmp_path / "out.bmp",
            input_format="PNG",
            output_format="BMP",
        )
        progress_values: list[int] = []
        self._run_convert(adapter, job)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = mock_result.stdout = ""

        def run_and_write_output(*_args, **_kwargs):
            job.output_path.write_bytes(b"verified conversion output")
            return mock_result

        with patch("engine.imagemagick_adapter.subprocess.run", side_effect=run_and_write_output):
            adapter.convert(job, progress_callback=progress_values.append)

        assert any(v > 0 for v in progress_values)
        assert 100 in progress_values

    def test_zero_exit_without_output_is_failure(self, tmp_path, sample_png):
        adapter = make_adapter()
        job = ConversionJob(
            input_path=sample_png,
            output_path=tmp_path / "missing.bmp",
            input_format="PNG",
            output_format="BMP",
        )
        mock_result = MagicMock(returncode=0, stderr="", stdout="")
        with patch("engine.imagemagick_adapter.subprocess.run", return_value=mock_result):
            result = adapter.convert(job)
        assert result.success is False
        assert job.status == JobStatus.FAILED
        assert "no non-empty output" in result.error_message

    def test_existing_unchanged_output_does_not_count_as_new_success(
        self, tmp_path, sample_png
    ):
        adapter = make_adapter()
        output = tmp_path / "existing.bmp"
        output.write_bytes(b"older output")
        job = ConversionJob(
            input_path=sample_png,
            output_path=output,
            input_format="PNG",
            output_format="BMP",
        )
        mock_result = MagicMock(returncode=0, stderr="", stdout="")
        with patch("engine.imagemagick_adapter.subprocess.run", return_value=mock_result):
            result = adapter.convert(job)
        assert result.success is False
        assert job.status == JobStatus.FAILED

    def test_timeout_raises_conversion_timeout_error(self, tmp_path, sample_png):
        from core.exceptions import ConversionTimeoutError
        adapter = make_adapter()
        job = ConversionJob(
            input_path=sample_png,
            output_path=tmp_path / "out.jpg",
            input_format="PNG",
            output_format="JPG",
        )
        with patch(
            "engine.imagemagick_adapter.subprocess.run",
            side_effect=__import__("subprocess").TimeoutExpired(cmd="magick", timeout=600),
        ):
            with pytest.raises(ConversionTimeoutError):
                adapter.convert(job)
