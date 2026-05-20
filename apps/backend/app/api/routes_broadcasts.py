from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import BroadcastCreate
from app.api.serializers import broadcast_dict
from app.core.exceptions import not_found
from app.core.security import AdminAuth
from app.db.models import Broadcast
from app.db.session import get_db
from app.workers.tasks_broadcast import enqueue_broadcast

router = APIRouter(prefix="/api/broadcasts", tags=["broadcasts"])


@router.get("")
def list_broadcasts(_: AdminAuth, db: Session = Depends(get_db)) -> dict:
    items = db.query(Broadcast).options(selectinload(Broadcast.recipients)).order_by(Broadcast.created_at.desc()).all()
    return {"items": [broadcast_dict(item) for item in items]}


@router.post("")
def create_broadcast(payload: BroadcastCreate, _: AdminAuth, db: Session = Depends(get_db)) -> dict:
    broadcast = Broadcast(**payload.model_dump(), status="draft")
    db.add(broadcast)
    db.commit()
    db.refresh(broadcast)
    return broadcast_dict(broadcast)


@router.post("/{broadcast_id}/send")
def send_broadcast(broadcast_id: int, _: AdminAuth, db: Session = Depends(get_db)) -> dict:
    broadcast = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
    if not broadcast:
        raise not_found("Рассылка не найдена")
    broadcast.status = "queued"
    db.commit()
    enqueue_broadcast(broadcast_id)
    return {"ok": True}

