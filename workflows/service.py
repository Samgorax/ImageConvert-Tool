"""Approval-gated workflow coordination, persistence, and safe resumption."""
from __future__ import annotations

import uuid
from pathlib import Path
from threading import Event

from core.exceptions import PermissionDeniedError
from permissions.audit_log import log_event
from permissions.enforcer import PermissionEnforcer
from permissions.policy import PermissionPolicy
from storage import workflow_repository

from .domain import (
    StepState,
    WorkflowRunRecord,
    WorkflowState,
    WorkflowStepRecord,
    validate_task,
)
from .planner import plan_workflow
from .tools import ToolContext, ToolRegistry, default_tool_registry


def create_workflow(
    task: str,
    model: str,
    *,
    policy: PermissionPolicy,
    document_ids: tuple[str, ...] = (),
    embedding_model: str = "",
    output_directory: Path | None = None,
    registry: ToolRegistry | None = None,
    cancel: Event | None = None,
) -> WorkflowRunRecord:
    """Plan via local chat, validate the untrusted JSON, and persist for review."""
    enforcer = PermissionEnforcer(policy)
    enforcer.require_ai_suggestions()
    enforcer.require_agent_tools()
    task = validate_task(task)
    registry = registry or default_tool_registry()
    context = ToolContext(
        allowed_document_ids=document_ids,
        embedding_model=embedding_model,
        output_directory=output_directory,
        policy=policy,
        cancel=cancel,
    )
    plan = plan_workflow(task, model, registry, context, cancel)
    if cancel and cancel.is_set():
        raise InterruptedError("Workflow planning cancelled before the plan was saved.")
    run_id = str(uuid.uuid4())
    steps = tuple(WorkflowStepRecord(
        step_id=str(uuid.uuid4()), run_id=run_id, ordinal=item.ordinal,
        tool_id=item.tool_id, arguments=item.arguments, state=StepState.AWAITING_APPROVAL,
        requires_approval=registry.get(item.tool_id).requires_approval,
    ) for item in plan.steps)
    run = WorkflowRunRecord(
        run_id=run_id, task=task, model=model, title=plan.title,
        state=WorkflowState.AWAITING_APPROVAL, steps=steps,
    )
    workflow_repository.create_run(run, plan.title)
    log_event("workflow_planned", f"run_id={run_id}; steps={len(steps)}")
    return run


def get_workflow(run_id: str) -> WorkflowRunRecord | None:
    """Load a persisted run; AWAITING_APPROVAL runs are safely resumable after restart."""
    return workflow_repository.get_run(run_id)


def list_workflows(limit: int = 100) -> list[WorkflowRunRecord]:
    return workflow_repository.list_runs(limit)


def approve_step(
    run_id: str,
    step_id: str,
    *,
    approved: bool,
    policy: PermissionPolicy,
    document_ids: tuple[str, ...] = (),
    embedding_model: str = "",
    output_directory: Path | None = None,
    registry: ToolRegistry | None = None,
    cancel: Event | None = None,
) -> WorkflowRunRecord:
    """Approve and execute one step; every step requires a fresh explicit approval."""
    run = workflow_repository.get_run(run_id)
    if run is None:
        raise ValueError("Workflow run no longer exists.")
    step = next((candidate for candidate in run.steps if candidate.step_id == step_id), None)
    if step is None:
        raise ValueError("Workflow step does not belong to this run.")
    if step.state != StepState.AWAITING_APPROVAL or run.state not in {
        WorkflowState.AWAITING_APPROVAL, WorkflowState.RUNNING,
    }:
        raise ValueError("Workflow step is not awaiting approval.")
    if any(previous.state != StepState.COMPLETED for previous in run.steps if previous.ordinal < step.ordinal):
        raise ValueError("Workflow steps must be approved and completed in order.")

    if not approved:
        workflow_repository.update_step(
            step_id, StepState.CANCELLED, approval_decision="denied", error_message="Approval denied by the user."
        )
        workflow_repository.update_run(run_id, WorkflowState.CANCELLED, "A required workflow step was denied.")
        log_event("workflow_step_denied", f"run_id={run_id}; step={step.ordinal}")
        return workflow_repository.get_run(run_id)  # type: ignore[return-value]

    try:
        enforcer = PermissionEnforcer(policy)
        enforcer.require_agent_tools()
        enforcer.require_document_access()
        if step.tool_id == "write_evidence_report":
            enforcer.require_ai_write_files()
    except PermissionDeniedError as exc:
        workflow_repository.update_step(
            step_id, StepState.CANCELLED, approval_decision="policy_denied", error_message=str(exc)
        )
        workflow_repository.update_run(run_id, WorkflowState.CANCELLED, str(exc))
        log_event("workflow_step_policy_denied", f"run_id={run_id}; step={step.ordinal}")
        return workflow_repository.get_run(run_id)  # type: ignore[return-value]

    if cancel and cancel.is_set():
        workflow_repository.update_step(
            step_id, StepState.CANCELLED, approval_decision="approved", error_message="Workflow cancelled before execution."
        )
        workflow_repository.update_run(run_id, WorkflowState.CANCELLED, "Workflow cancelled.")
        log_event("workflow_cancelled", f"run_id={run_id}; step={step.ordinal}")
        return workflow_repository.get_run(run_id)  # type: ignore[return-value]

    if not workflow_repository.claim_step(step_id):
        raise ValueError("Workflow step was already claimed or is no longer awaiting approval.")
    workflow_repository.update_run(run_id, WorkflowState.RUNNING)
    registry = registry or default_tool_registry()
    completed = [item for item in run.steps if item.state == StepState.COMPLETED and item.result is not None]
    context = ToolContext(
        allowed_document_ids=document_ids,
        embedding_model=embedding_model,
        output_directory=output_directory,
        policy=policy,
        previous_results={item.ordinal: item.result for item in completed if item.result is not None},
        cancel=cancel,
    )
    try:
        if cancel and cancel.is_set():
            raise InterruptedError("Workflow cancelled before tool execution.")
        tool = registry.get(step.tool_id)
        validated = registry.validate_arguments(step.tool_id, step.arguments, step.ordinal, context)
        result = tool.execute(validated, context)
        workflow_repository.update_step(
            step_id, StepState.COMPLETED, approval_decision="approved", result=result,
        )
        updated = workflow_repository.get_run(run_id)
        if updated is None:
            raise ValueError("Workflow disappeared after step execution.")
        all_complete = all(item.state == StepState.COMPLETED for item in updated.steps)
        workflow_repository.update_run(run_id, WorkflowState.COMPLETED if all_complete else WorkflowState.AWAITING_APPROVAL)
        log_event("workflow_step_completed", f"run_id={run_id}; step={step.ordinal}; tool={step.tool_id}")
    except InterruptedError as exc:
        workflow_repository.update_step(
            step_id, StepState.CANCELLED, approval_decision="approved", error_message=str(exc)
        )
        workflow_repository.update_run(run_id, WorkflowState.CANCELLED, str(exc))
        log_event("workflow_cancelled", f"run_id={run_id}; step={step.ordinal}")
    except Exception as exc:
        workflow_repository.update_step(
            step_id, StepState.FAILED, approval_decision="approved", error_message=str(exc)
        )
        workflow_repository.update_run(run_id, WorkflowState.FAILED, str(exc))
        log_event("workflow_step_failed", f"run_id={run_id}; step={step.ordinal}; error={type(exc).__name__}")
    result_run = workflow_repository.get_run(run_id)
    if result_run is None:
        raise ValueError("Workflow disappeared after execution.")
    return result_run
