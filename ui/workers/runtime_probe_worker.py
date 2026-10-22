"""Background discovery of locally installed model runtimes."""
from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from engine.model_runtime import probe_local_model_runtimes

_log = logging.getLogger(__name__)


class RuntimeProbeWorker(QThread):
    inventory_ready = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.inventory_ready.emit(probe_local_model_runtimes())
        except Exception as exc:
            _log.exception("Local runtime discovery failed")
            self.failed.emit(str(exc))
