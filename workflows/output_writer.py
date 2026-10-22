"""Bounded, atomic, no-overwrite report file creation."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from core.exceptions import PathTraversalError
from permissions.audit_log import log_event
from permissions.enforcer import PermissionEnforcer
from permissions.policy import PermissionPolicy

MAX_REPORT_BYTES = 1_000_000
FORMATS = {"txt": ".txt", "md": ".md", "json": ".json"}


def write_report(directory: Path, filename: str, content: str, file_format: str,
                 policy: PermissionPolicy) -> Path:
    """Create a validated report under a user-selected approved directory."""
    directory = directory.expanduser().resolve(strict=True)
    enforcer = PermissionEnforcer(policy)
    enforcer.require_ai_write_files()
    if not directory.is_dir() or not policy.allowed_output_roots:
        raise PermissionError("Choose an existing output directory explicitly approved for this session.")
    if not isinstance(filename, str) or not filename.strip() or filename != Path(filename).name or any(
        token in filename for token in ("/", "\\", "..", ":")
    ):
        raise ValueError("Report filename must be a plain base name without path components.")
    file_format = file_format.lower().lstrip(".")
    if file_format not in FORMATS:
        raise ValueError("Supported report formats are TXT, Markdown, and JSON.")
    suffix = FORMATS[file_format]
    if Path(filename).suffix.lower() != suffix:
        filename += suffix
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("Report content exceeds the 1 MB limit.")
    if file_format == "json":
        json.loads(content)
    destination = directory / filename
    try:
        destination.resolve().relative_to(directory)
    except ValueError as exc:
        raise PathTraversalError("Report path escapes the selected output directory.") from exc
    enforcer.require_write_output(destination.resolve())
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=directory, prefix=".sw-report-", delete=False) as stream:
            temporary = stream.name
            stream.write(content.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        # Hard-link creation is atomic and fails if the destination already exists.
        os.link(temporary, destination)
        log_event("workflow_file_created", f"name={filename}; format={file_format}; bytes={len(content.encode('utf-8'))}")
        return destination
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
