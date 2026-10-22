"""
storage/database.py
====================
SQLite database bootstrap.  Creates the schema on first launch and provides
the single ``get_connection()`` factory used across all repositories.

Design choices:
- WAL journal mode: better read concurrency; safe for our single-writer use case.
- ``foreign_keys = ON``: enforces referential integrity even though we use it only lightly.
- ``row_factory = sqlite3.Row``: lets callers access columns by name.
- Schema version table: makes forward migrations explicit and trackable.
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from core.config import DB_PATH

_log = logging.getLogger(__name__)

SCHEMA_VERSION = 3

_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version  INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS conversion_jobs (
    job_id          TEXT    PRIMARY KEY,
    input_path      TEXT    NOT NULL,
    output_path     TEXT    NOT NULL,
    input_format    TEXT    NOT NULL,
    output_format   TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'QUEUED',
    quality         INTEGER,
    density         INTEGER,
    all_pages       INTEGER,
    duration_sec    REAL,
    error_message   TEXT,
    created_at      TEXT    NOT NULL,
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,
    details     TEXT,
    actor       TEXT    NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    extension TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    status TEXT NOT NULL,
    page_count INTEGER,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    embedding_model TEXT NOT NULL DEFAULT '',
    embedding_dimensions INTEGER,
    extractor TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    text TEXT NOT NULL,
    page_number INTEGER,
    section TEXT,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    embedding_json TEXT,
    embedding_model TEXT NOT NULL DEFAULT '',
    UNIQUE(document_id, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_document_chunks_document ON document_chunks(document_id, ordinal);

CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    task TEXT NOT NULL,
    model TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_message TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS workflow_steps (
    step_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES workflow_runs(run_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    tool_id TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    state TEXT NOT NULL,
    requires_approval INTEGER NOT NULL,
    approval_decision TEXT NOT NULL DEFAULT 'pending',
    result_json TEXT,
    error_message TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    UNIQUE(run_id, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_run ON workflow_steps(run_id, ordinal);
"""


def _db_file() -> Path:
    return Path(DB_PATH)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """
    Open (and initialise if needed) the application SQLite database.

    The yielded connection uses ``row_factory = sqlite3.Row`` so columns
    are accessible by name. The connection commits or rolls back with the
    context and is always closed when the context exits.
    """
    db_file = _db_file()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialise_database() -> None:
    """Create or additively upgrade schema; existing conversion/user data is retained."""
    _log.info("Initialising database at %s", _db_file())
    with get_connection() as conn:
        conn.executescript(_SCHEMA_SQL)
        existing = conn.execute("SELECT MAX(version) AS version FROM schema_version").fetchone()
        version = existing["version"] or 0
        if version < 1:
            conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        if version < 2:
            conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (2)")
            _log.info("Database schema migrated additively to v2.")
        if version < 3:
            conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (3)")
            _log.info("Database schema migrated additively to v3.")
