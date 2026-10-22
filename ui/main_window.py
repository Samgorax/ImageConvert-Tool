"""Navigation shell and lifecycle management for the desktop workbench."""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from documents.domain import DocumentStatus
from engine.health_check import HealthReport, ToolInfo
from engine.model_runtime import RuntimeInventory
from storage import document_repository, settings_repository
from ui.pages.workbench_pages import (
    AIWorkspacePage,
    DashboardPage,
    DocumentsPage,
    ErrorPage,
    ModelManagerPage,
    SettingsPage,
    TaskHistoryPage,
)
from ui.pages.workflows_page import WorkflowsPage
from ui.panels.convert_panel import ConvertPanel
from ui.workers.health_check_worker import HealthCheckWorker
from ui.workers.runtime_probe_worker import RuntimeProbeWorker

_log = logging.getLogger(__name__)

_NAV_ITEMS = (
    ("dashboard", "◈", "Dashboard", "System overview and local status"),
    ("ai_workspace", "✦", "AI Workspace", "Local AI assistant"),
    ("documents", "▤", "Documents", "Local knowledge library"),
    ("model_manager", "◉", "Model Manager", "Local runtime inventory"),
    ("task_history", "≋", "Task History", "Saved conversion activity"),
    ("workflows", "WF", "Workflows", "Human-approved local tasks"),
    ("settings", "⚙", "Settings", "Preferences and data paths"),
    ("conversion", "⇄", "Conversion", "Image and document conversion"),
)


