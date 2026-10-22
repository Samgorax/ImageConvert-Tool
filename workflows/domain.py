"""Typed workflow records and strict model-plan parsing."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

MAX_TASK_CHARS = 4000
MAX_PLAN_CHARS = 64_000
MAX_WORKFLOW_STEPS = 8


class WorkflowState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class PlannedStep:
    ordinal: int
    tool_id: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class WorkflowPlan:
    title: str
    steps: tuple[PlannedStep, ...]


@dataclass(frozen=True)
class WorkflowStepRecord:
    step_id: str
    run_id: str
    ordinal: int
    tool_id: str
    arguments: dict[str, Any]
    state: StepState
    requires_approval: bool = True
    approval_decision: str = "pending"
    result: dict[str, Any] | None = None
    error_message: str = ""


@dataclass(frozen=True)
class WorkflowRunRecord:
    run_id: str
    task: str
    model: str
    title: str
    state: WorkflowState
    steps: tuple[WorkflowStepRecord, ...]
    error_message: str = ""


class WorkflowPlanError(ValueError):
    """A local model plan was malformed or requested disallowed work."""


def validate_task(task: str) -> str:
    value = task.strip()
    if not value or len(value) > MAX_TASK_CHARS:
        raise WorkflowPlanError(f"Task must contain 1 to {MAX_TASK_CHARS} characters.")
    return value


def parse_plan(raw: str, validate_tool_arguments) -> WorkflowPlan:
    """Parse untrusted planner JSON and validate every tool and argument."""
    if len(raw) > MAX_PLAN_CHARS:
        raise WorkflowPlanError("The generated plan exceeds the configured size limit.")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise WorkflowPlanError("The local model did not return a valid JSON workflow plan.") from exc
    if not isinstance(value, dict) or set(value) != {"title", "steps"}:
        raise WorkflowPlanError("A plan must contain only 'title' and 'steps'.")
    title = value["title"]
    raw_steps = value["steps"]
    if not isinstance(title, str) or not title.strip() or len(title) > 160:
        raise WorkflowPlanError("Plan title must contain 1 to 160 characters.")
    if not isinstance(raw_steps, list) or not raw_steps or len(raw_steps) > MAX_WORKFLOW_STEPS:
        raise WorkflowPlanError(f"A plan must contain 1 to {MAX_WORKFLOW_STEPS} steps.")
    steps: list[PlannedStep] = []
    for ordinal, item in enumerate(raw_steps, 1):
        if not isinstance(item, dict) or set(item) != {"tool", "arguments"}:
            raise WorkflowPlanError(f"Step {ordinal} must contain only 'tool' and 'arguments'.")
        tool_id, arguments = item["tool"], item["arguments"]
        if not isinstance(tool_id, str) or not isinstance(arguments, dict):
            raise WorkflowPlanError(f"Step {ordinal} has an invalid tool or arguments object.")
        validated = validate_tool_arguments(tool_id, arguments, ordinal)
        steps.append(PlannedStep(ordinal, tool_id, validated))
    return WorkflowPlan(title.strip(), tuple(steps))
