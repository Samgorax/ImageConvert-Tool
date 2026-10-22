"""Background worker for local document import, indexing, and Q&A."""
from __future__ import annotations

from threading import Event

from PySide6.QtCore import QThread, Signal

from documents.domain import AnswerResult, DocumentRecord
from documents.service import answer_question, index_document, ingest


class DocumentWorker(QThread):
    progress = Signal(str)
    document_ready = Signal(object)
    answer_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: str, **kwargs) -> None:
        super().__init__()
        self.operation = operation
        self.kwargs = kwargs
        self.cancel_event = Event()

    def cancel(self) -> None:
        self.cancel_event.set()
        self.requestInterruption()

    def run(self) -> None:
        try:
            if self.operation == "import":
                self.progress.emit("Extracting local document text…")
                result: DocumentRecord | AnswerResult = ingest(
                    self.kwargs["path"], self.cancel_event, policy=self.kwargs.get("policy")
                )
                self.document_ready.emit(result)
            elif self.operation == "index":
                self.progress.emit("Checking the configured local embedding model…")
                result = index_document(self.kwargs["document_id"], self.kwargs["model"], self.cancel_event,
                                        policy=self.kwargs.get("policy"))
                self.document_ready.emit(result)
            elif self.operation == "answer":
                self.progress.emit("Searching indexed local documents and asking the local model…")
                result = answer_question(**self.kwargs, cancel=self.cancel_event)
                self.answer_ready.emit(result)
            else:
                raise ValueError(f"Unknown document operation: {self.operation}")
        except Exception as exc:
            self.failed.emit(str(exc))
