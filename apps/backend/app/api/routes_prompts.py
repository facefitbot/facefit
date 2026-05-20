from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import PromptPatch
from app.api.serializers import prompt_dict
from app.core.exceptions import not_found
from app.core.security import AdminAuth
from app.db.models import PromptTemplate
from app.db.session import get_db

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


@router.get("")
def list_prompts(_: AdminAuth, db: Session = Depends(get_db)) -> dict:
    prompts = db.query(PromptTemplate).order_by(PromptTemplate.id.asc()).all()
    return {"items": [prompt_dict(item) for item in prompts]}


@router.patch("/{prompt_id}")
def patch_prompt(prompt_id: int, payload: PromptPatch, _: AdminAuth, db: Session = Depends(get_db)) -> dict:
    prompt = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
    if not prompt:
        raise not_found("Prompt не найден")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prompt, field, value)
    db.commit()
    db.refresh(prompt)
    return prompt_dict(prompt)

