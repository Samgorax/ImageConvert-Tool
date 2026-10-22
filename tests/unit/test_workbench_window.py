from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QLabel

import ui.main_window as main_window
import ui.pages.workbench_pages as workbench_pages
from documents.domain import DocumentStatus
from engine.health_check import HealthReport, ToolInfo
from engine.model_runtime import RuntimeInventory, RuntimeStatus
from storage import database, document_repository, job_repository, settings_repository
from ui.main_window import WorkbenchWindow
from ui.pages.workbench_pages import (
    AIWorkspacePage,
    DashboardPage,
    ErrorPage,
    ModelManagerPage,
    SettingsPage,
    TaskHistoryPage,
)
from ui.pages.workflows_page import WorkflowsPage
from ui.panels.convert_panel import ConvertPanel
from ui.theme import STYLESHEET


@pytest.fixture
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def local_database(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "workbench.db")
    database.initialise_database()


def make_health() -> HealthReport:
    return HealthReport(
        imagemagick=ToolInfo("ImageMagick", True, path="C:/tools/magick.exe", version="7.1"),
        ghostscript=ToolInfo("Ghostscript", False, notes="Not detected"),
    )


def cell_text(table, row: int, column: int) -> str:
    item = table.item(row, column)
    assert item is not None
    return item.text()


def test_workbench_pages_initialize_and_conversion_panel_is_preserved(
    app, local_database
):
    window = WorkbenchWindow(make_health(), start_runtime_probe=False)
    try:
        assert window.page_stack.count() == 8
        assert set(window._page_widgets) == {
            "dashboard",
            "ai_workspace",
            "documents",
            "model_manager",
            "task_history",
            "settings",
            "conversion",
            "workflows",
        }
        conversion = window.page_widget("conversion")
        assert isinstance(conversion, ConvertPanel)
        assert isinstance(window.page_widget("workflows"), WorkflowsPage)
        assert hasattr(conversion, "_in_combo")
        assert hasattr(conversion, "_convert_btn")
        assert isinstance(window.page_widget("settings"), SettingsPage)
        brand_subtitle = window.findChild(QLabel, "workbench_brand_subtitle")
        assert brand_subtitle is not None
        assert brand_subtitle.text() == "LOCAL DESKTOP WORKSPACE"
        dashboard_text = " ".join(
            label.text() for label in window.page_widget("dashboard").findChildren(QLabel)
        )
        assert "Your local workbench" in dashboard_text
        dashboard = window.page_widget("dashboard")
        assert isinstance(dashboard, DashboardPage)
        assert "7.1" in dashboard.image_detail.text()
        assert "Not detected" in dashboard.ghostscript_status.text()
        assert "No cloud AI provider is integrated" in dashboard.privacy_detail.text()
        assert "not implemented" in " ".join(
            label.text() for label in window.page_widget("ai_workspace").findChildren(QLabel)
        ).lower()
        assert "not available yet" in " ".join(
            label.text() for label in window.page_widget("documents").findChildren(QLabel)
        ).lower()
    finally:
        window.close()
        app.processEvents()


def test_sidebar_navigation_changes_page_and_header(app, local_database):
    window = WorkbenchWindow(make_health(), start_runtime_probe=False)
    try:
        for key in window._page_widgets:
            window._navigation_buttons[key].click()
            assert window.page_stack.currentWidget() is window.page_widget(key)
            assert window._navigation_buttons[key].isChecked()
            assert window.page_title.text() == window._page_titles[key][0]
        assert "stop:0 #7138df" in STYLESHEET
        assert "QPushButton#workbench_nav_button:checked" in STYLESHEET
        assert "QMainWindow, QDialog, QWidget {" not in STYLESHEET
        workflows = window.page_widget("workflows")
        assert isinstance(workflows, WorkflowsPage)
        assert not workflows.enable_planning.isChecked()
        assert not workflows.enable_tools.isChecked()
        assert not workflows.allow_writes.isChecked()
    finally:
        window.close()
        app.processEvents()


