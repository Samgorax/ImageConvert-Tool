"""Typed domain records shared by document extraction, storage, and RAG."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class DocumentStatus(StrEnum):
    IMPORTED = "IMPORTED"
    EXTRACTING = "EXTRACTING"
    AWAITING_EMBEDDING = "AWAITING_EMBEDDING"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class TextBlock:
    text: str
    page_number: int | None = None
    section: str | None = None


@dataclass(frozen=True)
class ExtractionResult:
    blocks: tuple[TextBlock, ...]
    page_count: int | None
    sha256: str
    size_bytes: int
    extractor: str


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    source_path: str
    filename: str
    extension: str
    content_type: str
    size_bytes: int
    sha256: str
    imported_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: DocumentStatus = DocumentStatus.IMPORTED
    page_count: int | None = None
    chunk_count: int = 0
    embedding_model: str = ""
    embedding_dimensions: int | None = None
    error_message: str = ""


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    ordinal: int
    text: str
    page_number: int | None
    section: str | None
    char_start: int
    char_end: int
    embedding: tuple[float, ...] | None = None
    embedding_model: str = ""


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    document_id: str
    filename: str
    page_number: int | None
    section: str | None
    text: str
    cosine_similarity: float


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    citations: tuple[RetrievalHit, ...]
    insufficient_evidence: bool
    model: str = ""
