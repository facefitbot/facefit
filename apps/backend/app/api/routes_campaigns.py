from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import CampaignCreate
from app.api.serializers import campaign_dict
from app.core.config import settings
from app.core.exceptions import not_found
from app.core.security import AdminAuth
from app.db.models import CampaignSource
from app.db.session import get_db

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("")
def list_campaigns(_: AdminAuth, db: Session = Depends(get_db)) -> dict:
    campaigns = db.query(CampaignSource).order_by(CampaignSource.created_at.desc()).all()
    return {"items": [campaign_dict(item) for item in campaigns]}


@router.post("")
def create_campaign(payload: CampaignCreate, _: AdminAuth, db: Session = Depends(get_db)) -> dict:
    start_payload = payload.start_payload or payload.slug
    bot_name = settings.telegram_bot_username or "YOUR_BOT_USERNAME"
    campaign = CampaignSource(
        slug=payload.slug,
        title=payload.title,
        start_payload=start_payload,
        url=f"https://t.me/{bot_name}?start={start_payload}",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign_dict(campaign)


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, _: AdminAuth, db: Session = Depends(get_db)) -> dict:
    campaign = db.query(CampaignSource).filter(CampaignSource.id == campaign_id).first()
    if not campaign:
        raise not_found("Источник не найден")
    return campaign_dict(campaign)