def test_dashboard_quick_actions_navigate_to_existing_pages(app, local_database):
    window = WorkbenchWindow(make_health(), start_runtime_probe=False)
    try:
        dashboard = window.page_widget("dashboard")
        assert isinstance(dashboard, DashboardPage)
        assert set(dashboard.quick_action_buttons) == {
            "conversion",
            "task_history",
            "model_manager",
            "settings",
        }
        for page_key, button in dashboard.quick_action_buttons.items():
            button.click()
            assert window.page_stack.currentWidget() is window.page_widget(page_key)
    finally:
        window.close()
        app.processEvents()


def test_dashboard_layout_adapts_to_window_width(app, local_database):
    window = WorkbenchWindow(make_health(), start_runtime_probe=False)
    dashboard = window.page_widget("dashboard")
    assert isinstance(dashboard, DashboardPage)
    try:
        window.resize(1440, 900)
        window.show()
        app.processEvents()
        assert dashboard.status_columns == 4
        assert dashboard.details_layout.direction().name == "LeftToRight"
        window.resize(960, 640)
        app.processEvents()
        assert dashboard.status_columns == 2
        assert dashboard.details_layout.direction().name == "TopToBottom"
    finally:
        window.close()
        app.processEvents()


def test_dashboard_runtime_and_recent_jobs_use_actual_data(app, local_database, monkeypatch):
    monkeypatch.setattr(
        job_repository,
        "list_jobs",
        lambda **_kwargs: [{
            "input_path": "D:/docs/actual.pdf",
            "output_path": "D:/out/actual.png",
            "input_format": "PDF",
            "output_format": "PNG",
            "status": "COMPLETED",
            "created_at": "2026-10-22T12:00:00+00:00",
        }],
    )
    window = WorkbenchWindow(make_health(), start_runtime_probe=False)
    inventory = RuntimeInventory((
        RuntimeStatus("Ollama", True, "C:/tools/ollama.exe", "0.5.0", ("qwen:latest",), True),
    ))
    try:
        dashboard = window.page_widget("dashboard")
        assert isinstance(dashboard, DashboardPage)
        dashboard.set_runtime_inventory(inventory)
        assert "Ollama" in dashboard.runtime_status.text()
        assert "1 installed model" in dashboard.runtime_detail.text()
        recent_text = " ".join(
            label.text() for label in dashboard.recent_card.findChildren(QLabel)
        )
        assert "actual.pdf" in recent_text
        assert "PDF → PNG" in recent_text
        assert "COMPLETED" in recent_text
    finally:
        window.close()
        app.processEvents()


def test_page_initialization_failure_is_shown_without_breaking_navigation(
    app, local_database, caplog
):
    def fail_page(_parent):
        raise RuntimeError("page dependency unavailable")

    window = WorkbenchWindow(
        make_health(),
        page_factories={"documents": fail_page},
        start_runtime_probe=False,
    )
    try:
        page = window.page_widget("documents")
        assert isinstance(page, ErrorPage)
        assert any("page dependency unavailable" in label.text() for label in page.findChildren(QLabel))
        window._navigation_buttons["settings"].click()
        assert window.page_title.text() == "Settings"
        assert "Could not initialize Documents page" in caplog.text
    finally:
        window.close()
        app.processEvents()


def test_task_history_reports_storage_errors(app, monkeypatch):
    monkeypatch.setattr(
        job_repository,
        "list_jobs",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("database is read-only")),
    )
    page = TaskHistoryPage()
    try:
        assert "database is read-only" in page.status_label.text()
        assert page.table.rowCount() == 0
    finally:
        page.close()
        app.processEvents()


def test_task_history_shows_saved_jobs(app, monkeypatch):
    monkeypatch.setattr(
        job_repository,
        "list_jobs",
        lambda **_kwargs: [
            {
                "input_path": "D:/docs/manual.png",
                "output_path": "D:/out/manual.pdf",
                "input_format": "PNG",
                "output_format": "PDF",
                "status": "COMPLETED",
                "created_at": "2026-10-22T12:00:00+00:00",
            }
        ],
    )
    page = TaskHistoryPage()
    try:
        assert page.table.rowCount() == 1
        assert cell_text(page.table, 0, 0) == "manual.png"
        assert cell_text(page.table, 0, 3) == "COMPLETED"
    finally:
        page.close()
        app.processEvents()


