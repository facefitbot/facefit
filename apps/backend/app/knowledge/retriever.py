from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import KnowledgeChunk, KnowledgeDocument


def retrieve_context(db: Session, selected_problems: list[str], limit: int = 6) -> str:
    query = (
        db.query(KnowledgeChunk)
        .join(KnowledgeDocument)
        .filter(KnowledgeChunk.is_active.is_(True), KnowledgeDocument.is_active.is_(True))
    )
    keywords = [problem.lower() for problem in selected_problems if problem]
    if keywords:
        query = query.filter(or_(*[KnowledgeChunk.content.ilike(f"%{keyword[:30]}%") for keyword in keywords]))
    chunks = query.order_by(KnowledgeChunk.id.asc()).limit(limit).all()
    if not chunks and keywords:
        chunks = (
            db.query(KnowledgeChunk)
            .join(KnowledgeDocument)
            .filter(KnowledgeChunk.is_active.is_(True), KnowledgeDocument.is_active.is_(True))
            .order_by(KnowledgeChunk.id.asc())
            .limit(limit)
            .all()
        )
    return "\n\n".join(chunk.content for chunk in chunks)

