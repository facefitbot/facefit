from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Broadcast, BroadcastRecipient, Lead, TelegramUser
from app.db.session import SessionLocal
from app.storage.local import local_storage
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _audience_query(db: Session, audience_filter: dict):
    query = db.query(TelegramUser).join(Lead)
    segment = audience_filter.get("segment")
    if segment == "no_photo":
        query = query.filter(Lead.status.in_(["WAITING_FOR_PHOTO", "WAITING_FOR_PROBLEMS"]))
    elif segment == "got_report":
        query = query.filter(Lead.status.in_(["COMPLETED", "NEEDS_REVIEW"]))
    elif segment == "report_opened":
        query = query.filter(Lead.report_opened.is_(True))
    elif segment == "no_cta":
        query = query.filter(Lead.cta_clicked.is_(False))
    if audience_filter.get("problem"):
        problem = audience_filter["problem"]
        query = query.filter(Lead.selected_problems.contains([problem]) if db.bind.dialect.name == "postgresql" else cast(Lead.selected_problems, String).ilike(f"%{problem}%"))
    if audience_filter.get("tag"):
        tag = audience_filter["tag"]
        query = query.filter(Lead.tags.contains([tag]) if db.bind.dialect.name == "postgresql" else cast(Lead.tags, String).ilike(f"%{tag}%"))
    return query


def _keyboard(buttons: list[dict[str, str]]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button.get("text", "Открыть"), url=button.get("url"))]
            for button in buttons
            if button.get("url")
        ]
    )


async def _send_to_user(bot: Bot, user: TelegramUser, broadcast: Broadcast) -> None:
    markup = _keyboard(broadcast.buttons or [])
    if broadcast.media_path:
        abs_path = local_storage.abs_path(broadcast.media_path)
        if broadcast.message_type == "photo":
            await bot.send_photo(user.telegram_id, FSInputFile(abs_path), caption=broadcast.text or None, reply_markup=markup)
            return
        if broadcast.message_type == "video":
            await bot.send_video(user.telegram_id, FSInputFile(abs_path), caption=broadcast.text or None, reply_markup=markup)
            return
        if broadcast.message_type == "voice":
            await bot.send_voice(user.telegram_id, FSInputFile(abs_path), caption=broadcast.text or None, reply_markup=markup)
            return
    await bot.send_message(user.telegram_id, broadcast.text or "", reply_markup=markup)


async def _send_broadcast_async(broadcast_id: int) -> None:
    db = SessionLocal()
    bot = Bot(settings.telegram_bot_token) if settings.telegram_bot_token else None
    try:
        broadcast = db.query(Broadcast).filter(Broadcast.id == broadcast_id).first()
        if not broadcast:
            return
        users = _audience_query(db, broadcast.audience_filter or {}).all()
        broadcast.status = "sending"
        db.commit()
        for user in users:
            recipient = BroadcastRecipient(broadcast_id=broadcast.id, telegram_user_id=user.id, status="pending")
            db.add(recipient)
            db.commit()
            try:
                if bot:
                    await _send_to_user(bot, user, broadcast)
                    recipient.status = "sent"
                else:
                    recipient.status = "mock_sent"
                recipient.delivered_at = datetime.now(timezone.utc)
            except Exception as exc:
                recipient.status = "failed"
                recipient.error_message = str(exc)
            db.commit()
        broadcast.status = "sent"
        broadcast.sent_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        if bot:
            await bot.session.close()
        db.close()


@celery_app.task(name="app.workers.tasks_broadcast.send_broadcast_task", bind=True)
def send_broadcast_task(self, broadcast_id: int) -> None:
    asyncio.run(_send_broadcast_async(broadcast_id))


def enqueue_broadcast(broadcast_id: int) -> None:
    try:
        send_broadcast_task.apply_async(args=[broadcast_id], queue="telegram")
    except Exception:
        asyncio.run(_send_broadcast_async(broadcast_id))
