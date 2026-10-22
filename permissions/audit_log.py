"""
permissions/audit_log.py
========================
Write-only audit trail for all privileged operations.

Every sensitive action — file write, batch start, future AI execution —
should call ``log_event()`` so there is an immutable trace in the database.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from storage.database import get_connection

_log = logging.getLogger(__name__)


def log_event(
    event_type: str,
    details:    str = "",
    actor:      str = "user",
) -> None:
    """
    Append an entry to the audit_log table.

    Parameters
    ----------
    event_type : str
        Short snake_case label, e.g. ``"conversion_started"``,
        ``"batch_queued"``, ``"ai_action_approved"``.
    details : str
        Free-form context (file paths, error snippet, etc.).
    actor : str
        ``"user"`` for user-initiated actions, ``"ai"`` for AI-driven ones.
    """
    ts = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (timestamp, event_type, details, actor)
            VALUES (?, ?, ?, ?)
            """,
            (ts, event_type, details or None, actor),
        )
    _log.debug("Audit: [%s] %s — %s", actor, event_type, details[:80] if details else "")


def get_recent_events(limit: int = 200) -> list[dict]:
    """Return the most recent *limit* audit entries (newest first)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
