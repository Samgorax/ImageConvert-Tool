"""
test_job.py
===========
Unit tests for engine.job dataclasses.
"""
from __future__ import annotations

from pathlib import Path

from engine.job import ConversionJob, ConversionOptions, ConversionResult, JobStatus


class TestConversionOptions:
    def test_defaults(self):
        opts = ConversionOptions()
        assert opts.quality       == 95
        assert opts.density       == 300
        assert opts.all_pages     is True
        assert opts.strip_metadata is False
        assert opts.flatten_alpha  is True

    def test_custom_values(self):
        opts = ConversionOptions(quality=60, density=72, all_pages=False)
        assert opts.quality   == 60
        assert opts.density   == 72
        assert opts.all_pages is False


class TestConversionJob:
    def _job(self, src="PNG", dst="JPG", **kw):
        return ConversionJob(
            input_path=Path("/in/file.png"),
            output_path=Path("/out/file.jpg"),
            input_format=src,
            output_format=dst,
            **kw,
        )

    def test_formats_normalised_to_uppercase(self):
        job = self._job(src="png", dst="pdf")
        assert job.input_format  == "PNG"
        assert job.output_format == "PDF"

    def test_is_same_format_true(self):
        job = self._job(src="PNG", dst="PNG")
        assert job.is_same_format is True

    def test_is_same_format_false(self):
        job = self._job(src="PNG", dst="PDF")
        assert job.is_same_format is False

    def test_default_status_is_queued(self):
        job = self._job()
        assert job.status == JobStatus.QUEUED

    def test_job_id_is_generated(self):
        job1 = self._job()
        job2 = self._job()
        assert job1.job_id != job2.job_id
        assert len(job1.job_id) == 36   # UUID4 format

    def test_created_at_is_set(self):
        job = self._job()
        assert job.created_at is not None

    def test_default_options_are_applied(self):
        job = self._job()
        assert job.options.quality == 95


class TestConversionResult:
    def test_success_result(self):
        r = ConversionResult(
            job_id="abc",
            success=True,
            output_path=Path("/out/file.jpg"),
            duration_seconds=1.5,
        )
        assert r.success is True
        assert r.error_message == ""

    def test_failure_result(self):
        r = ConversionResult(
            job_id="abc",
            success=False,
            output_path=None,
            duration_seconds=0.1,
            error_message="delegate error",
        )
        assert r.success is False
        assert r.output_path is None
        assert "delegate" in r.error_message
