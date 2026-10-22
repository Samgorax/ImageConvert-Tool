from __future__ import annotations

import threading

import ui.workers.health_check_worker as worker_module
from engine.health_check import HealthReport
from ui.workers.health_check_worker import HealthCheckWorker


def test_health_probe_runs_in_background_thread(monkeypatch):
    caller_thread = threading.get_ident()
    observed_threads: list[int] = []
    monkeypatch.setattr(
        worker_module,
        "run_health_check",
        lambda: (observed_threads.append(threading.get_ident()) or HealthReport()),
    )

    worker = HealthCheckWorker()
    worker.start()
    assert worker.wait(5000)

    assert observed_threads
    assert observed_threads[0] != caller_thread
    assert not worker.isRunning()
