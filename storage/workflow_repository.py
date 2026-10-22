"""SQLite persistence for workflow runs and audited step state."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from storage.database import get_connection
from workflows.domain import (
    StepState,
    WorkflowRunRecord,
    WorkflowState,
    WorkflowStepRecord,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def create_run(run: WorkflowRunRecord, title: str) -> None:
    timestamp = _now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO workflow_runs(run_id,title,task,model,state,created_at,updated_at,error_message)
               VALUES(?,?,?,?,?,?,?,?)""",
            (run.run_id, title, run.task, run.model, run.state.value, timestamp, timestamp, run.error_message),
        )
        conn.executemany(
            """INSERT INTO workflow_steps(step_id,run_id,ordinal,tool_id,arguments_json,state,
               requires_approval,approval_decision,result_json,error_message,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            [(
                step.step_id, step.run_id, step.ordinal, step.tool_id,
                json.dumps(step.arguments, ensure_ascii=False, allow_nan=False), step.state.value,
                int(step.requires_approval), step.approval_decision,
                json.dumps(step.result, ensure_ascii=False, allow_nan=False) if step.result is not None else None,
                step.error_message, timestamp,
            ) for step in run.steps],
        )


def get_run(run_id: str) -> WorkflowRunRecord | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            return None
        steps = conn.execute(
            "SELECT * FROM workflow_steps WHERE run_id=? ORDER BY ordinal", (run_id,)
        ).fetchall()
    return WorkflowRunRecord(
        run_id=row["run_id"], task=row["task"], model=row["model"], title=row["title"],
        state=WorkflowState(row["state"]), error_message=row["error_message"],
        steps=tuple(_step(item) for item in steps),
    )


def list_runs(limit: int = 100) -> list[WorkflowRunRecord]:
    with get_connection() as conn:
        ids = conn.execute(
            "SELECT run_id FROM workflow_runs ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 500)),),
        ).fetchall()
    return [run for row in ids if (run := get_run(row["run_id"])) is not None]


def claim_step(step_id: str) -> bool:
    """Atomically claim an approved step once; prevents duplicate concurrent execution."""
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE workflow_steps SET state=?,approval_decision='approved',updated_at=?
               WHERE step_id=? AND state=? AND requires_approval=1""",
            (StepState.RUNNING.value, _now(), step_id, StepState.AWAITING_APPROVAL.value),
        )
    return cursor.rowcount == 1


def update_step(
    step_id: str,
    state: StepState,
    *,
    approval_decision: str,
    result: dict | None = None,
    error_message: str = "",
) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """UPDATE workflow_steps SET state=?,approval_decision=?,result_json=?,error_message=?,updated_at=?
               WHERE step_id=?""",
            (state.value, approval_decision,
             json.dumps(result, ensure_ascii=False, allow_nan=False) if result is not None else None,
             error_message[:1000], _now(), step_id),
        )
    return cursor.rowcount == 1


def update_run(run_id: str, state: WorkflowState, error_message: str = "") -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE workflow_runs SET state=?,error_message=?,updated_at=? WHERE run_id=?",
            (state.value, error_message[:1000], _now(), run_id),
        )
    return cursor.rowcount == 1


def _step(row) -> WorkflowStepRecord:
    return WorkflowStepRecord(
        step_id=row["step_id"], run_id=row["run_id"], ordinal=row["ordinal"], tool_id=row["tool_id"],
        arguments=json.loads(row["arguments_json"]), state=StepState(row["state"]),
        requires_approval=bool(row["requires_approval"]), approval_decision=row["approval_decision"],
        result=json.loads(row["result_json"]) if row["result_json"] else None,
        error_message=row["error_message"],
    )
