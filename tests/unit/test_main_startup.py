from __future__ import annotations

from unittest.mock import MagicMock

import main


def test_main_initialises_local_app_and_uses_real_health_check(monkeypatch):
    calls: list[str] = []

    class FakeApplication:
        @staticmethod
        def instance():
            return None

        def __init__(self, _argv):
            calls.append("application")

        def setApplicationName(self, _name):
            pass

        def setOrganizationName(self, _name):
            pass

        def exec(self):
            calls.append("exec")
            return 23

    class FakeWindow:
        def __init__(self):
            calls.append("window")

        def show(self):
            calls.append("show")

    monkeypatch.setattr(main, "QApplication", FakeApplication)
    monkeypatch.setattr(main, "initialise_database", lambda: calls.append("database"))
    monkeypatch.setattr(main, "apply_theme", lambda _app: calls.append("theme"))
    monkeypatch.setattr(main, "WorkstationWindow", FakeWindow)

    assert main.main(["workstation"]) == 23
    assert calls == ["application", "database", "theme", "window", "show", "exec"]


def test_main_reports_startup_errors(monkeypatch):
    critical = MagicMock()

    class FakeApplication:
        @staticmethod
        def instance():
            return None

        def __init__(self, _argv):
            pass

        def setApplicationName(self, _name):
            pass

        def setOrganizationName(self, _name):
            pass

    monkeypatch.setattr(main, "QApplication", FakeApplication)
    monkeypatch.setattr(main, "initialise_database", lambda: (_ for _ in ()).throw(OSError("read-only")))
    monkeypatch.setattr(main.QMessageBox, "critical", critical)

    assert main.main(["workstation"]) == 1
    critical.assert_called_once()
    assert "read-only" in critical.call_args.args[2]
