"""Read-only discovery of local model runtimes and their visible models."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit

_log = logging.getLogger(__name__)
_PROBE_TIMEOUT_SECONDS = 3


@dataclass(frozen=True)
class RuntimeStatus:
    name: str
    available: bool
    executable: str = ""
    version: str = ""
    models: tuple[str, ...] = ()
    inventory_supported: bool = False
    message: str = ""


@dataclass(frozen=True)
class RuntimeInventory:
    runtimes: tuple[RuntimeStatus, ...]


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def _run(executable: str, *args: str) -> subprocess.CompletedProcess[str]:
    command = [executable, *args]
    if sys.platform == "win32":
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=_PROBE_TIMEOUT_SECONDS,
        check=False,
    )


def _ollama_host_is_local(value: str) -> bool:
    """Accept Ollama's default/local endpoint forms and reject remote hosts."""
    if not value:
        return True  # Ollama's default endpoint is loopback.
    parsed = urlsplit(value if "://" in value else f"//{value}")
    hostname = (parsed.hostname or "").strip("[]").lower()
    if hostname == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


def _ollama_status(executable: str | None) -> RuntimeStatus:
    if not executable:
        return RuntimeStatus(
            "Ollama", False, inventory_supported=True, message="Not detected on PATH."
        )

    try:
        version_result = _run(executable, "--version")
        version = _first_line(version_result.stdout or version_result.stderr)
        configured_host = os.environ.get("OLLAMA_HOST", "")
        if not _ollama_host_is_local(configured_host):
            return RuntimeStatus(
                "Ollama",
                True,
                executable,
                version,
                inventory_supported=True,
                message="OLLAMA_HOST is non-local; model inventory query skipped.",
            )
        models_result = _run(executable, "list")
        if models_result.returncode != 0:
            message = _first_line(models_result.stderr or models_result.stdout)
            return RuntimeStatus(
                "Ollama",
                True,
                executable,
                version,
                inventory_supported=True,
                message=message or "Runtime found; model inventory query failed.",
            )
        rows = [line.strip() for line in models_result.stdout.splitlines() if line.strip()]
        models = tuple(line.split()[0] for line in rows[1:] if line.split())
        return RuntimeStatus(
            "Ollama",
            True,
            executable,
            version,
            models,
            inventory_supported=True,
            message="Local model inventory available.",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.info("Ollama inventory probe unavailable: %s", exc)
        return RuntimeStatus(
            "Ollama",
            True,
            executable,
            inventory_supported=True,
            message=f"Runtime found; local inventory unavailable: {exc}",
        )


def _llama_cpp_status(executable: str | None) -> RuntimeStatus:
    if not executable:
        return RuntimeStatus(
            "llama.cpp",
            False,
            inventory_supported=False,
            message="CLI not detected on PATH.",
        )
    try:
        result = _run(executable, "--version")
        version = _first_line(result.stdout or result.stderr)
        message = "This CLI does not expose a general installed-model inventory."
        return RuntimeStatus(
            "llama.cpp",
            True,
            executable,
            version,
            inventory_supported=False,
            message=message,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.info("llama.cpp version probe unavailable: %s", exc)
        return RuntimeStatus(
            "llama.cpp",
            True,
            executable,
            inventory_supported=False,
            message=f"CLI found; version probe unavailable: {exc}",
        )


def probe_local_model_runtimes() -> RuntimeInventory:
    """Probe supported local runtimes without downloading or invoking a model."""
    ollama = shutil.which("ollama")
    llama = next(
        (path for name in ("llama-cli", "llama-server") if (path := shutil.which(name))),
        None,
    )
    return RuntimeInventory((_ollama_status(ollama), _llama_cpp_status(llama)))
