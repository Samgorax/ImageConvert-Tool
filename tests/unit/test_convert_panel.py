from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from engine.health_check import HealthReport, ToolInfo
from engine.job import ConversionResult, JobStatus
from storage import database, settings_repository
from ui.main_window import WorkbenchWindow
from ui.panels.convert_panel import ConvertPanel


@pytest.fixture
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def local_database(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "workbench.db")
    database.initialise_database()


def make_health(*, imagemagick=True, ghostscript=True):
    return HealthReport(
        imagemagick=ToolInfo(
            "ImageMagick", imagemagick, path="magick", version="ImageMagick test"
        ),
        ghostscript=ToolInfo(
            "Ghostscript", ghostscript, path="gs", version="Ghostscript test"
        ),
    )


def make_panel(app, tmp_path):
    panel = ConvertPanel(make_health())
    panel._out_combo.setCurrentText("BMP")
    panel._out_dir_edit.setText(str(tmp_path))
    return panel


def test_valid_queue_and_settings_enable_convert(app, local_database, tmp_path, sample_png):
    panel = make_panel(app, tmp_path)
    panel._enqueue_file(sample_png)
    assert panel._convert_btn.isEnabled()
    assert panel._in_combo.currentText() == "PNG"
    assert panel._queue.item(0, 2).text() == "BMP"


def test_conversion_refreshes_saved_settings_after_settings_page_change(app, local_database, tmp_path):
    panel = make_panel(app, tmp_path)
    settings_repository.set_values({
        "input_format": "JPEG",
        "output_format": "WEBP",
        "output_dir": str(tmp_path),
        "quality": "81",
        "density": "220",
        "all_pages": "false",
    })
    panel.refresh_preferences()
    assert panel._in_combo.currentText() == "JPEG"
    assert panel._out_combo.currentText() == "WEBP"
    assert panel._out_dir_edit.text() == str(tmp_path)
    assert panel._quality_slider.value() == 81
    assert panel._density_spin.value() == 220
    assert not panel._all_pages_chk.isChecked()


def test_output_format_change_updates_existing_queued_job(
    app, local_database, tmp_path, sample_png
):
    panel = make_panel(app, tmp_path)
    panel._enqueue_file(sample_png)
    panel._out_combo.setCurrentText("JPG")
    job = next(iter(panel._jobs.values()))
    assert job.output_format == "JPG"
    assert job.output_path == tmp_path / "sample.jpg"
    assert panel._queue.item(0, 2).text() == "JPG"


def test_empty_queue_keeps_convert_disabled(app, local_database, tmp_path):
    panel = make_panel(app, tmp_path)
    assert not panel._convert_btn.isEnabled()
    assert "Add one or more files" in panel._tool_status.text()


def test_missing_queued_input_disables_convert(app, local_database, tmp_path, sample_png):
    panel = make_panel(app, tmp_path)
    panel._enqueue_file(sample_png)
    sample_png.unlink()
    panel._refresh_convert_state()
    assert not panel._convert_btn.isEnabled()
    assert "missing or unreadable" in panel._tool_status.text()


def test_invalid_output_directory_disables_convert(app, local_database, tmp_path, sample_png):
    panel = make_panel(app, tmp_path)
    panel._enqueue_file(sample_png)
    panel._out_dir_edit.setText(str(tmp_path / "does-not-exist"))
    panel._update_queued_settings()
    assert not panel._convert_btn.isEnabled()
    assert "not writable" in panel._tool_status.text()


def test_unsupported_input_format_disables_convert(app, local_database, tmp_path):
    panel = make_panel(app, tmp_path)
    unsupported = tmp_path / "source.xyz"
    unsupported.write_bytes(b"data")
    panel._enqueue_file(unsupported)
    assert not panel._convert_btn.isEnabled()
    assert "Unsupported format" in panel._tool_status.text()


def test_missing_required_conversion_tool_disables_convert(
    app, local_database, tmp_path
):
    panel = ConvertPanel(make_health(ghostscript=False))
    panel._out_combo.setCurrentText("BMP")
    panel._out_dir_edit.setText(str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"pdf placeholder")
    panel._enqueue_file(source)
    assert not panel._convert_btn.isEnabled()
    assert "requires Ghostscript" in panel._tool_status.text()


