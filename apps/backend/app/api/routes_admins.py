from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import AdminCreate, AdminPatch
from app.api.serializers import admin_dict
from app.core.exceptions import forbidden, not_found
from app.core.security import AdminAuth, hash_password
from app.db.models import AdminRole, AdminUser
from app.db.session import get_db

router = APIRouter(prefix="/api/admins", tags=["admins"])


def _require_owner(admin: AdminUser) -> None:
    if admin.role != AdminRole.OWNER:
        raise forbidden("Только owner может управлять администраторами")


@router.get("")
def list_admins(admin: AdminAuth, db: Session = Depends(get_db)) -> dict:
    _require_owner(admin)
    items = db.query(AdminUser).order_by(AdminUser.created_at.desc()).all()
    return {"items": [admin_dict(item) for item in items]}


@router.post("")
def create_admin(payload: AdminCreate, admin: AdminAuth, db: Session = Depends(get_db)) -> dict:
    _require_owner(admin)
    item = AdminUser(email=payload.email, password_hash=hash_password(payload.password), role=payload.role, is_active=True)
    db.add(item)
    db.commit()
    db.refresh(item)
    return admin_dict(item)


@router.patch("/{admin_id}")
def patch_admin(admin_id: int, payload: AdminPatch, admin: AdminAuth, db: Session = Depends(get_db)) -> dict:
    _require_owner(admin)
    item = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not item:
        raise not_found("Администратор не найден")
    data = payload.model_dump(exclude_unset=True)
    if data.get("password"):
        item.password_hash = hash_password(data["password"])
    if data.get("role") is not None:
        item.role = data["role"]
    if data.get("is_active") is not None:
        item.is_active = data["is_active"]
    db.commit()
    db.refresh(item)
    return admin_dict(item)
