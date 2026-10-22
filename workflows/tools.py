"""Small allowlisted workflow tool registry; no shell or arbitrary code tools."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Any

from documents.service import retrieve
from permissions.policy import PermissionPolicy

from .domain import WorkflowPlanError
from .output_writer import write_report


@dataclass
class ToolContext:
    allowed_document_ids: tuple[str, ...] = ()
    embedding_model: str = ""
    output_directory: Path | None = None
    policy: PermissionPolicy = field(default_factory=PermissionPolicy.default)
    previous_results: dict[int, dict[str, Any]] = field(default_factory=dict)
    cancel: Event | None = None


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    description: str
    validate: Callable[[dict[str, Any], int, ToolContext], dict[str, Any]]
    execute: Callable[[dict[str, Any], ToolContext], dict[str, Any]]
    requires_approval: bool = True
    arguments_schema: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.tool_id in self._tools:
            raise ValueError(f"Tool {tool.tool_id!r} is already registered.")
        self._tools[tool.tool_id] = tool

    def get(self, tool_id: str) -> ToolDefinition:
        try:
            return self._tools[tool_id]
        except KeyError as exc:
            raise WorkflowPlanError(f"Tool {tool_id!r} is not allowlisted.") from exc

    def validate_arguments(self, tool_id: str, arguments: dict[str, Any], ordinal: int, context: ToolContext) -> dict[str, Any]:
        return self.get(tool_id).validate(arguments, ordinal, context)

    def descriptions(self, context: ToolContext) -> list[dict[str, Any]]:
        visible: list[dict[str, Any]] = []
        for tool in self._tools.values():
            if tool.tool_id == "search_documents" and (
                not context.allowed_document_ids or not context.embedding_model
                or not context.policy.allow_document_access
            ):
                continue
            if tool.tool_id == "write_evidence_report" and (
                context.output_directory is None or not context.policy.allow_ai_write_files
                or not context.policy.allowed_output_roots or not context.policy.allow_document_access
            ):
                continue
            visible.append({
                "tool": tool.tool_id,
                "description": tool.description,
                "arguments_schema": tool.arguments_schema,
            })
        return visible


def _validate_search(arguments: dict[str, Any], _ordinal: int, context: ToolContext) -> dict[str, Any]:
    if set(arguments) != {"question", "document_ids"}:
        raise WorkflowPlanError("search_documents accepts only question and document_ids.")
    question = arguments["question"]
    document_ids = arguments["document_ids"]
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise WorkflowPlanError("Document search question must contain 1 to 4000 characters.")
    if (not isinstance(document_ids, list) or not document_ids or len(document_ids) > 20
            or any(not isinstance(item, str) for item in document_ids)):
        raise WorkflowPlanError("Document search requires 1 to 20 document IDs.")
    if len(set(document_ids)) != len(document_ids) or not set(document_ids).issubset(context.allowed_document_ids):
        raise WorkflowPlanError("The plan requested a document outside the user-selected document scope.")
    return {"question": question.strip(), "document_ids": document_ids}


def _search_documents(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    if context.cancel and context.cancel.is_set():
        raise InterruptedError("Workflow cancelled before document retrieval.")
    hits = retrieve(arguments["question"], context.embedding_model,
                    tuple(arguments["document_ids"]), policy=context.policy)
    return {
        "hits": [
            {
                "document_id": hit.document_id,
                "source": hit.filename,
                "page": hit.page_number,
                "section": hit.section,
                "excerpt": hit.text,
                "similarity": hit.cosine_similarity,
            }
            for hit in hits
        ]
    }


def _validate_report(arguments: dict[str, Any], ordinal: int, context: ToolContext) -> dict[str, Any]:
    if set(arguments) != {"source_step", "filename", "format"}:
        raise WorkflowPlanError("write_evidence_report accepts only source_step, filename, and format.")
    source_step, filename, file_format = arguments["source_step"], arguments["filename"], arguments["format"]
    if not isinstance(source_step, int) or source_step < 1 or source_step >= ordinal:
        raise WorkflowPlanError("Report source_step must refer to an earlier completed step.")
    if not isinstance(filename, str) or not filename.strip() or len(filename) > 120:
        raise WorkflowPlanError("Report filename must be 1 to 120 characters.")
    if file_format not in {"txt", "md", "json"}:
        raise WorkflowPlanError("Only TXT, Markdown, and JSON reports are supported.")
    if (context.output_directory is None or not context.policy.allow_ai_write_files
            or not context.policy.allow_document_access):
        raise WorkflowPlanError("Report creation was not explicitly enabled for this session.")
    return {"source_step": source_step, "filename": filename.strip(), "format": file_format}


def _create_evidence_report(arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    hits = context.previous_results.get(arguments["source_step"], {}).get("hits", [])
    if not isinstance(hits, list) or not hits:
        raise ValueError("The approved retrieval step returned no evidence; no report was created.")
    if arguments["format"] == "json":
        content = __import__("json").dumps({"evidence": hits}, ensure_ascii=False, indent=2)
    elif arguments["format"] == "md":
        content = "# Local document evidence\n\n" + "\n\n".join(
            f"## {item['source']}\n\n{item['excerpt']}" for item in hits
        )
    else:
        content = "LOCAL DOCUMENT EVIDENCE\n\n" + "\n\n".join(
            f"Source: {item['source']}\nExcerpt: {item['excerpt']}" for item in hits
        )
    output = write_report(context.output_directory, arguments["filename"], content,
                          arguments["format"], context.policy)
    return {"path": str(output), "format": arguments["format"], "bytes": len(content.encode("utf-8"))}


def default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        tool_id="search_documents",
        description="Retrieve relevant passages from only the documents selected by the user.",
        validate=_validate_search,
        execute=_search_documents,
        arguments_schema={
            "type": "object", "required": ["question", "document_ids"], "additionalProperties": False,
            "properties": {
                "question": {"type": "string", "minLength": 1, "maxLength": 4000},
                "document_ids": {"type": "array", "minItems": 1, "maxItems": 20,
                                 "items": {"type": "string"}},
            },
        },
    ))
    registry.register(ToolDefinition(
        tool_id="write_evidence_report",
        description="Create a TXT, Markdown, or JSON report from an earlier approved retrieval result.",
        validate=_validate_report,
        execute=_create_evidence_report,
        arguments_schema={
            "type": "object", "required": ["source_step", "filename", "format"],
            "additionalProperties": False,
            "properties": {
                "source_step": {"type": "integer", "minimum": 1},
                "filename": {"type": "string", "minLength": 1, "maxLength": 120},
                "format": {"type": "string", "enum": ["txt", "md", "json"]},
            },
        },
    ))
    return registry
