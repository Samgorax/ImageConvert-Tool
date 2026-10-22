"""
ui/panels/convert_panel.py
===========================
The main conversion panel — the heart of the UI.

Layout:
  ┌─ Drop Zone ────────────────────────────────────────────────┐
  │  ⬆  Drop files here or click Browse                        │
  └────────────────────────────────────────────────────────────┘
  ┌─ Format row ──────────────────────────────────────────────┐
  │  [ PNG  ▼ ]     ──→──     [ PDF  ▼ ]                     │
  └───────────────────────────────────────────────────────────┘
  ┌─ Job queue (QTableWidget) ────────────────────────────────┐
  │  File name      │ Fmt │ Output │ Status  │ Size           │
  └───────────────────────────────────────────────────────────┘
  ┌─ Options ─────────────────────────────────────────────────┐
  │  Quality ─────●──── 95%   DPI [300]  ☑ All pages         │
  └───────────────────────────────────────────────────────────┘
  ┌─ Output dir ──────────────────────────────────────────────┐
  │  /Users/.../Downloads                        [Browse]     │
  └───────────────────────────────────────────────────────────┘
  [  Convert Now  ]   [  Clear Queue  ]   ████░░░░ 45%
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.config import (
    DEFAULT_ALL_PAGES,
    DEFAULT_DENSITY,
    DEFAULT_QUALITY,
    FORMATS,
    VECTOR_DOC_FORMATS,
)
from engine.health_check import HealthReport
from engine.imagemagick_adapter import ImageMagickAdapter
from engine.job import ConversionJob, ConversionOptions, ConversionResult, JobStatus
from permissions.audit_log import log_event
from storage import job_repository, settings_repository
from ui.workers.conversion_worker import ConversionWorker

_log = logging.getLogger(__name__)


# ── Column indices for the job queue table ─────────────────────────────────────
_COL_NAME   = 0
_COL_IN_FMT = 1
_COL_OUT_FMT= 2
_COL_STATUS = 3
_COL_SIZE   = 4


# ── Drop zone widget ───────────────────────────────────────────────────────────

class DropZone(QFrame):
    """Clickable, drag-and-drop file receiving area."""

    def __init__(self, parent: ConvertPanel) -> None:
        super().__init__(parent)
        self._panel = parent
        self.setObjectName("drop_zone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(6)

        icon = QLabel("⬆")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 32px; color: #7c3aed;")

        title = QLabel("Drop files here or click to browse")
        title.setObjectName("drop_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub = QLabel("PNG · JPG · PDF · WEBP · TIFF and more")
        sub.setObjectName("drop_sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(icon)
        lay.addWidget(title)
        lay.addWidget(sub)

    # ── Mouse click → open file dialog ────────────────────────────────────────
    def mousePressEvent(self, event):
        self._panel._browse_files()

    # ── Drag & drop ───────────────────────────────────────────────────────────
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("drag_active", "true")
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("drag_active", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event: QDropEvent):
        self.setProperty("drag_active", "false")
        self.style().unpolish(self)
        self.style().polish(self)
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        for p in paths:
            self._panel._enqueue_file(Path(p))


# ── Main panel ─────────────────────────────────────────────────────────────────

class ConvertPanel(QWidget):
    """Primary conversion UI panel."""

    def __init__(self, health: HealthReport, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._health  = health
        self._adapter = ImageMagickAdapter(health.imagemagick)
        self._workers: list[ConversionWorker] = []   # keep references alive
        self._jobs:    dict[str, ConversionJob] = {}  # job_id → job
        self._batch_active = False

        self._build_ui()
        self._load_settings()
        self._in_combo.setToolTip("Input formats are detected from the queued file names.")
        self._in_combo.setEnabled(False)
        self._out_combo.currentTextChanged.connect(self._update_queued_settings)
        self._quality_slider.valueChanged.connect(self._update_queued_settings)
        self._density_spin.valueChanged.connect(self._update_queued_settings)
        self._all_pages_chk.toggled.connect(self._update_queued_settings)
        self._refresh_tool_status()

    def has_running_workers(self) -> bool:
        """Return whether a conversion thread is still executing."""
        return any(worker.isRunning() for worker in self._workers)

    def update_health_report(self, health: HealthReport) -> None:
        """Refresh tool availability after asynchronous startup discovery."""
        self._health = health
        self._adapter = ImageMagickAdapter(health.imagemagick)
        self._refresh_tool_status()

    # ── Build UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # ── Drop zone ──────────────────────────────────────────────────────────
        self._drop_zone = DropZone(self)
        root.addWidget(self._drop_zone)

        # ── Format selection row ───────────────────────────────────────────────
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(0)

        in_label  = QLabel("INPUT FORMAT")
        in_label.setObjectName("section_label")
        in_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._in_combo = QComboBox()
        self._in_combo.setObjectName("format_combo")
        self._in_combo.addItems(FORMATS)
        self._in_combo.setCurrentText("PNG")

        arrow = QLabel("→")
        arrow.setObjectName("arrow_label")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(50)

        out_label = QLabel("OUTPUT FORMAT")
        out_label.setObjectName("section_label")
        out_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._out_combo = QComboBox()
        self._out_combo.setObjectName("format_combo")
        self._out_combo.addItems(FORMATS)
        self._out_combo.setCurrentText("PDF")

        in_col  = QVBoxLayout()
        out_col = QVBoxLayout()
        in_col.setSpacing(4)
        out_col.setSpacing(4)
        in_col.addWidget(in_label)
        in_col.addWidget(self._in_combo)
        out_col.addWidget(out_label)
        out_col.addWidget(self._out_combo)

        fmt_row.addLayout(in_col)
        fmt_row.addWidget(arrow)
        fmt_row.addLayout(out_col)
        fmt_row.addStretch()

        root.addLayout(fmt_row)

        # ── Job queue ──────────────────────────────────────────────────────────
        q_label = QLabel("QUEUE")
        q_label.setObjectName("section_label")
        root.addWidget(q_label)

        self._queue = QTableWidget(0, 5)
        self._queue.setObjectName("queue_table")
        self._queue.setHorizontalHeaderLabels(
            ["File", "Input", "Output", "Status", "Size"]
        )
        self._queue.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            self._queue.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._queue.setAlternatingRowColors(True)
        self._queue.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._queue.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._queue.verticalHeader().setVisible(False)
        self._queue.setMinimumHeight(140)
        root.addWidget(self._queue, stretch=1)

        # ── Conversion options ─────────────────────────────────────────────────
        opts_group = QGroupBox("CONVERSION OPTIONS")
        opts_lay   = QVBoxLayout(opts_group)
        opts_lay.setSpacing(10)

        # Quality row
        q_row = QHBoxLayout()
        q_lbl = QLabel("JPEG / WEBP quality")
        q_lbl.setObjectName("section_label")
        self._quality_slider = QSlider(Qt.Orientation.Horizontal)
        self._quality_slider.setRange(1, 100)
        self._quality_slider.setValue(DEFAULT_QUALITY)
        self._quality_val = QLabel(f"{DEFAULT_QUALITY}%")
        self._quality_slider.valueChanged.connect(
            lambda v: self._quality_val.setText(f"{v}%")
        )
        q_row.addWidget(q_lbl)
        q_row.addWidget(self._quality_slider, stretch=1)
        q_row.addWidget(self._quality_val)

        # DPI row
        dpi_row = QHBoxLayout()
        dpi_lbl = QLabel("PDF / PS / EPS render DPI")
        dpi_lbl.setObjectName("section_label")
        self._density_spin = QSpinBox()
        self._density_spin.setRange(72, 1200)
        self._density_spin.setValue(DEFAULT_DENSITY)
        self._density_spin.setSuffix("  DPI")
        dpi_row.addWidget(dpi_lbl)
        dpi_row.addStretch()
        dpi_row.addWidget(self._density_spin)

        self._all_pages_chk = QCheckBox(
            "Convert every page / frame to numbered files "
            "(recommended for multi-page PDFs and animated GIFs)"
        )
        self._all_pages_chk.setChecked(DEFAULT_ALL_PAGES)

        opts_lay.addLayout(q_row)
        opts_lay.addLayout(dpi_row)
        opts_lay.addWidget(self._all_pages_chk)
        root.addWidget(opts_group)

        # ── Output directory ───────────────────────────────────────────────────
        out_row = QHBoxLayout()
        out_lbl = QLabel("OUTPUT FOLDER")
        out_lbl.setObjectName("section_label")
        self._out_dir_edit = QLineEdit()
        self._out_dir_edit.setReadOnly(True)
        self._out_dir_edit.setPlaceholderText("Same folder as input file")
        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("secondary_btn")
        browse_btn.clicked.connect(self._browse_output_dir)
        out_row.addWidget(out_lbl)
        out_row.addWidget(self._out_dir_edit, stretch=1)
        out_row.addWidget(browse_btn)
        root.addLayout(out_row)

        # ── Action bar ─────────────────────────────────────────────────────────
        action_row = QHBoxLayout()

        self._convert_btn = QPushButton("⚡  Convert Now")
        self._convert_btn.setObjectName("primary_btn")
        self._convert_btn.clicked.connect(self._start_conversion)

        clear_btn = QPushButton("Clear Queue")
        clear_btn.setObjectName("secondary_btn")
        clear_btn.clicked.connect(self._clear_queue)
        self._clear_btn = clear_btn

        open_btn = QPushButton("📂  Open Folder")
        open_btn.setObjectName("secondary_btn")
        open_btn.clicked.connect(self._open_output_folder)

        self._progress = QProgressBar()
        self._progress.setObjectName("conversion_progress")
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(8)
        self._progress.setVisible(False)

        action_row.addWidget(self._convert_btn)
        action_row.addWidget(clear_btn)
        action_row.addWidget(open_btn)
        action_row.addStretch()

        root.addLayout(action_row)
        root.addWidget(self._progress)

        # ── Tool status label ──────────────────────────────────────────────────
        self._tool_status = QLabel("")
        self._tool_status.setWordWrap(True)
        root.addWidget(self._tool_status)

    # ── Settings persistence ───────────────────────────────────────────────────

    def refresh_preferences(self) -> None:
        """Apply Settings-page changes when revisiting Conversion without changing active jobs."""
        if self.has_running_workers() or self._queued_jobs():
            return
        try:
            self._load_settings()
            self._refresh_convert_state()
        except Exception as exc:
            self._tool_status.setText(f"Could not reload conversion preferences: {exc}")

    def _load_settings(self):
        s = settings_repository.get_all()
        self._in_combo.setCurrentText(s.get("input_format", "PNG"))
        self._out_combo.setCurrentText(s.get("output_format", "PDF"))
        self._quality_slider.setValue(int(s.get("quality", DEFAULT_QUALITY)))
        self._density_spin.setValue(int(s.get("density", DEFAULT_DENSITY)))
        self._all_pages_chk.setChecked(s.get("all_pages", "true").lower() == "true")
        out_dir = s.get("output_dir", "")
        if out_dir:
            self._out_dir_edit.setText(out_dir)

    def _save_settings(self):
        settings_repository.set_value("input_format",  self._in_combo.currentText())
        settings_repository.set_value("output_format", self._out_combo.currentText())
        settings_repository.set_value("quality",       str(self._quality_slider.value()))
        settings_repository.set_value("density",       str(self._density_spin.value()))
        settings_repository.set_value("all_pages",     str(self._all_pages_chk.isChecked()).lower())
        settings_repository.set_value("output_dir",    self._out_dir_edit.text())

    # ── Tool status ────────────────────────────────────────────────────────────

    def _refresh_tool_status(self):
        if not self._health.conversion_ok:
            tool_message = "ImageMagick is unavailable. Install it and restart the application."
        elif self._health.ghostscript.found:
            tool_message = (
                f"ImageMagick {self._health.imagemagick.version} · "
                f"Ghostscript {self._health.ghostscript.version}"
            )
        else:
            tool_message = f"ImageMagick {self._health.imagemagick.version} · Ghostscript not detected"

        self._tool_status.setObjectName("status_ok" if self._health.conversion_ok else "status_err")
        self._tool_status.setText(tool_message)
        self._tool_status.style().unpolish(self._tool_status)
        self._tool_status.style().polish(self._tool_status)
        self._refresh_convert_state()

    def _queued_jobs(self) -> list[ConversionJob]:
        return [job for job in self._jobs.values() if job.status == JobStatus.QUEUED]

    @staticmethod
    def _input_is_readable(path: Path) -> bool:
        try:
            if not path.is_file():
                return False
            with path.open("rb"):
                return True
        except OSError:
            return False

    def _output_directory(self, job: ConversionJob) -> Path:
        configured = self._out_dir_edit.text().strip()
        return Path(configured).expanduser() if configured else job.input_path.parent

    def _refresh_convert_state(self):
        queued = self._queued_jobs()
        reason = "Ready to convert."
        valid = True
        if self._batch_active or self.has_running_workers():
            reason, valid = "Conversion is in progress.", False
        elif not queued:
            reason, valid = "Add one or more files to the queue to begin.", False
        elif not self._health.imagemagick.found:
            reason, valid = "Conversion unavailable: ImageMagick was not detected.", False
        else:
            for job in queued:
                if not self._input_is_readable(job.input_path):
                    reason, valid = f"Input file is missing or unreadable: {job.input_path.name}", False
                    break
                if job.input_format not in FORMATS or job.output_format not in FORMATS:
                    reason, valid = f"Unsupported format for {job.input_path.name}.", False
                    break
                if job.input_format == job.output_format:
                    reason, valid = f"Choose a different output format for {job.input_path.name}.", False
                    break
                if (job.input_format in VECTOR_DOC_FORMATS or job.output_format in VECTOR_DOC_FORMATS) and not self._health.ghostscript.found:
                    reason, valid = "PDF, PS, and EPS conversion requires Ghostscript, which was not detected.", False
                    break
                out_dir = self._output_directory(job)
                if not out_dir.is_dir() or not os.access(out_dir, os.W_OK):
                    reason, valid = f"Output folder is missing or not writable: {out_dir}", False
                    break
        self._tool_status.setText(reason if not valid else f"{reason}  {self._health.imagemagick.version}")
        self._tool_status.setObjectName("status_ok" if valid else "status_warn")
        self._tool_status.style().unpolish(self._tool_status)
        self._tool_status.style().polish(self._tool_status)
        self._convert_btn.setEnabled(valid)
        self._clear_btn.setEnabled(not self._batch_active)

    def _update_queued_settings(self, *_args):
        out_fmt = self._out_combo.currentText()
        for job in self._queued_jobs():
            job.output_format = out_fmt
            job.output_path = self._output_directory(job) / f"{job.input_path.stem}.{out_fmt.lower()}"
            job.options.quality = self._quality_slider.value()
            job.options.density = self._density_spin.value()
            job.options.all_pages = self._all_pages_chk.isChecked()
            self._update_queue_row(job)
        self._refresh_convert_state()

    def _update_queue_row(self, job: ConversionJob):
        for row in range(self._queue.rowCount()):
            name_item = self._queue.item(row, _COL_NAME)
            if name_item and name_item.data(Qt.ItemDataRole.UserRole) == job.job_id:
                input_item = self._queue.item(row, _COL_IN_FMT)
                output_item = self._queue.item(row, _COL_OUT_FMT)
                if input_item is not None:
                    input_item.setText(job.input_format)
                if output_item is not None:
                    output_item.setText(job.output_format)
                break

    def _sync_input_format_display(self):
        formats = {job.input_format for job in self._queued_jobs()}
        value = next(iter(formats)) if len(formats) == 1 else ("MIXED" if formats else "PNG")
        if self._in_combo.findText(value) < 0:
            self._in_combo.addItem(value)
        self._in_combo.setCurrentText(value)

    # ── File management ────────────────────────────────────────────────────────

    def _browse_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select files to convert",
            str(Path.home() / "Downloads"),
            "All files (*.*)",
        )
        for p in paths:
            self._enqueue_file(Path(p))

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select output folder", self._out_dir_edit.text() or str(Path.home())
        )
        if d:
            self._out_dir_edit.setText(d)
            settings_repository.set_value("output_dir", d)
            self._update_queued_settings()

    def _open_output_folder(self):
        folder = self._out_dir_edit.text().strip()
        if not folder:
            # Default: parent of the first completed job's output
            for job in self._jobs.values():
                if job.status == JobStatus.COMPLETED:
                    folder = str(job.output_path.parent)
                    break
        if folder and os.path.isdir(folder):
            if os.name == "nt":
                os.startfile(folder)
        else:
            QMessageBox.warning(self, "Folder not found",
                                "No output folder to open yet.")

    def _enqueue_file(self, path: Path):
        if not path.is_file():
            QMessageBox.warning(self, "File not found", f"Not a file:\n{path}")
            return
        ext = path.suffix.lstrip(".").upper() or self._in_combo.currentText()
        row = self._queue.rowCount()
        self._queue.insertRow(row)

        # Determine output path
        out_dir  = Path(self._out_dir_edit.text().strip() or str(path.parent))
        out_fmt  = self._out_combo.currentText()
        out_path = out_dir / f"{path.stem}.{out_fmt.lower()}"

        job = ConversionJob(
            input_path=path,
            output_path=out_path,
            input_format=ext,
            output_format=out_fmt,
            options=ConversionOptions(
                quality   = self._quality_slider.value(),
                density   = self._density_spin.value(),
                all_pages = self._all_pages_chk.isChecked(),
            ),
        )
        self._jobs[job.job_id] = job

        size_mb = path.stat().st_size / (1024 * 1024)

        items = [
            QTableWidgetItem(path.name),
            QTableWidgetItem(ext),
            QTableWidgetItem(out_fmt),
            QTableWidgetItem("Queued"),
            QTableWidgetItem(f"{size_mb:.1f} MB"),
        ]
        items[0].setData(Qt.ItemDataRole.UserRole, job.job_id)
        for col, item in enumerate(items):
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._queue.setItem(row, col, item)

        job_repository.save_job(job)
        self._sync_input_format_display()
        self._refresh_convert_state()

    def _clear_queue(self):
        if self._batch_active or self.has_running_workers():
            return
        self._queue.setRowCount(0)
        self._jobs.clear()
        self._workers.clear()
        self._progress.setVisible(False)
        self._progress.setValue(0)
        self._sync_input_format_display()
        self._refresh_convert_state()

    # ── Conversion ─────────────────────────────────────────────────────────────

    def _start_conversion(self):
        self._refresh_convert_state()
        queued = self._queued_jobs()
        if not self._convert_btn.isEnabled() or not queued:
            return

        self._save_settings()
        self._batch_active = True
        self._refresh_convert_state()
        self._progress.setVisible(True)
        self._progress.setValue(0)

        log_event("batch_started", f"{len(queued)} file(s) queued")
        self._run_next(queued, index=0, total=len(queued))

    def _run_next(self, queue: list[ConversionJob], index: int, total: int):
        if index >= len(queue):
            self._batch_active = False
            self._progress.setValue(100)
            log_event("batch_completed", f"{total} file(s) processed")
            self._refresh_convert_state()
            return

        job = queue[index]
        worker = ConversionWorker(job, self._adapter)
        self._workers.append(worker)

        def on_progress(pct: int):
            # Blend individual file progress with overall batch progress
            overall = int((index / total) * 100 + pct / total)
            self._progress.setValue(min(overall, 99))
            self._update_row_status(job.job_id, f"{pct}%", "#8b949e")

        def on_finished(result: ConversionResult):
            if result.success:
                self._update_row_status(job.job_id, "✓ Done", "#10b981")
                log_event("conversion_completed",
                          f"{job.input_path.name} → {job.output_format}")
            else:
                self._update_row_status(job.job_id, "✗ Failed", "#ef4444")
                log_event("conversion_failed",
                          f"{job.input_path.name}: {result.error_message[:200]}")
            job_repository.update_job_status(
                job.job_id, job.status, job.duration_seconds, job.error_message
            )
            self._workers = [item for item in self._workers if item is not worker]
            self._run_next(queue, index + 1, total)

        def on_error(msg: str):
            job.status = JobStatus.FAILED
            job.error_message = msg
            self._update_row_status(job.job_id, "✗ Error", "#ef4444")
            log_event("conversion_error", msg[:300])
            job_repository.update_job_status(
                job.job_id, job.status, job.duration_seconds, job.error_message
            )
            self._workers = [item for item in self._workers if item is not worker]
            self._run_next(queue, index + 1, total)

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.start()

    def _update_row_status(self, job_id: str, text: str, colour: str):
        for row in range(self._queue.rowCount()):
            item = self._queue.item(row, _COL_NAME)
            if item and item.data(Qt.ItemDataRole.UserRole) == job_id:
                status_item = self._queue.item(row, _COL_STATUS)
                if status_item:
                    status_item.setText(text)
                    status_item.setForeground(
                        __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(colour)
                    )
                break
