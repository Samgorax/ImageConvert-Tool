"""Workbench pages that surface only locally available application state."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config import APP_DATA_DIR, DB_PATH, REPO_ROOT
from documents.domain import AnswerResult, DocumentRecord, DocumentStatus
from documents.service import remove_document_index
from engine.health_check import HealthReport
from engine.model_runtime import RuntimeInventory
from permissions.policy import PermissionPolicy
from storage import document_repository, job_repository, settings_repository
from ui.workers.document_worker import DocumentWorker


def _card(title: str, body: str = "") -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setObjectName("workbench_card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    heading = QLabel(title)
    heading.setObjectName("card_heading")
    detail = QLabel(body)
    detail.setObjectName("card_detail")
    detail.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(detail)
    return frame, detail


def _page_layout(page: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(page)
    layout.setContentsMargins(22, 18, 22, 20)
    layout.setSpacing(14)
    return layout


class DashboardPage(QWidget):
    _ACTIONS = (
        ("conversion", "Open Conversion", "Convert images and documents"),
        ("task_history", "Task History", "Review saved conversion jobs"),
        ("model_manager", "Model Manager", "Check local runtime inventory"),
        ("settings", "Settings", "Manage preferences and data paths"),
    )

    def __init__(
        self,
        health: HealthReport,
        parent: QWidget | None = None,
        navigate_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.health = health
        self.runtime_inventory: RuntimeInventory | None = None
        self._navigate_callback = navigate_callback or (lambda _key: None)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("dashboard_scroll")
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.viewport().installEventFilter(self)
        content = QWidget()
        content.setObjectName("dashboard_content")
        self._layout = _page_layout(content)
        self.scroll_area.setWidget(content)
        root_layout.addWidget(self.scroll_area)

        hero = QFrame()
        hero.setObjectName("dashboard_hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(20, 16, 20, 16)
        hero_layout.setSpacing(5)
        hero_title = QLabel("Your local workbench")
        hero_title.setObjectName("dashboard_hero_title")
        hero_detail = QLabel(
            "A clear view of conversion tools, local runtime discovery, saved jobs, and application policy."
        )
        hero_detail.setObjectName("dashboard_hero_detail")
        hero_detail.setWordWrap(True)
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_detail)
        self._layout.addWidget(hero)

        self.status_grid = QGridLayout()
        self.status_grid.setSpacing(12)
        self.status_cards: list[QFrame] = []
        self.image_status_card, self.image_status, self.image_detail = self._make_status_card(
            "ImageMagick", "Checking…", "Image conversion engine"
        )
        self.ghostscript_card, self.ghostscript_status, self.ghostscript_detail = self._make_status_card(
            "Ghostscript", "Checking…", "PDF and PostScript support"
        )
        self.runtime_card, self.runtime_status, self.runtime_detail = self._make_status_card(
            "Local model runtime", "Checking…", "Discovery does not load or run a model."
        )
        self.ai_card, self.ai_status, self.ai_detail = self._make_status_card(
            "Document Q&A readiness", "Checking…", "Runtime inventory and saved configuration are checked separately."
        )
        policy = PermissionPolicy.default()
        network_state = "Enabled" if policy.allow_network_access else "Disabled"
        self.privacy_card, self.privacy_status, self.privacy_detail = self._make_status_card(
            "Application network policy",
            f"Remote access {network_state.lower()}",
            "Local model requests use loopback only after you submit an action. No cloud AI provider is integrated; app policy does not control system-wide networking.",
        )
        self.status_cards.extend(
            [self.image_status_card, self.ghostscript_card, self.runtime_card, self.ai_card, self.privacy_card]
        )
        self._layout.addLayout(self.status_grid)

        self.details_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.details_layout.setSpacing(12)
        self.recent_card = self._build_recent_card()
        self.quick_actions_card = self._build_quick_actions_card()
        self.details_layout.addWidget(self.recent_card, 3)
        self.details_layout.addWidget(self.quick_actions_card, 2)
        self._layout.addLayout(self.details_layout, 1)
        self._arrange_responsive(width=0)
        self.set_health_report(health)
        self.refresh()

    @staticmethod
    def _make_status_card(title: str, value: str, detail: str) -> tuple[QFrame, QLabel, QLabel]:
        frame = QFrame()
        frame.setObjectName("dashboard_status_card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 13, 15, 13)
        layout.setSpacing(5)
        heading = QLabel(title)
        heading.setObjectName("dashboard_card_heading")
        heading.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        status = QLabel(value)
        status.setObjectName("dashboard_status_value")
        status.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        status.setWordWrap(True)
        description = QLabel(detail)
        description.setObjectName("dashboard_status_detail")
        description.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        description.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(status)
        layout.addWidget(description)
        return frame, status, description

    def _build_recent_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("workbench_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)
        title = QLabel("Recent conversions")
        title.setObjectName("dashboard_section_title")
        title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout.addWidget(title)
        self.recent_job_rows = QVBoxLayout()
        self.recent_job_rows.setSpacing(7)
        layout.addLayout(self.recent_job_rows)
        self.recent_jobs = QLabel("Loading saved task history…")
        self.recent_jobs.setObjectName("dashboard_status_detail")
        self.recent_jobs.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.recent_jobs.setWordWrap(True)
        self.recent_job_rows.addWidget(self.recent_jobs)
        return card

    def _build_quick_actions_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("workbench_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(9)
        title = QLabel("Quick actions")
        title.setObjectName("dashboard_section_title")
        title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout.addWidget(title)
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        self.quick_action_buttons: dict[str, QPushButton] = {}
        for index, (page_key, label, description) in enumerate(self._ACTIONS):
            button = QPushButton(f"{label}\n{description}")
            button.setObjectName("dashboard_action")
            button.setMinimumHeight(66)
            button.setAccessibleName(label)
            button.setAccessibleDescription(description)
            button.clicked.connect(
                lambda checked=False, target=page_key: self._navigate_callback(target)
            )
            self.quick_action_buttons[page_key] = button
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)
        return card

    def _arrange_responsive(self, width: int) -> None:
        columns = 4 if width >= 1080 else 2
        self.status_columns = columns
        while self.status_grid.count():
            self.status_grid.takeAt(0)
        for index, card in enumerate(self.status_cards):
            self.status_grid.addWidget(card, index // columns, index % columns)
        for column in range(4):
            self.status_grid.setColumnStretch(column, int(column < columns))
        direction = (
            QBoxLayout.Direction.LeftToRight if width >= 1080 else QBoxLayout.Direction.TopToBottom
        )
        self.details_layout.setDirection(direction)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().resizeEvent(event)
        self._arrange_responsive(self.scroll_area.viewport().width())

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().showEvent(event)
        self._arrange_responsive(self.scroll_area.viewport().width())

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API name
        if watched is self.scroll_area.viewport() and event.type() == QEvent.Type.Resize:
            self._arrange_responsive(event.size().width())
        return super().eventFilter(watched, event)

    def set_health_pending(self) -> None:
        self.image_status.setText("Checking availability…")
        self.image_detail.setText("ImageMagick health check is running.")
        self.ghostscript_status.setText("Checking availability…")
        self.ghostscript_detail.setText("Ghostscript health check is running.")

    def set_health_report(self, health: HealthReport) -> None:
        self.health = health
        for status, detail, tool, description in (
            (self.image_status, self.image_detail, health.imagemagick, "Image conversion engine"),
            (self.ghostscript_status, self.ghostscript_detail, health.ghostscript, "PDF and PostScript support"),
        ):
            if tool.found:
                status.setText("Detected")
                detail.setText(tool.version or tool.path or description)
            else:
                status.setText("Not detected")
                detail.setText(tool.notes or description)

    def set_health_error(self, message: str) -> None:
        self.image_status.setText("Health check failed")
        self.image_detail.setText(message)
        self.ghostscript_status.setText("Health check failed")
        self.ghostscript_detail.setText(message)

    def set_runtime_inventory(self, inventory: RuntimeInventory) -> None:
        self.runtime_inventory = inventory
        found = [runtime for runtime in inventory.runtimes if runtime.available]
        if not found:
            self.runtime_status.setText("No supported runtime detected")
            self.runtime_detail.setText("No local model runtime was found on PATH.")
            return
        names = ", ".join(runtime.name for runtime in found)
        self.runtime_status.setText(f"Detected · {names}")
        model_counts = [len(runtime.models) for runtime in found if runtime.inventory_supported]
        if model_counts:
            count = sum(model_counts)
            model_text = f"{count} installed model(s) listed locally" if count else "No installed models listed"
        else:
            model_text = "Installed model inventory is unavailable for this runtime"
        self.runtime_detail.setText(f"{model_text}. Discovery does not load or invoke a model.")

    def set_runtime_error(self, message: str) -> None:
        self.runtime_status.setText("Runtime discovery failed")
        self.runtime_detail.setText(message)

    def set_ai_readiness(self, status: str, detail: str) -> None:
        self.ai_status.setText(status)
        self.ai_detail.setText(detail)

    def _clear_recent_rows(self) -> None:
        while self.recent_job_rows.count():
            item = self.recent_job_rows.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
            if widget is self.recent_jobs:
                widget.hide()
            else:
                widget.deleteLater()

    def refresh(self) -> None:
        self._clear_recent_rows()
        try:
            jobs = job_repository.list_jobs(limit=4)
        except Exception as exc:
            self.recent_jobs.setText(f"Saved task history is unavailable: {exc}")
            self.recent_jobs.show()
            self.recent_job_rows.addWidget(self.recent_jobs, 1)
            return
        if not jobs:
            self.recent_jobs.setText("No saved conversion tasks yet.")
            self.recent_jobs.show()
            self.recent_job_rows.addWidget(self.recent_jobs, 1)
            return
        self.recent_jobs.hide()
        for job in jobs:
            row = QFrame()
            row.setObjectName("dashboard_recent_row")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(11, 8, 11, 8)
            row_layout.setSpacing(12)
            text_layout = QVBoxLayout()
            text_layout.setSpacing(3)
            name = QLabel(Path(job["input_path"]).name or str(job["input_path"]))
            name.setObjectName("dashboard_recent_name")
            name.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            detail = QLabel(
                f"{job['input_format']} → {job['output_format']}  ·  {job['created_at']}"
            )
            detail.setObjectName("dashboard_recent_detail")
            detail.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            detail.setWordWrap(True)
            detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            text_layout.addWidget(name)
            text_layout.addWidget(detail)
            status = QLabel(str(job["status"]))
            status.setObjectName("dashboard_card_heading")
            status.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
            status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addLayout(text_layout, 1)
            row_layout.addWidget(status)
            self.recent_job_rows.addWidget(row, 1)


class AIWorkspacePage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = _page_layout(self)
        self._worker: DocumentWorker | None = None
        self._runtime_inventory: RuntimeInventory | None = None
        self._runtime_error = ""
        card = QFrame()
        card.setObjectName("workbench_card")
        form = QVBoxLayout(card)
        form.setContentsMargins(18, 16, 18, 16)
        form.setSpacing(10)
        heading = QLabel("Document-grounded local Q&A")
        heading.setObjectName("card_heading")
        detail = QLabel("Answers use only selected indexed documents and an explicitly configured loopback Ollama model. Agentic workflows and scanned-PDF OCR are not implemented.")
        detail.setObjectName("card_detail")
        detail.setWordWrap(True)
        self.document_selector = QComboBox()
        self.document_selector.setAccessibleName("Indexed documents for question answering")
        self.document_selector.setMinimumHeight(38)
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("Ask a question about selected documents…")
        self.question_input.setAccessibleName("Question")
        self.allow_document_access = QCheckBox("I allow local retrieval from the selected document for this session")
        self.allow_ai_answers = QCheckBox("Allow the configured local model to generate an answer this session")
        self.chat_model_input = QLineEdit(settings_repository.get("local_chat_model"))
        self.chat_model_input.setPlaceholderText("Installed local chat model name")
        self.chat_model_input.setAccessibleName("Local chat model")
        self.embedding_model_input = QLineEdit(settings_repository.get("local_embedding_model"))
        self.embedding_model_input.setPlaceholderText("Installed local embedding model name (separate from chat)")
        self.embedding_model_input.setAccessibleName("Local embedding model")
        self.ask_button = QPushButton("Ask selected documents")
        self.ask_button.setObjectName("primary_button")
        self.ask_button.clicked.connect(self.ask)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        self.answer_output = QTextEdit()
        self.answer_output.setReadOnly(True)
        self.answer_output.setMinimumHeight(180)
        self.answer_output.setAccessibleName("Answer")
        self.citations = QTableWidget(0, 3)
        self.citations.setColumnCount(4)
        self.citations.setHorizontalHeaderLabels(["Source", "Location", "Evidence excerpt", "Similarity"])
        self.citations.horizontalHeader().setStretchLastSection(True)
        self.citations.setMaximumHeight(150)
        self.status = QLabel("Configure a separately installed embedding model and chat model. No cloud fallback is available.")
        self.status.setObjectName("muted_text")
        self.status.setWordWrap(True)
        for widget in (heading, detail, self.document_selector, self.allow_document_access, self.allow_ai_answers,
                       self.embedding_model_input,
                       self.chat_model_input, self.question_input, self.ask_button, self.cancel_button, self.status,
                       self.answer_output, self.citations):
            form.addWidget(widget)
        layout.addWidget(card)
        layout.addStretch(1)
        self.refresh_documents()
        self._update_availability()

    def set_runtime_pending(self) -> None:
        self._runtime_inventory = None
        self._runtime_error = ""
        self._installed_models = ()
        self._update_availability()
        self.question_input.textChanged.connect(self._update_availability)
        self.document_selector.currentIndexChanged.connect(self._update_availability)
        self.allow_document_access.toggled.connect(self._update_availability)
        self.allow_ai_answers.toggled.connect(self._update_availability)
        self.embedding_model_input.textChanged.connect(self._update_availability)
        self.chat_model_input.textChanged.connect(self._update_availability)

    def set_runtime_inventory(self, inventory: RuntimeInventory) -> None:
        self._runtime_inventory = inventory
        self._runtime_error = ""
        models = [model for runtime in inventory.runtimes if runtime.name == "Ollama" and runtime.available
                  for model in runtime.models]
        self._installed_models = tuple(models)
        if models and not self.chat_model_input.text().strip():
            self.chat_model_input.setPlaceholderText(f"Installed local chat model (e.g. {models[0]})")
        if models and self.embedding_model_input.text().strip() in models:
            self.status.setText("Configured model is installed; embedding capability is still verified separately before indexing.")
        self._update_availability()

    def set_runtime_error(self, message: str) -> None:
        self._runtime_error = message
        self._update_availability()

    def refresh_preferences(self) -> None:
        try:
            self.chat_model_input.setText(settings_repository.get("local_chat_model"))
            self.embedding_model_input.setText(settings_repository.get("local_embedding_model"))
            self.refresh_documents()
        except Exception as exc:
            self.status.setText(f"Could not load saved model preferences: {exc}")
            self.ask_button.setEnabled(False)

    def refresh_documents(self) -> None:
        selected_id = self.document_selector.currentData()
        self.document_selector.clear()
        try:
            records = document_repository.list_documents()
        except Exception as exc:
            self.document_selector.clear()
            self.status.setText(f"Local document index unavailable: {exc}")
            self._update_availability()
            return
        for record in records:
            if record.status == DocumentStatus.INDEXED:
                self.document_selector.addItem(record.filename, record.document_id)
        if selected_id:
            index = self.document_selector.findData(selected_id)
            if index >= 0:
                self.document_selector.setCurrentIndex(index)
        if not records:
            self.status.setText("No documents have been imported. Add and index files in Documents.")
        elif not self.document_selector.count():
            self.status.setText("Imported documents are not indexed yet. Open Documents and index one with an installed embedding model.")
        self._update_availability()

    def _update_availability(self) -> None:
        if self._worker and self._worker.isRunning():
            self.ask_button.setEnabled(False)
            return
        runtime = next((item for item in self._runtime_inventory.runtimes if item.name == "Ollama"), None) if self._runtime_inventory else None
        models = getattr(self, "_installed_models", ())

        def installed(name: str) -> bool:
            return name in models or (":" not in name and f"{name}:latest" in models)

        try:
            requirements = (
                (not self._runtime_error and runtime is not None and runtime.available,
                 (self._runtime_error or (runtime.message if runtime else "Waiting for local Ollama inventory. Open Model Manager and refresh."))),
                (bool(self.document_selector.count()), "Import and index a document in Documents first."),
                (bool(self.embedding_model_input.text().strip()), "Enter an installed embedding model, such as nomic-embed-text:latest."),
                (bool(self.chat_model_input.text().strip()), "Enter an installed local chat model, such as phi3:latest."),
                (installed(self.embedding_model_input.text().strip()), "The configured embedding model is not listed by local Ollama."),
                (installed(self.chat_model_input.text().strip()), "The configured chat model is not listed by local Ollama."),
                (settings_repository.get_bool("policy_allow_document_access"), "Enable document access in Settings, then confirm it for this session."),
                (settings_repository.get_bool("policy_allow_ai_suggestions"), "Enable local AI answers in Settings, then confirm them for this session."),
                (self.allow_document_access.isChecked(), "Confirm local document access for this session."),
                (self.allow_ai_answers.isChecked(), "Confirm local AI answers for this session."),
                (bool(self.question_input.text().strip()), "Enter a question about the selected document."),
            )
        except Exception as exc:
            self.status.setText(f"Preferences unavailable: {exc}")
            self.ask_button.setEnabled(False)
            return
        reason = next((message for ready, message in requirements if not ready), "Ready to query selected local documents.")
        self.status.setText(reason)
        self.ask_button.setEnabled(reason == "Ready to query selected local documents.")

    def ask(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        ids = (self.document_selector.currentData(),) if self.document_selector.currentData() else ()
        if not ids:
            self.status.setText("Select at least one indexed document.")
            return
        if not self.allow_document_access.isChecked():
            self.status.setText("Enable local document access for this session before asking a question.")
            return
        if not settings_repository.get_bool("policy_allow_document_access"):
            self.status.setText("Enable document access in Settings before confirming it for this session.")
            return
        if not self.allow_ai_answers.isChecked():
            self.status.setText("Enable local AI answers for this session before asking a question.")
            return
        if not settings_repository.get_bool("policy_allow_ai_suggestions"):
            self.status.setText("Enable local AI answers in Settings before confirming them for this session.")
            return
        try:
            settings_repository.set_value("local_chat_model", self.chat_model_input.text().strip())
            settings_repository.set_value("local_embedding_model", self.embedding_model_input.text().strip())
        except Exception as exc:
            self.status.setText(f"Could not save local model preferences: {exc}")
            return
        self._worker = DocumentWorker(
            "answer", question=self.question_input.text(), document_ids=ids,
            embedding_model=self.embedding_model_input.text().strip(), chat_model=self.chat_model_input.text().strip(),
            policy=PermissionPolicy(allow_document_access=True, allow_ai_suggestions=True),
        )
        self._worker.progress.connect(self.status.setText)
        self._worker.answer_ready.connect(self._show_answer)
        self._worker.failed.connect(lambda message: self.status.setText(f"Local Q&A failed: {message}"))
        self._worker.finished.connect(self._worker_finished)
        self.ask_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self._worker.start()

    def cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.status.setText("Cancellation requested. Waiting for the local request to return…")

    def _show_answer(self, result: AnswerResult) -> None:
        self.refresh_documents()
        self.answer_output.setPlainText(result.answer)
        self.citations.setRowCount(0)
        for hit in result.citations:
            row = self.citations.rowCount()
            self.citations.insertRow(row)
            self.citations.setItem(row, 0, QTableWidgetItem(hit.filename))
            self.citations.setItem(row, 1, QTableWidgetItem(f"Page {hit.page_number}" if hit.page_number else (hit.section or "Text")))
            excerpt = QTableWidgetItem(hit.text)
            excerpt.setToolTip(hit.text)
            self.citations.setItem(row, 2, excerpt)
            self.citations.setItem(row, 3, QTableWidgetItem(f"{hit.cosine_similarity:.3f}"))
        self.status.setText("Insufficient evidence in selected documents; the chat model was not called." if result.insufficient_evidence else
                            f"Answer generated locally with {result.model}. Citations identify retrieved source chunks.")

    def _worker_finished(self) -> None:
        self._worker = None
        self.cancel_button.setEnabled(False)
        self._update_availability()

    def has_running_workers(self) -> bool:
        return bool(self._worker and self._worker.isRunning())


class DocumentsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = _page_layout(self)
        self._worker: DocumentWorker | None = None
        self._pending_paths: list[str] = []
        card = QFrame()
        card.setObjectName("workbench_card")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(18, 16, 18, 16)
        inner.setSpacing(10)
        title = QLabel("Local document library")
        title.setObjectName("card_heading")
        info = QLabel("PDF text, DOCX, TXT, and Markdown are extracted locally. Scanned PDF OCR is not available yet and requires a separately configured local tool.")
        info.setObjectName("card_detail")
        info.setWordWrap(True)
        actions = QHBoxLayout()
        self.import_button = QPushButton("Import documents")
        self.import_button.setObjectName("primary_button")
        self.import_button.clicked.connect(self.import_files)
        self.allow_document_access = QCheckBox("I authorize local document import, indexing, search, and index removal this session")
        self.embedding_model = QLineEdit(settings_repository.get("local_embedding_model"))
        self.embedding_model.setPlaceholderText("Installed local embedding model (separate from chat model)")
        self.embedding_model.setAccessibleName("Local embedding model")
        self.index_button = QPushButton("Index selected")
        self.index_button.clicked.connect(self.index_selected)
        self.remove_button = QPushButton("Remove index")
        self.remove_button.clicked.connect(self.remove_selected)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        for widget in (self.allow_document_access, self.import_button, QLabel("Embedding model"), self.embedding_model,
                       self.index_button, self.remove_button, self.cancel_button):
            actions.addWidget(widget)
        inner.addWidget(title)
        inner.addWidget(info)
        inner.addLayout(actions)
        self.status = QLabel("Document contents remain local. Removing an index preserves the original source file.")
        self.status.setObjectName("muted_text")
        self.status.setWordWrap(True)
        inner.addWidget(self.status)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Document", "Status", "Pages", "Chunks", "Details"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        inner.addWidget(self.table)
        layout.addWidget(card, 1)
        self.refresh_preferences()
        self.refresh_documents()

    def refresh_preferences(self) -> None:
        try:
            self.embedding_model.setText(settings_repository.get("local_embedding_model"))
        except Exception as exc:
            self.status.setText(f"Could not load the embedding model preference: {exc}")

    def import_files(self) -> None:
        if not self.allow_document_access.isChecked():
            self.status.setText("Enable document access for this session before importing files.")
            return
        if not settings_repository.get_bool("policy_allow_document_access"):
            self.status.setText("Enable document access in Settings before confirming it for this session.")
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Import local documents", "",
                                                "Documents (*.pdf *.docx *.txt *.md *.markdown)")
        if paths:
            self._pending_paths = paths
            self._start_next_import()

    def _start_next_import(self) -> None:
        if self._pending_paths:
            self._run_worker("import", path=self._pending_paths.pop(0), policy=self._document_policy())

    def _document_policy(self) -> PermissionPolicy:
        return PermissionPolicy(
            allow_document_access=(self.allow_document_access.isChecked()
                                   and settings_repository.get_bool("policy_allow_document_access"))
        )

    def _selected_id(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def index_selected(self) -> None:
        document_id = self._selected_id()
        model = self.embedding_model.text().strip()
        if not document_id:
            self.status.setText("Select an imported document first.")
            return
        if not self.allow_document_access.isChecked():
            self.status.setText("Enable document access for this session before indexing files.")
            return
        if not settings_repository.get_bool("policy_allow_document_access"):
            self.status.setText("Enable document access in Settings before confirming it for this session.")
            return
        if not model:
            self.status.setText("Enter the name of a separately installed local embedding model. No model will be downloaded.")
            return
        try:
            settings_repository.set_value("local_embedding_model", model)
        except Exception as exc:
            self.status.setText(f"Could not save the embedding model preference: {exc}")
            return
        self._run_worker("index", document_id=document_id, model=model, policy=self._document_policy())

    def remove_selected(self) -> None:
        document_id = self._selected_id()
        if not document_id:
            self.status.setText("Select a document index to remove.")
            return
        if not self.allow_document_access.isChecked():
            self.status.setText("Enable document access for this session before removing an index.")
            return
        if not settings_repository.get_bool("policy_allow_document_access"):
            self.status.setText("Enable document access in Settings before confirming it for this session.")
            return
        try:
            remove_document_index(document_id, policy=self._document_policy())
            self.status.setText("Index removed. The original source file was preserved.")
            self.refresh_documents()
        except Exception as exc:
            self.status.setText(f"Could not remove the local index: {exc}")

    def _run_worker(self, operation: str, **kwargs) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._worker = DocumentWorker(operation, **kwargs)
        self._worker.progress.connect(self.status.setText)
        self._worker.document_ready.connect(self._document_ready)
        self._worker.failed.connect(self._failed)
        self._worker.finished.connect(self._finished)
        self.cancel_button.setEnabled(True)
        for button in (self.import_button, self.index_button, self.remove_button):
            button.setEnabled(False)
        self._worker.start()

    def _document_ready(self, record: DocumentRecord) -> None:
        self.status.setText(f"{record.filename} extracted to the local index. Configure a separate embedding model to enable semantic retrieval.")
        self.refresh_documents()

    def _failed(self, message: str) -> None:
        self.status.setText(f"Document operation failed: {message}")
        self.refresh_documents()

    def _finished(self) -> None:
        self._worker = None
        self.cancel_button.setEnabled(False)
        if self._pending_paths:
            self._start_next_import()
            return
        for button in (self.import_button, self.index_button, self.remove_button):
            button.setEnabled(True)

    def cancel(self) -> None:
        self._pending_paths.clear()
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.status.setText("Cancellation requested. Waiting for the local operation to return…")

    def refresh_documents(self) -> None:
        try:
            records = document_repository.list_documents()
        except Exception as exc:
            self.table.setRowCount(0)
            self.status.setText(f"Local index unavailable: {exc}")
            return
        self.table.setRowCount(0)
        for record in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name = QTableWidgetItem(record.filename)
            name.setData(Qt.ItemDataRole.UserRole, record.document_id)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem(record.status.value))
            self.table.setItem(row, 2, QTableWidgetItem(str(record.page_count or "—")))
            self.table.setItem(row, 3, QTableWidgetItem(str(record.chunk_count)))
            detail = record.error_message or (f"{record.embedding_model} · {record.embedding_dimensions} dimensions" if record.embedding_model else "Awaiting local embedding model")
            self.table.setItem(row, 4, QTableWidgetItem(detail))

    def has_running_workers(self) -> bool:
        return bool(self._worker and self._worker.isRunning())


class ModelManagerPage(QWidget):
    def __init__(self, refresh_callback, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._refresh_callback = refresh_callback
        layout = _page_layout(self)
        top = QHBoxLayout()
        heading = QLabel("Installed local runtimes")
        heading.setObjectName("card_heading")
        top.addWidget(heading)
        top.addStretch(1)
        self.refresh_button = QPushButton("Refresh inventory")
        self.refresh_button.setObjectName("primary_button")
        self.refresh_button.clicked.connect(refresh_callback)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)

        self.status_label = QLabel("Checking local runtime availability…")
        self.status_label.setObjectName("muted_text")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Runtime", "Detected", "Models / inventory"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        note, note_detail = _card(
            "Model setup",
            "Model downloads and imports are user-controlled and are not performed by this screen.",
        )
        note_detail.setText(
            "Ollama model inventory is read through its local CLI when installed. llama.cpp does "
            "not provide a general installed-model catalog here; no model files are searched or "
            "loaded automatically."
        )
        layout.addWidget(note)

    def set_inventory(self, inventory: RuntimeInventory) -> None:
        self.table.setRowCount(0)
        for runtime in inventory.runtimes:
            row = self.table.rowCount()
            self.table.insertRow(row)
            detected = "Detected" if runtime.available else "Not detected"
            if runtime.available and runtime.version:
                detected += f" · {runtime.version}"
            if runtime.available and runtime.executable:
                detected += f"\n{runtime.executable}"
            if not runtime.available:
                inventory_text = runtime.message
            elif runtime.inventory_supported:
                inventory_text = ", ".join(runtime.models) if runtime.models else "No models listed"
                if runtime.message and runtime.message != "Local model inventory available.":
                    inventory_text += f" · {runtime.message}"
            else:
                inventory_text = runtime.message
            for column, value in enumerate((runtime.name, detected, inventory_text)):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, column, cell)
            self.table.setRowHeight(row, 58 if runtime.available else 42)
        found = sum(1 for runtime in inventory.runtimes if runtime.available)
        self.status_label.setText(
            f"{found} supported local runtime(s) detected. Discovery does not load a model."
        )

    def set_error(self, message: str) -> None:
        self.table.setRowCount(0)
        self.status_label.setText(f"Runtime discovery failed: {message}")


class TaskHistoryPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = _page_layout(self)
        top = QHBoxLayout()
        heading = QLabel("Saved conversion tasks")
        heading.setObjectName("card_heading")
        top.addWidget(heading)
        top.addStretch(1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)
        self.status_label = QLabel("")
        self.status_label.setObjectName("muted_text")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Input", "Output", "Formats", "Status", "Created"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        try:
            jobs = job_repository.list_jobs(limit=500)
        except Exception as exc:
            self.table.setRowCount(0)
            self.status_label.setText(f"Task history could not be loaded: {exc}")
            return
        self.table.setRowCount(len(jobs))
        self.status_label.setText(f"{len(jobs)} saved task(s).")
        for row, job in enumerate(jobs):
            values = (
                Path(job["input_path"]).name,
                Path(job["output_path"]).name,
                f"{job['input_format']} → {job['output_format']}",
                job["status"],
                job["created_at"],
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))


class SettingsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = _page_layout(self)
        storage_card, _ = _card("Application data")
        storage_layout = cast(QVBoxLayout, storage_card.layout())
        self.data_directory = self._add_path_row(storage_layout, "Workbench data", APP_DATA_DIR)
        self.database_path = self._add_path_row(storage_layout, "SQLite database", DB_PATH)
        self.repository_path = self._add_path_row(storage_layout, "Application files", REPO_ROOT)
        layout.addWidget(storage_card)

        model_card, _ = _card("Local model preferences")
        model_layout = cast(QVBoxLayout, model_card.layout())
        self.embedding_model = QLineEdit()
        self.embedding_model.setPlaceholderText("Installed embedding model, e.g. nomic-embed-text:latest")
        self.embedding_model.setAccessibleName("Preferred local embedding model")
        self.chat_model = QLineEdit()
        self.chat_model.setPlaceholderText("Installed chat model, e.g. phi3:latest")
        self.chat_model.setAccessibleName("Preferred local chat model")
        model_layout.addWidget(QLabel("Embedding model (separate capability)"))
        model_layout.addWidget(self.embedding_model)
        model_layout.addWidget(QLabel("Chat model"))
        model_layout.addWidget(self.chat_model)
        layout.addWidget(model_card)

        output_card, _ = _card("Conversion defaults and report output")
        output_layout = cast(QVBoxLayout, output_card.layout())
        row = QHBoxLayout()
        label = QLabel("Default output folder")
        label.setMinimumWidth(150)
        self.output_directory = QLineEdit()
        self.output_directory.setReadOnly(True)
        self.output_directory.setText(settings_repository.get("output_dir") or "Use the input file's folder")
        choose = QPushButton("Choose folder…")
        choose.clicked.connect(self._choose_output_folder)
        row.addWidget(label)
        row.addWidget(self.output_directory, 1)
        row.addWidget(choose)
        output_layout.addLayout(row)
        self.preference_feedback = QLabel("")
        self.preference_feedback.setWordWrap(True)
        self.preference_feedback.setVisible(False)
        output_layout.addWidget(self.preference_feedback)
        layout.addWidget(output_card)

        policy_card, policy_detail = _card("Saved permission policy")
        self.permission_controls: dict[str, QCheckBox] = {}
        policy_layout = cast(QVBoxLayout, policy_card.layout())
        for key, label in (
            ("policy_allow_document_access", "Allow local document import, indexing, and retrieval"),
            ("policy_allow_ai_suggestions", "Allow local AI answers and workflow planning"),
            ("policy_allow_agent_tools", "Allow the restricted local workflow tools"),
            ("policy_allow_ai_write_files", "Allow approved local evidence report creation"),
        ):
            checkbox = QCheckBox(label)
            checkbox.setAccessibleDescription(
                "Saved permission ceiling. The relevant page still requires a separate confirmation for each session."
            )
            self.permission_controls[key] = checkbox
            policy_layout.addWidget(checkbox)
        policy_detail.setText(
            "All saved permissions default to off. Saving a permission does not authorize an operation by itself: "
            "the relevant page also requires an explicit session confirmation. Ollama requests are restricted to "
            "loopback; cloud AI and remote model endpoints are not supported. This is application configuration, "
            "not proof of system-wide network isolation."
        )
        layout.addWidget(policy_card)
        self.save_button = QPushButton("Save model and permission settings")
        self.save_button.setObjectName("primary_button")
        self.save_button.clicked.connect(self.save_preferences)
        layout.addWidget(self.save_button)
        self.refresh_preferences()
        layout.addStretch(1)

    def refresh_preferences(self) -> None:
        """Reload saved values when returning to Settings from another page."""
        try:
            self.embedding_model.setText(settings_repository.get("local_embedding_model"))
            self.chat_model.setText(settings_repository.get("local_chat_model"))
            self.output_directory.setText(settings_repository.get("output_dir") or "Use the input file's folder")
            for key, checkbox in self.permission_controls.items():
                checkbox.setChecked(settings_repository.get_bool(key))
        except Exception as exc:
            self.preference_feedback.setObjectName("status_err")
            self.preference_feedback.setText(f"Could not load settings: {exc}")
            self.preference_feedback.setVisible(True)

    def save_preferences(self) -> None:
        values = {
            "local_embedding_model": self.embedding_model.text().strip(),
            "local_chat_model": self.chat_model.text().strip(),
            **{key: str(checkbox.isChecked()).lower() for key, checkbox in self.permission_controls.items()},
        }
        try:
            settings_repository.set_values(values)
        except Exception as exc:
            self.preference_feedback.setObjectName("status_err")
            self.preference_feedback.setText(f"Could not save settings: {exc}")
            self.preference_feedback.setVisible(True)
            return
        self.preference_feedback.setObjectName("status_ok")
        self.preference_feedback.setText("Model and permission settings saved. Page-level session confirmation is still required.")
        self.preference_feedback.setVisible(True)
        refresh = getattr(self.window(), "refresh_ai_readiness", None)
        if callable(refresh):
            refresh()

    @staticmethod
    def _add_path_row(layout, name: str, path: Path) -> QLabel:
        row = QHBoxLayout()
        label = QLabel(name)
        label.setMinimumWidth(150)
        value = QLabel(str(path))
        value.setObjectName("muted_text")
        value.setWordWrap(True)
        row.addWidget(label)
        row.addWidget(value, 1)
        layout.addLayout(row)
        return value

    def _choose_output_folder(self) -> None:
        current = settings_repository.get("output_dir")
        folder = QFileDialog.getExistingDirectory(self, "Choose default output folder", current or str(Path.home()))
        if not folder:
            return
        try:
            settings_repository.set_value("output_dir", folder)
        except Exception as exc:
            self.output_directory.setToolTip(f"Could not save preference: {exc}")
            self.preference_feedback.setObjectName("status_err")
            self.preference_feedback.setText(f"Could not save this preference: {exc}")
            self.preference_feedback.setVisible(True)
            return
        self.output_directory.setText(folder)
        self.output_directory.setToolTip("Saved as the default conversion output folder.")
        self.preference_feedback.setObjectName("status_ok")
        self.preference_feedback.setText("Default output folder saved.")
        self.preference_feedback.setVisible(True)


class ErrorPage(QWidget):
    def __init__(self, page_name: str, message: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = _page_layout(self)
        card, detail = _card(f"{page_name} is unavailable", message)
        detail.setText(f"This page could not be initialized.\n\n{message}")
        layout.addWidget(card)
        layout.addStretch(1)