def test_missing_imagemagick_disables_convert(app, local_database, tmp_path, sample_png):
    panel = ConvertPanel(make_health(imagemagick=False))
    panel._out_combo.setCurrentText("BMP")
    panel._out_dir_edit.setText(str(tmp_path))
    panel._enqueue_file(sample_png)
    assert not panel._convert_btn.isEnabled()
    assert "ImageMagick was not detected" in panel._tool_status.text()


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, value):
        for callback in self.callbacks:
            callback(value)


class FakeWorker:
    starts = 0
    result_success = True

    def __init__(self, job, _adapter):
        self.job = job
        self.progress = FakeSignal()
        self.finished = FakeSignal()
        self.error = FakeSignal()

    def isRunning(self):
        return False

    def start(self):
        type(self).starts += 1
        self.progress.emit(60)
        if self.result_success:
            self.job.output_path.write_bytes(b"actual test output")
            self.job.status = JobStatus.COMPLETED
            result = ConversionResult(
                self.job.job_id, True, self.job.output_path, 0.01
            )
        else:
            self.job.status = JobStatus.FAILED
            self.job.error_message = "conversion failed"
            result = ConversionResult(
                self.job.job_id, False, None, 0.01, "conversion failed"
            )
        self.finished.emit(result)


class DeferredWorker(FakeWorker):
    def isRunning(self):
        return True

    def start(self):
        type(self).starts += 1


class ErrorWorker(FakeWorker):
    def start(self):
        type(self).starts += 1
        self.error.emit("worker could not launch conversion")


@pytest.mark.parametrize(
    ("result_success", "expected_status", "expected_row"),
    [(True, JobStatus.COMPLETED, "✓ Done"), (False, JobStatus.FAILED, "✗ Failed")],
)
def test_click_starts_worker_and_worker_result_updates_ui(
    app,
    local_database,
    tmp_path,
    sample_png,
    monkeypatch,
    result_success,
    expected_status,
    expected_row,
):
    import ui.panels.convert_panel as convert_panel

    panel = make_panel(app, tmp_path)
    panel._enqueue_file(sample_png)
    FakeWorker.starts = 0
    FakeWorker.result_success = result_success
    monkeypatch.setattr(convert_panel, "ConversionWorker", FakeWorker)
    job = next(iter(panel._jobs.values()))

    panel._convert_btn.click()

    assert FakeWorker.starts == 1
    assert job.status == expected_status
    assert panel._queue.item(0, 3).text() == expected_row
    assert panel._progress.value() == 100
    assert not panel._convert_btn.isEnabled()


def test_worker_error_signal_marks_job_failed(app, local_database, tmp_path, sample_png, monkeypatch):
    import ui.panels.convert_panel as convert_panel

    panel = make_panel(app, tmp_path)
    panel._enqueue_file(sample_png)
    monkeypatch.setattr(convert_panel, "ConversionWorker", ErrorWorker)
    job = next(iter(panel._jobs.values()))

    panel._convert_btn.click()

    assert job.status == JobStatus.FAILED
    assert job.error_message == "worker could not launch conversion"
    assert panel._queue.item(0, 3).text() == "✗ Error"
    assert panel._progress.value() == 100


def test_repeated_click_does_not_start_concurrent_batch(
    app, local_database, tmp_path, sample_png, monkeypatch
):
    import ui.panels.convert_panel as convert_panel

    panel = make_panel(app, tmp_path)
    panel._enqueue_file(sample_png)
    DeferredWorker.starts = 0
    monkeypatch.setattr(convert_panel, "ConversionWorker", DeferredWorker)

    panel._convert_btn.click()
    panel._start_conversion()

    assert DeferredWorker.starts == 1
    assert panel._batch_active


def test_developer_branding_appears_once_in_sidebar(app, local_database):
    window = WorkbenchWindow(make_health(), start_runtime_probe=False)
    try:
        credits = [
            label for label in window.findChildren(QLabel)
            if label.text() == "Developed by SAURABH_GORAX"
        ]
        assert len(credits) == 1
        assert credits[0].objectName() == "sidebar_developer_credit"
    finally:
        window.close()
        app.processEvents()
