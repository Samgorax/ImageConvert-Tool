from __future__ import annotations

import json

import pytest

from core.exceptions import PathTraversalError, PermissionDeniedError
from documents import providers
from documents.providers import OllamaChatProvider
from permissions.audit_log import get_recent_events
from permissions.policy import PermissionPolicy
from storage import database
from workflows.domain import PlannedStep, WorkflowPlan, WorkflowPlanError, WorkflowState
from workflows.output_writer import MAX_REPORT_BYTES, write_report
from workflows.service import approve_step, create_workflow
from workflows.tools import ToolContext, default_tool_registry


def allowed_policy(folder):
    return PermissionPolicy(allow_ai_write_files=True, allowed_output_roots=[str(folder)])


def test_chat_provider_requests_json_mode_only_when_planning(monkeypatch):
    calls = []
    monkeypatch.setattr(providers, "_require_installed", lambda *args: None)
    monkeypatch.setattr(providers, "_post", lambda path, payload, *args, **kwargs: (
        calls.append((path, payload)) or ({"capabilities": ["completion"]}
        if path == "/api/show" else {"message": {"content": '{"title":"Plan","steps":[]}'}}
    )))
    schema = {"type": "object", "required": ["ok"]}
    result = OllamaChatProvider("local-model").answer("system", "task", response_format=schema)
    assert result.startswith("{")
    chat_payload = next(payload for path, payload in calls if path == "/api/chat")
    assert chat_payload["format"] == schema
    assert chat_payload["stream"] is False


@pytest.mark.parametrize(("kind", "content", "expected"), [
    ("txt", "Evidence", "Evidence"),
    ("md", "# Evidence", "# Evidence"),
    ("json", '{"ok":true}', '{"ok":true}'),
])
def test_report_formats_are_written_atomically(tmp_path, kind, content, expected):
    target = write_report(tmp_path, "report", content, kind, allowed_policy(tmp_path))
    assert target.name == f"report.{kind}"
    assert target.read_text(encoding="utf-8") == expected


def test_existing_output_is_never_overwritten(tmp_path):
    destination = tmp_path / "report.txt"
    destination.write_text("user data", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_report(tmp_path, "report.txt", "new", "txt", allowed_policy(tmp_path))
    assert destination.read_text(encoding="utf-8") == "user data"
    assert not list(tmp_path.glob(".sw-report-*"))


def test_output_rejects_traversal_invalid_json_oversize_and_missing_consent(tmp_path):
    with pytest.raises(ValueError, match="base name"):
        write_report(tmp_path, "../escape", "x", "txt", allowed_policy(tmp_path))
    with pytest.raises(json.JSONDecodeError):
        write_report(tmp_path, "bad", "not json", "json", allowed_policy(tmp_path))
    with pytest.raises(ValueError, match="1 MB"):
        write_report(tmp_path, "large", "x" * (MAX_REPORT_BYTES + 1), "txt", allowed_policy(tmp_path))
    with pytest.raises(PermissionDeniedError):
        write_report(tmp_path, "denied", "x", "txt", PermissionPolicy.default())
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    with pytest.raises(PathTraversalError):
        write_report(outside, "report", "x", "txt", allowed_policy(tmp_path))


def test_report_tool_requires_an_earlier_retrieval_and_write_consent(tmp_path):
    registry = default_tool_registry()
    tool_context = ToolContext(output_directory=tmp_path, policy=PermissionPolicy(
        allow_ai_write_files=True, allow_document_access=True, allowed_output_roots=[str(tmp_path)]))
    validated = registry.validate_arguments("write_evidence_report", {
        "source_step": 1, "filename": "evidence", "format": "txt",
    }, 2, tool_context)
    with pytest.raises(ValueError, match="no evidence"):
        registry.get("write_evidence_report").execute(validated, tool_context)
    denied = ToolContext(output_directory=tmp_path, policy=PermissionPolicy.default())
    with pytest.raises(WorkflowPlanError, match="not explicitly enabled"):
        registry.validate_arguments("write_evidence_report", {
            "source_step": 1, "filename": "evidence", "format": "txt",
        }, 2, denied)


def test_report_workflow_requires_each_approval_and_writes_retrieved_evidence(tmp_path, monkeypatch):
    path = tmp_path / "workbench.sqlite3"
    monkeypatch.setattr(database, "_db_file", lambda: path)
    database.initialise_database()
    import workflows.service as service
    import workflows.tools as tools
    from documents.domain import RetrievalHit
    monkeypatch.setattr(tools, "retrieve", lambda *args, **kwargs: (
        RetrievalHit("chunk", "doc-1", "notes.txt", None, None, "verified excerpt", 0.9),
    ))
    monkeypatch.setattr(service, "plan_workflow", lambda *args, **kwargs: WorkflowPlan("Evidence report", (
        PlannedStep(1, "search_documents", {"question": "fact?", "document_ids": ["doc-1"]}),
        PlannedStep(2, "write_evidence_report", {"source_step": 1, "filename": "evidence", "format": "txt"}),
    )))
    policy = PermissionPolicy(allow_ai_suggestions=True, allow_agent_tools=True, allow_ai_write_files=True,
                             allow_document_access=True,
                             allowed_output_roots=[str(tmp_path)])
    run = create_workflow("Report evidence", "local", policy=policy, document_ids=("doc-1",),
                          embedding_model="embed", output_directory=tmp_path)
    first = approve_step(run.run_id, run.steps[0].step_id, approved=True, policy=policy,
                         document_ids=("doc-1",), embedding_model="embed", output_directory=tmp_path)
    assert first.state == WorkflowState.AWAITING_APPROVAL
    assert not (tmp_path / "evidence.txt").exists()
    completed = approve_step(run.run_id, run.steps[1].step_id, approved=True, policy=policy,
                             document_ids=("doc-1",), embedding_model="embed", output_directory=tmp_path)
    assert completed.state == WorkflowState.COMPLETED
    assert (tmp_path / "evidence.txt").is_file()
    assert "verified excerpt" in (tmp_path / "evidence.txt").read_text(encoding="utf-8")
    assert completed.steps[1].result["path"].endswith("evidence.txt")
    assert "workflow_file_created" in [event["event_type"] for event in get_recent_events()]
