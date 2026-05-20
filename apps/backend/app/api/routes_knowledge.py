import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.api.serializers import document_dict
from app.core.exceptions import not_found
from app.core.security import AdminAuth
from app.db.models import KnowledgeChunk, KnowledgeDocument
from app.db.session import get_db
from app.knowledge.chunker import chunk_text
from app.knowledge.document_loader import load_document_text

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class KnowledgePatch(BaseModel):
    title: str | None = None
    is_active: bool | None = None


@router.get("")
def list_documents(_: AdminAuth, db: Session = Depends(get_db)) -> dict:
    docs = db.query(KnowledgeDocument).options(selectinload(KnowledgeDocument.chunks)).order_by(KnowledgeDocument.created_at.desc()).all()
    return {"items": [document_dict(item) for item in docs]}


@router.post("/upload")
async def upload_document(
    _: AdminAuth,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    suffix = Path(file.filename or "document.txt").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        data = await file.read()
        temp.write(data)
        temp_path = temp.name
    content = load_document_text(temp_path, file.filename)
    Path(temp_path).unlink(missing_ok=True)
    document = KnowledgeDocument(
        title=title or file.filename or "Документ",
        filename=file.filename or "document",
        mime_type=file.content_type,
        content=content,
        is_active=True,
    )
    db.add(document)
    db.flush()
    for index, chunk in enumerate(chunk_text(content), start=1):
        db.add(KnowledgeChunk(document_id=document.id, chunk_index=index, content=chunk, is_active=True))
    db.commit()
    db.refresh(document)
    return document_dict(document, include_chunks=True)


@router.get("/{document_id}")
def get_document(document_id: int, _: AdminAuth, db: Session = Depends(get_db)) -> dict:
    doc = db.query(KnowledgeDocument).options(selectinload(KnowledgeDocument.chunks)).filter(KnowledgeDocument.id == document_id).first()
    if not doc:
        raise not_found("Документ не найден")
    return document_dict(doc, include_chunks=True)


@router.patch("/{document_id}")
def patch_document(document_id: int, payload: KnowledgePatch, _: AdminAuth, db: Session = Depends(get_db)) -> dict:
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
    if not doc:
        raise not_found("Документ не найден")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    db.commit()
    db.refresh(doc)
    return document_dict(doc)


@router.delete("/{document_id}")
def delete_document(document_id: int, _: AdminAuth, db: Session = Depends(get_db)) -> dict:
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
    if not doc:
        raise not_found("Документ не найден")
    db.delete(doc)
    db.commit()
    return {"ok": True}

