"""Background startup discovery of required conversion tools."""
from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from engine.health_check import run_health_check

_log = logging.getLogger(__name__)


class HealthCheckWorker(QThread):
    health_ready = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.health_ready.emit(run_health_check())
        except Exception as exc:
            _log.exception("External tool health discovery failed")
            self.failed.emit(str(exc))
