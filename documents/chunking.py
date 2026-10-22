"""Deterministic character-based chunking with source provenance."""
from __future__ import annotations

import hashlib

from .domain import DocumentChunk, ExtractionResult

DEFAULT_CHUNK_CHARS = 2400
DEFAULT_OVERLAP_CHARS = 300


def chunk_document(
    document_id: str,
    extraction: ExtractionResult,
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> tuple[DocumentChunk, ...]:
    """Chunk approximately by characters (not tokens), carrying page/section provenance."""
    if chunk_chars < 100 or overlap_chars < 0 or overlap_chars >= chunk_chars:
        raise ValueError("Chunk size must be >= 100 characters and overlap smaller than chunk size.")
    chunks = []
    ordinal = 0
    for block_index, block in enumerate(extraction.blocks):
        text = block.text.strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_chars)
            if end < len(text):
                boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
                if boundary > start + chunk_chars // 2:
                    end = boundary + (1 if text[boundary] == "\n" else 2)
            part = text[start:end].strip()
            if part:
                signature = f"{document_id}:{block_index}:{start}:{part}"
                chunk_id = hashlib.sha256(signature.encode("utf-8")).hexdigest()
                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    ordinal=ordinal,
                    text=part,
                    page_number=block.page_number,
                    section=block.section,
                    char_start=start,
                    char_end=end,
                ))
                ordinal += 1
            if end >= len(text):
                break
            start = max(start + 1, end - overlap_chars)
    return tuple(chunks)
