"""
storage/job_repository.py
==========================
CRUD operations for ConversionJob records in SQLite.
All functions open and close their own connection via ``get_connection()``.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from engine.job import ConversionJob, JobStatus
from storage.database import get_connection

_log = logging.getLogger(__name__)


def save_job(job: ConversionJob) -> None:
    """Insert or update a ConversionJob record."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO conversion_jobs
                (job_id, input_path, output_path, input_format, output_format,
                 status, quality, density, all_pages, duration_sec,
                 error_message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id,
                str(job.input_path),
                str(job.output_path),
                job.input_format,
                job.output_format,
                job.status.name,
                job.options.quality,
                job.options.density,
                int(job.options.all_pages),
                job.duration_seconds or None,
                job.error_message or None,
                job.created_at.isoformat(),
            ),
        )
    _log.debug("Saved job %s (status=%s)", job.job_id[:8], job.status.name)


def update_job_status(
    job_id: str,
    status: JobStatus,
    duration_sec: float = 0.0,
    error_message: str = "",
) -> None:
    """Update only the mutable outcome fields of an existing record."""
    completed_at = (
        datetime.now(UTC).isoformat()
        if status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
        else None
    )
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE conversion_jobs
               SET status = ?, duration_sec = ?, error_message = ?, completed_at = ?
             WHERE job_id = ?
            """,
            (status.name, duration_sec, error_message or None, completed_at, job_id),
        )


def list_jobs(limit: int = 500) -> list[dict]:
    """Return the *limit* most recent job records as plain dicts."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM conversion_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_job(job_id: str) -> None:
    """Permanently remove a single job record."""
    with get_connection() as conn:
        conn.execute("DELETE FROM conversion_jobs WHERE job_id = ?", (job_id,))


def clear_all_jobs() -> int:
    """Delete all job records.  Returns the number of rows deleted."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM conversion_jobs")
        return cur.rowcount
