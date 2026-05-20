from __future__ import annotations

from pathlib import Path

from docx import Document
from pypdf import PdfReader


def load_document_text(path: str, filename: str | None = None) -> str:
    file_path = Path(path)
    suffix = (filename or file_path.name).lower()
    if suffix.endswith(".pdf"):
        reader = PdfReader(str(file_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix.endswith(".docx"):
        doc = Document(str(file_path))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
    return file_path.read_text(encoding="utf-8", errors="ignore")

