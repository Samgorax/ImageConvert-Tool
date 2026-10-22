"""
storage/settings_repository.py
================================
Persisted user preferences backed by the ``settings`` SQLite table.
Falls back to ``_DEFAULTS`` for any key that has not been explicitly set.
"""
from __future__ import annotations

import logging

from storage.database import get_connection

_log = logging.getLogger(__name__)

_DEFAULTS: dict[str, str] = {
    "output_dir":      "",        # empty → use input file's directory
    "input_format":    "PNG",
    "output_format":   "PDF",
    "quality":         "95",
    "density":         "300",
    "all_pages":       "true",
    "theme":           "dark",
    "window_geometry": "",
    "window_state":    "",
    "local_embedding_model": "",
    "local_chat_model": "",
    # Persistent capability ceilings. Page-level consent is still required for every session.
    "policy_allow_document_access": "false",
    "policy_allow_ai_suggestions": "false",
    "policy_allow_agent_tools": "false",
    "policy_allow_ai_write_files": "false",
}


def get(key: str) -> str:
    """Return the value for *key*, falling back to its default."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
    if row:
        return row["value"]
    default = _DEFAULTS.get(key, "")
    _log.debug("Settings key %r not found, using default %r", key, default)
    return default


def set_value(key: str, value: str) -> None:
    """Persist *key* = *value*."""
    set_values({key: value})


def set_values(values: dict[str, str]) -> None:
    """Persist a preference group atomically in one SQLite transaction."""
    with get_connection() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            [(key, str(value)) for key, value in values.items()],
        )
    _log.debug("Settings updated for keys: %s", ", ".join(values))


def get_bool(key: str) -> bool:
    """Read a persisted boolean preference; unknown values fail closed."""
    value = get(key).strip().casefold()
    return value in {"1", "true", "yes", "on"}


def get_all() -> dict[str, str]:
    """Return all settings merged with defaults (persisted values win)."""
    result = dict(_DEFAULTS)
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    for row in rows:
        result[row["key"]] = row["value"]
    return result


def reset_to_defaults() -> None:
    """Wipe all persisted settings (restores factory defaults on next read)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM settings")