def test_settings_page_persists_output_directory(app, local_database, monkeypatch):
    monkeypatch.setattr(
        workbench_pages.QFileDialog,
        "getExistingDirectory",
        lambda *_args: "D:/workbench/outputs",
    )
    page = SettingsPage()
    try:
        page._choose_output_folder()
        assert settings_repository.get("output_dir") == "D:/workbench/outputs"
        assert page.output_directory.text() == "D:/workbench/outputs"
        assert not page.preference_feedback.isHidden()
        assert "saved" in page.preference_feedback.text().lower()
    finally:
        page.close()
        app.processEvents()


def test_settings_page_exposes_persistence_error(app, local_database, monkeypatch):
    monkeypatch.setattr(
        workbench_pages.QFileDialog,
        "getExistingDirectory",
        lambda *_args: "D:/workbench/outputs",
    )
    monkeypatch.setattr(
        settings_repository,
        "set_value",
        lambda *_args: (_ for _ in ()).throw(OSError("database is read-only")),
    )
    page = SettingsPage()
    try:
        page._choose_output_folder()
        assert not page.preference_feedback.isHidden()
        assert "database is read-only" in page.preference_feedback.text()
    finally:
        page.close()
        app.processEvents()


def test_settings_page_persists_models_and_default_deny_permission_profile(app, local_database):
    page = SettingsPage()
    try:
        page.embedding_model.setText("nomic-embed-text:latest")
        page.chat_model.setText("phi3:latest")
        page.permission_controls["policy_allow_document_access"].setChecked(True)
        page.permission_controls["policy_allow_ai_suggestions"].setChecked(True)
        page.save_button.click()

        assert settings_repository.get("local_embedding_model") == "nomic-embed-text:latest"
        assert settings_repository.get("local_chat_model") == "phi3:latest"
        assert settings_repository.get_bool("policy_allow_document_access")
        assert settings_repository.get_bool("policy_allow_ai_suggestions")
        assert not settings_repository.get_bool("policy_allow_agent_tools")
        assert "session confirmation is still required" in page.preference_feedback.text()
    finally:
        page.close()
        app.processEvents()


def test_dashboard_ai_readiness_uses_runtime_settings_and_index_state(app, local_database, monkeypatch):
    monkeypatch.setattr(document_repository, "list_documents", lambda: [])
    settings_repository.set_values({
        "local_embedding_model": "nomic-embed-text:latest",
        "local_chat_model": "phi3:latest",
        "policy_allow_document_access": "true",
        "policy_allow_ai_suggestions": "true",
    })
    window = WorkbenchWindow(make_health(), start_runtime_probe=False)
    inventory = RuntimeInventory((RuntimeStatus(
        "Ollama", True, "C:/tools/ollama.exe", "0.5.0",
        ("nomic-embed-text:latest", "phi3:latest"), True,
    ),))
    try:
        window._runtime_inventory = inventory
        window.refresh_ai_readiness()
        dashboard = window.page_widget("dashboard")
        assert dashboard.ai_status.text() == "Models configured · no indexed documents"
        assert "0 indexed document(s)" in dashboard.ai_detail.text()
        assert window.mode_badge.text() == "AI NEEDS SETUP"
    finally:
        window.close()
        app.processEvents()


def test_workflow_permissions_require_saved_policy_and_session_confirmation(app, local_database):
    page = WorkflowsPage()
    try:
        page.enable_planning.setChecked(True)
        page.allow_documents.setChecked(True)
        page.enable_tools.setChecked(True)
        page.allow_writes.setChecked(True)
        policy = page._policy()
        assert not policy.allow_ai_suggestions
        assert not policy.allow_document_access
        assert not policy.allow_agent_tools
        assert not policy.allow_ai_write_files

        settings_repository.set_values({
            "policy_allow_ai_suggestions": "true",
            "policy_allow_document_access": "true",
            "policy_allow_agent_tools": "true",
            "policy_allow_ai_write_files": "true",
        })
        policy = page._policy()
        assert policy.allow_ai_suggestions
        assert policy.allow_document_access
        assert policy.allow_agent_tools
        assert policy.allow_ai_write_files
    finally:
        page.close()
        app.processEvents()


