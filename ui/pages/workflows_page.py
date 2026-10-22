"""Human-approved local workflow UI."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from documents.domain import DocumentStatus
from permissions.policy import PermissionPolicy
from storage import document_repository, settings_repository
from ui.workers.workflow_worker import WorkflowWorker
from workflows.domain import StepState, WorkflowRunRecord
from workflows.service import get_workflow, list_workflows


class WorkflowsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 20)
        self.status = QLabel("Local workflow planning is off until enabled for this session.")
        self.task = QTextEdit()
        self.task.setPlaceholderText("Describe a document task…")
        self.documents = QListWidget()
        self.embedding_model = QLineEdit(settings_repository.get("local_embedding_model"))
        self.chat_model = QLineEdit(settings_repository.get("local_chat_model"))
        self.enable_planning = QCheckBox("Enable local AI planning for this session")
        self.allow_documents = QCheckBox("Allow selected documents to be retrieved in this session")
        self.enable_tools = QCheckBox("Allow approved workflow tools for this session")
        self.allow_writes = QCheckBox("Allow approved report file creation for this session")
        self.output_directory = QLineEdit(settings_repository.get("output_dir"))
        browse = QPushButton("Choose output folder")
        browse.clicked.connect(self._browse_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_directory, 1)
        output_row.addWidget(browse)
        self.plan_button = QPushButton("Plan workflow")
        self.plan_button.clicked.connect(self.plan)
        self.steps = QTableWidget(0, 4)
        self.steps.setHorizontalHeaderLabels(["#", "Tool", "State", "Result / error"])
        self.steps.horizontalHeader().setStretchLastSection(True)
        self.approve_button = QPushButton("Approve selected step")
        self.deny_button = QPushButton("Deny selected step")
        self.cancel_button = QPushButton("Cancel active request")
        self.approve_button.clicked.connect(lambda: self.decide(True))
        self.deny_button.clicked.connect(lambda: self.decide(False))
        self.cancel_button.clicked.connect(self.cancel)
        self.runs = QListWidget()
        self.runs.itemSelectionChanged.connect(self._load_selected_run)
        self.documents.itemChanged.connect(self._refresh_controls)
        self.steps.currentCellChanged.connect(lambda *_args: self._refresh_controls())
        self.task.textChanged.connect(self._refresh_controls)
        self.chat_model.textChanged.connect(self._refresh_controls)
        self.embedding_model.textChanged.connect(self._refresh_controls)
        for checkbox in (self.enable_planning, self.allow_documents, self.enable_tools, self.allow_writes):
            checkbox.toggled.connect(self._refresh_controls)
        actions = QHBoxLayout()
        actions.addWidget(self.plan_button)
        actions.addWidget(self.approve_button)
        actions.addWidget(self.deny_button)
        actions.addWidget(self.cancel_button)
        for widget in (QLabel("Task"), self.task, QLabel("Indexed documents in scope"), self.documents,
                       QLabel("Ollama chat model"), self.chat_model, QLabel("Ollama embedding model"),
                       self.embedding_model, self.enable_planning, self.allow_documents,
                       self.enable_tools, self.allow_writes,
                       QLabel("Report output directory")):
            layout.addWidget(widget)
        layout.addLayout(output_row)
        layout.addLayout(actions)
        layout.addWidget(self.status)
        layout.addWidget(QLabel("Saved workflow runs (select to resume or review)"))
        layout.addWidget(self.runs)
        layout.addWidget(self.steps, 1)
        self._worker: WorkflowWorker | None = None
        self._run: WorkflowRunRecord | None = None
        self.refresh_documents()
        self.refresh_runs()
        self.refresh_preferences()

    def refresh_preferences(self) -> None:
        try:
            self.embedding_model.setText(settings_repository.get("local_embedding_model"))
            self.chat_model.setText(settings_repository.get("local_chat_model"))
            self.output_directory.setText(settings_repository.get("output_dir"))
            self._refresh_controls()
        except Exception as exc:
            self.status.setText(f"Could not load saved preferences: {exc}")

    def _output_directory(self) -> Path | None:
        value = self.output_directory.text().strip()
        if not self.allow_writes.isChecked() or not value:
            return None
        path = Path(value).expanduser()
        return path if path.is_dir() else None

    def refresh_documents(self) -> None:
        self.documents.clear()
        try:
            records = document_repository.list_documents()
        except Exception as exc:
            self.status.setText(f"Could not load indexed documents: {exc}")
            self._refresh_controls()
            return
        for record in records:
            if record.status == DocumentStatus.INDEXED:
                item = QListWidgetItem(f"{record.filename} · {record.document_id[:10]}")
                item.setData(Qt.ItemDataRole.UserRole, record.document_id)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.documents.addItem(item)
        self._refresh_controls()

    def _selected_documents(self) -> tuple[str, ...]:
        return tuple(str(self.documents.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(self.documents.count())
                     if self.documents.item(i).checkState())

    def _policy(self) -> PermissionPolicy:
        output = self._output_directory()
        return PermissionPolicy(
            allow_ai_suggestions=(self.enable_planning.isChecked()
                                  and settings_repository.get_bool("policy_allow_ai_suggestions")),
            allow_agent_tools=(self.enable_tools.isChecked()
                               and settings_repository.get_bool("policy_allow_agent_tools")),
            allow_document_access=(self.allow_documents.isChecked()
                                   and settings_repository.get_bool("policy_allow_document_access")),
            allow_ai_write_files=(self.allow_writes.isChecked()
                                  and settings_repository.get_bool("policy_allow_ai_write_files")),
            allowed_output_roots=[str(output.resolve())] if output else [],
        )

    def _browse_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose report output folder", self.output_directory.text())
        if folder:
            try:
                settings_repository.set_value("output_dir", folder)
            except Exception as exc:
                self.status.setText(f"Could not save the output folder: {exc}")
                return
            self.output_directory.setText(folder)

    def plan(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        try:
            reason = self._plan_block_reason()
            if reason:
                self.status.setText(reason)
                self._refresh_controls()
                return
            settings_repository.set_values({
                "local_chat_model": self.chat_model.text().strip(),
                "local_embedding_model": self.embedding_model.text().strip(),
                "output_dir": self.output_directory.text().strip(),
            })
            self._start(WorkflowWorker("plan", task=self.task.toPlainText(), model=self.chat_model.text().strip(),
                policy=self._policy(), document_ids=self._selected_documents(),
                embedding_model=self.embedding_model.text().strip(),
                output_directory=self._output_directory()))
            self.status.setText("Planning with the configured local Ollama model…")
        except Exception as exc:
            self.status.setText(str(exc))
            self._refresh_controls()

    def decide(self, approved: bool) -> None:
        if not self._run or (self._worker and self._worker.isRunning()):
            return
        row = self.steps.currentRow()
        if row < 0 or row >= len(self._run.steps):
            self.status.setText("Select a step first.")
            return
        step = self._run.steps[row]
        if step.state != StepState.AWAITING_APPROVAL:
            self.status.setText("The selected step is not awaiting approval.")
            self._refresh_controls()
            return
        if approved:
            reason = self._approval_block_reason(step)
            if reason:
                self.status.setText(reason)
                self._refresh_controls()
                return
        self._start(WorkflowWorker("approve", run_id=self._run.run_id, step_id=step.step_id,
            approved=approved, policy=self._policy(), document_ids=self._selected_documents(),
            embedding_model=self.embedding_model.text().strip(),
            output_directory=self._output_directory()))
        self.status.setText("Executing approved local step…" if approved else "Recording denial…")

    def _start(self, worker: WorkflowWorker) -> None:
        self._worker = worker
        worker.workflow_ready.connect(self._on_workflow)
        worker.failed.connect(lambda message: self.status.setText(f"Workflow action failed: {message}"))
        worker.finished.connect(self._on_finished)
        worker.start()
        self._refresh_controls()

    def _on_workflow(self, run: WorkflowRunRecord) -> None:
        self._run = run
        self.steps.setRowCount(len(run.steps))
        for row, step in enumerate(run.steps):
            result = step.error_message or (str(step.result) if step.result else str(step.arguments))
            for column, value in enumerate((str(step.ordinal), step.tool_id, step.state.value, result)):
                self.steps.setItem(row, column, QTableWidgetItem(value))
        self.status.setText(f"{run.title} · {run.state.value}")
        self.refresh_runs()

    def refresh_runs(self) -> None:
        selected = self._run.run_id if self._run else None
        self.runs.blockSignals(True)
        self.runs.clear()
        try:
            records = list_workflows()
        except Exception as exc:
            self.runs.blockSignals(False)
            self.status.setText(f"Workflow history unavailable: {exc}")
            return
        for run in records:
            item = QListWidgetItem(f"{run.title} · {run.state.value}")
            item.setData(Qt.ItemDataRole.UserRole, run.run_id)
            self.runs.addItem(item)
            if run.run_id == selected:
                self.runs.setCurrentItem(item)
        self.runs.blockSignals(False)
        self._refresh_controls()

    def _load_selected_run(self) -> None:
        item = self.runs.currentItem()
        if item is None:
            return
        try:
            run = get_workflow(str(item.data(Qt.ItemDataRole.UserRole)))
        except Exception as exc:
            self.status.setText(f"Could not load the selected workflow: {exc}")
            return
        if run:
            self._on_workflow(run)

    def cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.status.setText("Cancellation requested; waiting for the local request to return…")

    def _on_finished(self) -> None:
        self._worker = None
        self._refresh_controls()

    def _plan_block_reason(self) -> str:
        checks = (
            (bool(self.task.toPlainText().strip()), "Describe the task before planning."),
            (bool(self.chat_model.text().strip()), "Set an installed local chat model in Settings."),
            (bool(self.embedding_model.text().strip()), "Set an installed local embedding model in Settings."),
            (bool(self._selected_documents()), "Select at least one indexed document for the workflow scope."),
            (settings_repository.get_bool("policy_allow_ai_suggestions"), "Enable local AI planning in Settings."),
            (settings_repository.get_bool("policy_allow_agent_tools"), "Enable restricted workflow tools in Settings."),
            (settings_repository.get_bool("policy_allow_document_access"), "Enable document access in Settings."),
            (self.enable_planning.isChecked(), "Confirm local AI planning for this session."),
            (self.enable_tools.isChecked(), "Confirm restricted workflow tools for this session."),
            (self.allow_documents.isChecked(), "Confirm document retrieval for this session."),
        )
        blocked = next((reason for ready, reason in checks if not ready), "")
        if blocked:
            return blocked
        if self.allow_writes.isChecked() and self._output_directory() is None:
            return "Choose an existing output folder or turn off report file creation."
        return ""

    def _approval_block_reason(self, step) -> str:
        policy = self._policy()
        if not policy.allow_agent_tools:
            return "Enable restricted workflow tools in Settings and confirm them for this session."
        if not policy.allow_document_access:
            return "Enable document access in Settings and confirm it for this session."
        if step.tool_id == "write_evidence_report" and not policy.allow_ai_write_files:
            return "Enable report creation in Settings and confirm file writing for this session."
        if step.tool_id == "write_evidence_report" and self._output_directory() is None:
            return "Choose an existing report output folder before approving file creation."
        return ""

    def _refresh_controls(self, *_args) -> None:
        active = bool(self._worker and self._worker.isRunning())
        self.plan_button.setEnabled(not active)
        try:
            self.plan_button.setToolTip(self._plan_block_reason())
        except Exception as exc:
            self.plan_button.setToolTip(f"Saved workflow settings are unavailable: {exc}")
        selected = self.steps.currentRow()
        awaiting = bool(self._run and 0 <= selected < len(self._run.steps)
                        and self._run.steps[selected].state == StepState.AWAITING_APPROVAL)
        self.approve_button.setEnabled(not active and awaiting)
        self.deny_button.setEnabled(not active and awaiting)
        self.cancel_button.setEnabled(active)

    def has_running_workers(self) -> bool:
        return self._worker is not None and self._worker.isRunning()
