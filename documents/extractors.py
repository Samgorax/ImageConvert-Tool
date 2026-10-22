"""Local, bounded text extraction for supported document formats."""
from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .domain import ExtractionResult, TextBlock
from .errors import DocumentExtractionError, DocumentValidationError

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED = 100 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown"}


def extract_document(path: str | Path) -> ExtractionResult:
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise DocumentValidationError("Choose a readable PDF, DOCX, TXT, or Markdown file.")
    if source.stat().st_size > MAX_FILE_BYTES:
        raise DocumentValidationError("The document exceeds the 50 MiB import limit.")
    if not source.stat().st_size:
        raise DocumentValidationError("The document is empty.")
    try:
        with source.open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise DocumentValidationError(f"The document cannot be read: {exc}") from exc
    if len(raw) > MAX_FILE_BYTES:
        raise DocumentValidationError("The document exceeds the 50 MiB import limit.")
    digest = hashlib.sha256(raw).hexdigest()
    extension = source.suffix.lower()
    if extension == ".pdf":
        blocks, page_count = _extract_pdf(source)
    elif extension == ".docx":
        blocks, page_count = _extract_docx(source)
    else:
        blocks, page_count = _extract_plain(raw, extension), None
    if not any(block.text.strip() for block in blocks):
        raise DocumentExtractionError(
            "No extractable text was found. Scanned PDFs need a separately configured local OCR tool."
        )
    extractor = "QtPdf" if extension == ".pdf" else "python-docx-xml" if extension == ".docx" else "UTF text"
    return ExtractionResult(tuple(blocks), page_count, digest, len(raw), extractor)


def _extract_pdf(path: Path) -> tuple[list[TextBlock], int]:
    try:
        from PySide6.QtPdf import QPdfDocument
    except ImportError as exc:
        raise DocumentExtractionError("PySide6 QtPdf is unavailable for PDF text extraction.") from exc
    document = QPdfDocument()
    status = document.load(str(path))
    if status == QPdfDocument.Status.Loading:
        # QtPdf loads asynchronously; poll from the document worker, never from the UI thread.
        import time

        deadline = time.monotonic() + 30
        while document.status() == QPdfDocument.Status.Loading and time.monotonic() < deadline:
            time.sleep(0.025)
    if document.status() != QPdfDocument.Status.Ready:
        raise DocumentExtractionError("PDF could not be opened; it may be encrypted or damaged.")
    blocks = []
    for page in range(document.pageCount()):
        selection = document.getAllText(page)
        value = selection.text().strip()
        if value:
            blocks.append(TextBlock(value, page_number=page + 1))
    return blocks, document.pageCount()


def _extract_docx(path: Path) -> tuple[list[TextBlock], None]:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if sum(item.file_size for item in members) > MAX_DOCX_UNCOMPRESSED:
                raise DocumentValidationError("The DOCX expands beyond the 100 MiB safety limit.")
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
    except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise DocumentExtractionError("The DOCX package is invalid or unreadable.") from exc
    blocks = []
    for paragraph in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            style = paragraph.find("./w:pPr/w:pStyle", ns)
            style_name = style.get(f"{{{ns['w']}}}val", "") if style is not None else ""
            blocks.append(TextBlock(text, section=style_name or None))
    return blocks, None


def _extract_plain(raw: bytes, extension: str) -> list[TextBlock]:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - cp1252 decodes any byte sequence
        raise DocumentExtractionError("Text encoding could not be detected.")
    if "\x00" in text:
        raise DocumentValidationError("Binary content is not accepted as a text document.")
    lines = text.splitlines()
    blocks: list[TextBlock] = []
    current: list[str] = []
    section: str | None = None
    for line in lines:
        heading = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line) if extension in {".md", ".markdown"} else None
        if heading:
            if current:
                blocks.append(TextBlock("\n".join(current), section=section))
                current = []
            section = heading.group(1)
            blocks.append(TextBlock(heading.group(0), section=section))
        elif line.strip():
            current.append(line.rstrip())
        elif current:
            blocks.append(TextBlock("\n".join(current), section=section))
            current = []
    if current:
        blocks.append(TextBlock("\n".join(current), section=section))
    return blocks