def test_workflow_plan_explains_missing_local_model(app, local_database):
    page = WorkflowsPage()
    try:
        page.task.setPlainText("Find a fact in the selected local document.")
        page.plan_button.click()
        assert "installed local chat model" in page.status.text()
    finally:
        page.close()
        app.processEvents()


def test_ai_workspace_reports_runtime_settings_and_session_blockers(
    app, local_database, monkeypatch
):
    monkeypatch.setattr(document_repository, "list_documents", lambda: [SimpleNamespace(
        status=DocumentStatus.INDEXED, filename="known.txt", document_id="doc-known",
    )])
    page = AIWorkspacePage()
    try:
        assert not page.ask_button.isEnabled()
        assert "Waiting for local Ollama inventory" in page.status.text()

        page.set_runtime_inventory(RuntimeInventory((RuntimeStatus(
            "Ollama", True, models=("nomic-embed-text:latest", "phi3:latest"), inventory_supported=True,
        ),)))
        page.embedding_model_input.setText("nomic-embed-text:latest")
        page.chat_model_input.setText("phi3:latest")
        page.question_input.setText("What is the known fact?")
        page.allow_document_access.setChecked(True)
        page.allow_ai_answers.setChecked(True)
        page._update_availability()
        assert "Enable document access in Settings" in page.status.text()

        settings_repository.set_value("policy_allow_document_access", "true")
        page._update_availability()
        assert "Enable local AI answers in Settings" in page.status.text()

        settings_repository.set_value("policy_allow_ai_suggestions", "true")
        page._update_availability()
        assert page.ask_button.isEnabled()
        page.set_runtime_error("Ollama CLI is not responding")
        assert not page.ask_button.isEnabled()
        assert "not responding" in page.status.text()
    finally:
        page.close()
        app.processEvents()


def test_close_is_blocked_while_workbench_workers_are_active(app, local_database, monkeypatch):
    window = WorkbenchWindow(make_health(), start_runtime_probe=False)
    shown = []

    class CloseEvent:
        accepted = False
        ignored = False

        def accept(self):
            self.accepted = True

        def ignore(self):
            self.ignored = True

    try:
        monkeypatch.setattr(window, "has_running_workers", lambda: True)
        monkeypatch.setattr(main_window.QMessageBox, "information", lambda *args: shown.append(args))
        event = CloseEvent()
        window.closeEvent(event)
        assert event.ignored and not event.accepted
        assert shown
    finally:
        monkeypatch.setattr(window, "has_running_workers", lambda: False)
        window.close()
        app.processEvents()


def test_model_manager_uses_actual_runtime_inventory(app):
    refresh_requests = []
    page = ModelManagerPage(lambda: refresh_requests.append(True))
    inventory = RuntimeInventory(
        (
            RuntimeStatus(
                "Ollama", True, "C:/tools/ollama.exe", "0.5.0", ("qwen:latest",), True
            ),
            RuntimeStatus("llama.cpp", False, inventory_supported=False, message="CLI not detected"),
        )
    )
    try:
        page.set_inventory(inventory)
        assert page.table.rowCount() == 2
        assert cell_text(page.table, 0, 0) == "Ollama"
        assert "qwen:latest" in cell_text(page.table, 0, 2)
        assert cell_text(page.table, 1, 1) == "Not detected"
        page.refresh_button.click()
        assert refresh_requests == [True]
        page.set_error("local inventory command failed")
        assert page.table.rowCount() == 0
        assert "local inventory command failed" in page.status_label.text()
    finally:
        page.close()
        app.processEvents()
