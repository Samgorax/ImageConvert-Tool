"""
ui/workers/conversion_worker.py
================================
QThread worker that runs a ConversionJob on a background thread so the UI
never blocks during conversion (fixes audit bug B1).

Signals:
    progress(int)   0-100 percentage updates
    finished(obj)   ConversionResult on completion
    error(str)      human-readable error string on hard failure
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from core.exceptions import WorkstationError
from engine.imagemagick_adapter import ImageMagickAdapter
from engine.job import ConversionJob, ConversionResult

_log = logging.getLogger(__name__)


class ConversionWorker(QThread):
    """Executes a single ConversionJob off the main thread."""

    progress = Signal(int)      # 0-100
    finished = Signal(object)   # ConversionResult
    error    = Signal(str)      # error message

    def __init__(self, job: ConversionJob, adapter: ImageMagickAdapter) -> None:
        super().__init__()
        self._job     = job
        self._adapter = adapter

    def run(self) -> None:
        """Called by QThread.start() — runs on the worker thread."""
        _log.info(
            "Worker starting: %s → %s",
            self._job.input_format, self._job.output_format,
        )
        try:
            result: ConversionResult = self._adapter.convert(
                self._job,
                progress_callback=self.progress.emit,
            )
            self.finished.emit(result)
        except WorkstationError as exc:
            _log.error("WorkstationError in worker: %s", exc)
            self.error.emit(str(exc))
        except Exception as exc:
            _log.exception("Unexpected error in worker")
            self.error.emit(f"Unexpected error: {exc}")
