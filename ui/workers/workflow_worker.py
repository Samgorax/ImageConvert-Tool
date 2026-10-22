"""Background worker for local workflow planning and approved tool execution."""
from __future__ import annotations

from threading import Event
from typing import Any

from PySide6.QtCore import QThread, Signal

from workflows.service import approve_step, create_workflow


class WorkflowWorker(QThread):
    workflow_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: str, **kwargs: Any) -> None:
        super().__init__()
        self.operation = operation
        self.kwargs = kwargs
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            if self.operation == "plan":
                result = create_workflow(**self.kwargs, cancel=self.cancel_event)
            elif self.operation == "approve":
                result = approve_step(**self.kwargs, cancel=self.cancel_event)
            else:
                raise ValueError(f"Unsupported workflow worker operation: {self.operation}")
            self.workflow_ready.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
