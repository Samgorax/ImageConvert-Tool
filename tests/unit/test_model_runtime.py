from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

from engine.model_runtime import probe_local_model_runtimes


def test_runtime_probe_reports_absent_local_runtimes(monkeypatch):
    monkeypatch.setattr("engine.model_runtime.shutil.which", lambda _name: None)

    inventory = probe_local_model_runtimes()

    assert [(runtime.name, runtime.available) for runtime in inventory.runtimes] == [
        ("Ollama", False),
        ("llama.cpp", False),
    ]
    assert all(runtime.message for runtime in inventory.runtimes)


def test_ollama_model_inventory_is_read_from_local_cli(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.setattr(
        "engine.model_runtime.shutil.which",
        lambda name: "C:/tools/ollama.exe" if name == "ollama" else None,
    )

    def fake_run(args, **_kwargs):
        if args[-1] == "--version":
            return subprocess.CompletedProcess(args, 0, "ollama version is 0.13.1", "")
        return subprocess.CompletedProcess(
            args,
            0,
            "NAME                  ID       SIZE    MODIFIED\nqwen2.5:latest        abc123   5 GB    2 days ago\n",
            "",
        )

    monkeypatch.setattr("engine.model_runtime.subprocess.run", fake_run)
    inventory = probe_local_model_runtimes()
    ollama = inventory.runtimes[0]

    assert ollama.available
    assert ollama.version == "ollama version is 0.13.1"
    assert ollama.models == ("qwen2.5:latest",)
    assert ollama.inventory_supported


def test_ollama_unavailable_inventory_is_not_reported_as_empty_models(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.setattr(
        "engine.model_runtime.shutil.which",
        lambda name: "ollama" if name == "ollama" else None,
    )
    run = MagicMock(
        side_effect=[
            subprocess.CompletedProcess(["ollama", "--version"], 0, "0.13.1", ""),
            subprocess.CompletedProcess(["ollama", "list"], 1, "", "daemon unavailable"),
        ]
    )
    monkeypatch.setattr("engine.model_runtime.subprocess.run", run)

    ollama = probe_local_model_runtimes().runtimes[0]

    assert ollama.available
    assert ollama.models == ()
    assert "daemon unavailable" in ollama.message


def test_remote_ollama_host_skips_model_inventory_query(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "https://models.example.test:11434")
    monkeypatch.setattr(
        "engine.model_runtime.shutil.which",
        lambda name: "ollama" if name == "ollama" else None,
    )
    run = MagicMock(
        return_value=subprocess.CompletedProcess(["ollama", "--version"], 0, "0.13.1", "")
    )
    monkeypatch.setattr("engine.model_runtime.subprocess.run", run)

    ollama = probe_local_model_runtimes().runtimes[0]

    assert ollama.available
    assert not ollama.models
    assert "non-local" in ollama.message
    run.assert_called_once()