class WorkbenchWindow(QMainWindow):
    """Main application window with resilient page creation and safe shutdown."""

    def __init__(
        self,
        health: HealthReport | None = None,
        parent: QWidget | None = None,
        page_factories: Mapping[str, Callable[[QWidget], QWidget]] | None = None,
        start_runtime_probe: bool = True,
    ) -> None:
        super().__init__(parent)
        self.health = health or HealthReport(
            imagemagick=ToolInfo("ImageMagick", False, notes="Tool discovery is running."),
            ghostscript=ToolInfo("Ghostscript", False, notes="Tool discovery is running."),
        )
        self._health_pending = health is None
        self._health_worker: HealthCheckWorker | None = None
        self.setWindowTitle("Sovereign Workbench")
        self.resize(1280, 820)
        self.setMinimumSize(960, 640)
        self._runtime_worker: RuntimeProbeWorker | None = None
        self._runtime_inventory: RuntimeInventory | None = None
        self._runtime_error = ""
        self._page_widgets: dict[str, QWidget] = {}
        self._navigation_buttons: dict[str, QPushButton] = {}
        self._page_titles = {key: (title, subtitle) for key, _, title, subtitle in _NAV_ITEMS}
        self._page_factories = self._default_page_factories()
        if page_factories:
            self._page_factories.update(page_factories)
        self._build_shell()
        self._build_pages()
        self.navigate("dashboard")
        self.statusBar().showMessage("Workbench foundation · local conversion tools")
        if self._health_pending:
            self._set_health_pending()
            self.refresh_health()
        if start_runtime_probe:
            self.refresh_runtime_inventory()

    def _default_page_factories(self) -> dict[str, Callable[[QWidget], QWidget]]:
        return {
            "dashboard": lambda parent: DashboardPage(self.health, parent, self.navigate),
            "ai_workspace": lambda parent: AIWorkspacePage(parent),
            "documents": lambda parent: DocumentsPage(parent),
            "model_manager": lambda parent: ModelManagerPage(self.refresh_runtime_inventory, parent),
            "task_history": lambda parent: TaskHistoryPage(parent),
            "workflows": lambda parent: WorkflowsPage(parent),
            "settings": lambda parent: SettingsPage(parent),
            "conversion": lambda parent: ConvertPanel(self.health, parent),
        }

    def _build_shell(self) -> None:
        shell = QWidget(self)
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("workbench_sidebar")
        sidebar.setFixedWidth(252)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 22, 18, 18)
        side_layout.setSpacing(7)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        brand_mark = QLabel("SW")
        brand_mark.setObjectName("workbench_brand_mark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setFixedSize(42, 42)
        brand_copy = QVBoxLayout()
        brand_copy.setSpacing(2)
        brand = QLabel("SOVEREIGN\nWORKBENCH")
        brand.setObjectName("workbench_brand")
        brand_subtitle = QLabel("LOCAL DESKTOP WORKSPACE")
        brand_subtitle.setObjectName("workbench_brand_subtitle")
        brand_copy.addWidget(brand)
        brand_copy.addWidget(brand_subtitle)
        brand_row.addWidget(brand_mark)
        brand_row.addLayout(brand_copy, 1)
        side_layout.addLayout(brand_row)
        section = QLabel("WORKSPACE")
        section.setObjectName("sidebar_section")
        side_layout.addSpacing(24)
        side_layout.addWidget(section)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        for key, icon, label, _subtitle in _NAV_ITEMS:
            button = QPushButton(f"{icon}    {label}")
            button.setObjectName("workbench_nav_button")
            button.setCheckable(True)
            button.setProperty("page_key", key)
            button.setMinimumHeight(46)
            button.clicked.connect(lambda checked=False, page_key=key: self.navigate(page_key))
            self._button_group.addButton(button)
            self._navigation_buttons[key] = button
            side_layout.addWidget(button)

        side_layout.addStretch(1)
        footer = QLabel("LOCAL WORKBENCH\nAI features are not configured")
        footer.setObjectName("sidebar_footer")
        footer.setWordWrap(True)
        side_layout.addWidget(footer)
        developer_credit = QLabel("Developed by SAURABH_GORAX")
        developer_credit.setObjectName("sidebar_developer_credit")
        developer_credit.setWordWrap(True)
        side_layout.addWidget(developer_credit)

        main_area = QWidget()
        main_area.setObjectName("workbench_main_area")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("workbench_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(28, 12, 28, 12)
        title_stack = QVBoxLayout()
        title_stack.setSpacing(3)
        self.page_title = QLabel("Dashboard")
        self.page_title.setObjectName("workbench_page_title")
        self.page_subtitle = QLabel("System overview and local status")
        self.page_subtitle.setObjectName("workbench_page_subtitle")
        title_stack.addWidget(self.page_title)
        title_stack.addWidget(self.page_subtitle)
        header_layout.addLayout(title_stack)
        header_layout.addStretch(1)
        self.mode_badge = QLabel("AI CHECKING")
        self.mode_badge.setObjectName("workbench_mode_badge")
        header_layout.addWidget(self.mode_badge)
        main_layout.addWidget(header)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("workbench_page_stack")
        main_layout.addWidget(self.page_stack, 1)
        shell_layout.addWidget(sidebar)
        shell_layout.addWidget(main_area, 1)
        self.setCentralWidget(shell)

    def _build_pages(self) -> None:
        for key, _icon, title, _subtitle in _NAV_ITEMS:
            try:
                factory = self._page_factories[key]
                page = factory(self.page_stack)
                if not isinstance(page, QWidget):
                    raise TypeError(f"Page factory for {title} did not return a QWidget")
            except Exception as exc:
                _log.exception("Could not initialize %s page", title)
                page = ErrorPage(title, str(exc), self.page_stack)
            self._page_widgets[key] = page
            self.page_stack.addWidget(page)

    def page_widget(self, key: str) -> QWidget:
        return self._page_widgets[key]

    def navigate(self, key: str) -> None:
        page = self._page_widgets.get(key)
        if page is None:
            return
        self.page_stack.setCurrentWidget(page)
        title, subtitle = self._page_titles[key]
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        for button_key, button in self._navigation_buttons.items():
            button.setChecked(button_key == key)
        if key == "dashboard" and isinstance(page, DashboardPage):
            page.refresh()
            self.refresh_ai_readiness()
        elif key == "ai_workspace" and isinstance(page, AIWorkspacePage):
            page.refresh_preferences()
        elif key == "documents" and isinstance(page, DocumentsPage):
            page.refresh_preferences()
        elif key == "conversion" and isinstance(page, ConvertPanel):
            page.refresh_preferences()
        elif key == "settings" and isinstance(page, SettingsPage):
            page.refresh_preferences()
        elif key == "task_history" and isinstance(page, TaskHistoryPage):
            page.refresh()
        elif key == "workflows" and isinstance(page, WorkflowsPage):
            page.refresh_preferences()
            page.refresh_documents()
            page.refresh_runs()

    def refresh_ai_readiness(self) -> None:
        """Show actionable readiness based on local inventory, saved settings, and indexed data."""
        dashboard = self._page_widgets.get("dashboard")
        if not isinstance(dashboard, DashboardPage):
            return
        try:
            if self._runtime_error:
                status, detail = "Runtime discovery failed", self._runtime_error
            elif self._runtime_inventory is None:
                status, detail = "Checking local runtime", "Ollama inventory is being checked in the background."
            else:
                ollama = next((runtime for runtime in self._runtime_inventory.runtimes
                               if runtime.name == "Ollama"), None)
                if ollama is None or not ollama.available:
                    status, detail = "Ollama unavailable", (ollama.message if ollama else "Ollama was not detected.")
                else:
                    embedding = settings_repository.get("local_embedding_model").strip()
                    chat = settings_repository.get("local_chat_model").strip()
                    installed = set(ollama.models)

                    def is_installed(model: str) -> bool:
                        return model in installed or (":" not in model and f"{model}:latest" in installed)

                    missing_settings = [name for name, value in (("embedding model", embedding), ("chat model", chat))
                                        if not value]
                    missing_models = [value for value in (embedding, chat) if value and not is_installed(value)]
                    if missing_settings:
                        status = "Models not configured"
                        detail = f"Set an installed local {' and '.join(missing_settings)} in Settings."
                    elif missing_models:
                        status = "Configured model not installed"
                        detail = f"Not listed by local Ollama: {', '.join(missing_models)}. No model is downloaded automatically."
                    elif not settings_repository.get_bool("policy_allow_document_access") or not settings_repository.get_bool("policy_allow_ai_suggestions"):
                        status = "AI permissions disabled"
                        detail = "Enable document access and local AI in Settings; each page still asks for session confirmation."
                    else:
                        indexed = sum(record.status == DocumentStatus.INDEXED
                                      for record in document_repository.list_documents())
                        status = ("Configured · session approval required" if indexed
                                  else "Models configured · no indexed documents")
                        detail = (f"Installed models: {embedding} and {chat}. {indexed} indexed document(s) available. "
                                  "The selected embedding and chat capabilities are verified when used.")
        except Exception as exc:
            status, detail = "Readiness check failed", f"Could not read local settings or document state: {exc}"
        dashboard.set_ai_readiness(status, detail)
        if status.startswith("Checking"):
            self.mode_badge.setText("AI CHECKING")
        elif status == "Configured · session approval required":
            self.mode_badge.setText("AI CONFIGURED")
        else:
            self.mode_badge.setText("AI NEEDS SETUP")

    def _set_health_pending(self) -> None:
        dashboard = self._page_widgets.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard.set_health_pending()

    def refresh_health(self) -> None:
        if self._health_worker is not None and self._health_worker.isRunning():
            return
        worker = HealthCheckWorker(self)
        self._health_worker = worker
        worker.health_ready.connect(self._on_health_report)
        worker.failed.connect(self._on_health_error)
        worker.finished.connect(self._on_health_probe_finished)
        worker.start()

    def _on_health_report(self, health: HealthReport) -> None:
        self.health = health
        self._health_pending = False
        dashboard = self._page_widgets.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard.set_health_report(health)
        conversion = self._page_widgets.get("conversion")
        if isinstance(conversion, ConvertPanel):
            conversion.update_health_report(health)

    def _on_health_error(self, message: str) -> None:
        self._health_pending = False
        dashboard = self._page_widgets.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard.set_health_error(message)
        conversion = self._page_widgets.get("conversion")
        if isinstance(conversion, ConvertPanel):
            conversion.update_health_report(self.health)

    def refresh_runtime_inventory(self) -> None:
        if self._runtime_worker is not None and self._runtime_worker.isRunning():
            return
        model_page = self._page_widgets.get("model_manager")
        if isinstance(model_page, ModelManagerPage):
            model_page.refresh_button.setEnabled(False)
            model_page.status_label.setText("Checking local runtimes in the background…")
            model_page.table.setRowCount(0)
        worker = RuntimeProbeWorker(self)
        self._runtime_error = ""
        self._runtime_inventory = None
        self.mode_badge.setText("AI CHECKING")
        workspace = self._page_widgets.get("ai_workspace")
        if isinstance(workspace, AIWorkspacePage):
            workspace.set_runtime_pending()
        self.refresh_ai_readiness()
        self._runtime_worker = worker
        worker.inventory_ready.connect(self._on_runtime_inventory)
        worker.failed.connect(self._on_runtime_probe_error)
        worker.finished.connect(self._on_runtime_probe_finished)
        worker.start()

    def _on_runtime_inventory(self, inventory: RuntimeInventory) -> None:
        self._runtime_inventory = inventory
        page = self._page_widgets.get("model_manager")
        if isinstance(page, ModelManagerPage):
            page.set_inventory(inventory)
        dashboard = self._page_widgets.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard.set_runtime_inventory(inventory)
        workspace = self._page_widgets.get("ai_workspace")
        if isinstance(workspace, AIWorkspacePage):
            workspace.set_runtime_inventory(inventory)
        self.refresh_ai_readiness()

    def _on_runtime_probe_error(self, message: str) -> None:
        self._runtime_error = message
        page = self._page_widgets.get("model_manager")
        if isinstance(page, ModelManagerPage):
            page.set_error(message)
        dashboard = self._page_widgets.get("dashboard")
        if isinstance(dashboard, DashboardPage):
            dashboard.set_runtime_error(message)
        workspace = self._page_widgets.get("ai_workspace")
        if isinstance(workspace, AIWorkspacePage):
            workspace.set_runtime_error(message)
        self.refresh_ai_readiness()

    def _on_runtime_probe_finished(self) -> None:
        page = self._page_widgets.get("model_manager")
        if isinstance(page, ModelManagerPage):
            page.refresh_button.setEnabled(True)
        self._runtime_worker = None

    def _on_health_probe_finished(self) -> None:
        self._health_worker = None

    def has_running_workers(self) -> bool:
        conversion = self._page_widgets.get("conversion")
        conversion_active = isinstance(conversion, ConvertPanel) and conversion.has_running_workers()
        document_pages_active = any(
            bool(getattr(self._page_widgets.get(key), "has_running_workers", lambda: False)())
            for key in ("documents", "ai_workspace")
        )
        runtime_active = self._runtime_worker is not None and self._runtime_worker.isRunning()
        health_active = self._health_worker is not None and self._health_worker.isRunning()
        workflows = self._page_widgets.get("workflows")
        workflow_active = bool(getattr(workflows, "has_running_workers", lambda: False)())
        return conversion_active or runtime_active or health_active or document_pages_active or workflow_active

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if self.has_running_workers():
            QMessageBox.information(
                self,
                "Workbench task in progress",
                "Wait for active local discovery, conversion, document, or workflow work to finish before closing.",
            )
            event.ignore()
            return
        event.accept()
