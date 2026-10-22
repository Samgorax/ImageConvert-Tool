"""Application entry point for the Sovereign Workstation desktop UI."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from core.config import APP_NAME
from storage.database import initialise_database
from ui.main_window import WorkbenchWindow as WorkstationWindow
from ui.theme import apply_theme

_log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Initialise local storage and launch the Sovereign Workbench."""
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("SamGorax")

    try:
        initialise_database()
        apply_theme(app)
        window = WorkstationWindow()
        window.show()
    except Exception as exc:
        _log.exception("Application startup failed")
        QMessageBox.critical(None, "Application startup failed", str(exc))
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
