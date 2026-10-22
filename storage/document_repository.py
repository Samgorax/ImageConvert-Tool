"""Persistent local document metadata, text chunks, and optional vectors."""
from __future__ import annotations

import json
import math

from documents.domain import DocumentChunk, DocumentRecord, DocumentStatus
from storage.database import get_connection


def list_documents() -> list[DocumentRecord]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY imported_at DESC").fetchall()
    return [_record(row) for row in rows]


def get_document(document_id: str) -> DocumentRecord | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
    return _record(row) if row else None


def save_extracted(record: DocumentRecord, chunks: tuple[DocumentChunk, ...], extractor: str) -> None:
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        prior = conn.execute("SELECT document_id FROM documents WHERE source_path=?", (record.source_path,)).fetchone()
        if prior:
            conn.execute("DELETE FROM document_chunks WHERE document_id=?", (prior["document_id"],))
        conn.execute("DELETE FROM documents WHERE document_id=? OR source_path=?", (record.document_id, record.source_path))
        conn.execute("""INSERT INTO documents
            (document_id,source_path,filename,extension,content_type,size_bytes,sha256,imported_at,status,
             page_count,chunk_count,embedding_model,embedding_dimensions,extractor,error_message)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            record.document_id, record.source_path, record.filename, record.extension, record.content_type,
            record.size_bytes, record.sha256, record.imported_at, record.status.value, record.page_count,
            len(chunks), record.embedding_model, record.embedding_dimensions, extractor, record.error_message,
        ))
        conn.executemany("""INSERT INTO document_chunks
            (chunk_id,document_id,ordinal,text,page_number,section,char_start,char_end,embedding_json,embedding_model)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", [(
            chunk.chunk_id, chunk.document_id, chunk.ordinal, chunk.text, chunk.page_number, chunk.section,
            chunk.char_start, chunk.char_end, None, "",
        ) for chunk in chunks])


def set_status(document_id: str, status: DocumentStatus, error: str = "") -> None:
    with get_connection() as conn:
        conn.execute("UPDATE documents SET status=?, error_message=? WHERE document_id=?",
                     (status.value, error[:1000], document_id))


def save_embeddings(document_id: str, chunks: tuple[DocumentChunk, ...], model: str, dimensions: int) -> None:
    if not model.strip() or dimensions <= 0:
        raise ValueError("An embedding model and positive vector dimension are required.")
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT document_id FROM documents WHERE document_id=?", (document_id,)).fetchone()
        if not current:
            raise ValueError("Document index was removed while embedding was in progress.")
        expected_ids = {
            row["chunk_id"] for row in conn.execute(
                "SELECT chunk_id FROM document_chunks WHERE document_id=?", (document_id,)
            ).fetchall()
        }
        supplied_ids = [chunk.chunk_id for chunk in chunks]
        if not expected_ids or len(supplied_ids) != len(set(supplied_ids)) or set(supplied_ids) != expected_ids:
            raise ValueError("Embedding batch must contain exactly one vector for every stored document chunk.")
        for chunk in chunks:
            if chunk.embedding is None or len(chunk.embedding) != dimensions:
                raise ValueError("Embedding batch is incomplete or dimension-incompatible.")
            if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in chunk.embedding):
                raise ValueError("Embedding vectors must contain only finite numeric values.")
            cursor = conn.execute(
                "UPDATE document_chunks SET embedding_json=?, embedding_model=? WHERE chunk_id=? AND document_id=?",
                (json.dumps(chunk.embedding, allow_nan=False), model, chunk.chunk_id, document_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("An embedding did not match a stored document chunk.")
        conn.execute("UPDATE documents SET status=?,embedding_model=?,embedding_dimensions=?,error_message='' WHERE document_id=?",
                     (DocumentStatus.INDEXED.value, model, dimensions, document_id))


def get_chunks(document_ids: tuple[str, ...] | None = None) -> list[tuple[DocumentChunk, DocumentRecord]]:
    with get_connection() as conn:
        if document_ids is None:
            rows = conn.execute("""SELECT c.*,d.filename,d.extension,d.status,d.source_path,d.size_bytes,d.sha256,
                d.imported_at,d.content_type,d.page_count,d.chunk_count,d.embedding_model,d.embedding_dimensions,
                d.extractor,d.error_message,d.document_id AS d_id FROM document_chunks c JOIN documents d USING(document_id)
                WHERE d.status=? AND c.embedding_json IS NOT NULL ORDER BY d.imported_at,c.ordinal""",
                (DocumentStatus.INDEXED.value,)).fetchall()
        elif not document_ids:
            return []
        else:
            placeholders = ",".join("?" for _ in document_ids)
            rows = conn.execute(f"""SELECT c.*,d.filename,d.extension,d.status,d.source_path,d.size_bytes,d.sha256,
                d.imported_at,d.content_type,d.page_count,d.chunk_count,d.embedding_model,d.embedding_dimensions,
                d.extractor,d.error_message,d.document_id AS d_id FROM document_chunks c JOIN documents d USING(document_id)
                WHERE d.status=? AND c.embedding_json IS NOT NULL AND d.document_id IN ({placeholders})
                ORDER BY d.imported_at,c.ordinal""", (DocumentStatus.INDEXED.value, *document_ids)).fetchall()
    records = []
    for row in rows:
        vector = tuple(json.loads(row["embedding_json"]))
        chunk = DocumentChunk(row["chunk_id"], row["document_id"], row["ordinal"], row["text"],
                              row["page_number"], row["section"], row["char_start"], row["char_end"], vector,
                              row["embedding_model"])
        records.append((chunk, _record(row)))
    return records


def remove_index(document_id: str) -> bool:
    """Remove stored text/vectors only. The source file is never deleted."""
    with get_connection() as conn:
        conn.execute("DELETE FROM document_chunks WHERE document_id=?", (document_id,))
        cursor = conn.execute("DELETE FROM documents WHERE document_id=?", (document_id,))
    return cursor.rowcount > 0


def _record(row) -> DocumentRecord:
    return DocumentRecord(
        document_id=row["document_id"], source_path=row["source_path"], filename=row["filename"],
        extension=row["extension"], content_type=row["content_type"], size_bytes=row["size_bytes"],
        sha256=row["sha256"], imported_at=row["imported_at"], status=DocumentStatus(row["status"]),
        page_count=row["page_count"], chunk_count=row["chunk_count"], embedding_model=row["embedding_model"],
        embedding_dimensions=row["embedding_dimensions"], error_message=row["error_message"],
    )
