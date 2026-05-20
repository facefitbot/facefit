from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards import consent_keyboard
from app.db.models import AnalysisStatus, CampaignSource, EventLog, Lead, TelegramUser
from app.db.repositories import get_bot_settings
from app.db.session import SessionLocal

router = Router()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    payload = (message.text or "").split(maxsplit=1)[1] if message.text and len(message.text.split(maxsplit=1)) > 1 else None
    db = SessionLocal()
    try:
        campaign = None
        if payload:
            campaign = db.query(CampaignSource).filter(CampaignSource.start_payload == payload, CampaignSource.is_active.is_(True)).first()
            if campaign:
                campaign.clicks += 1
        user = db.query(TelegramUser).filter(TelegramUser.telegram_id == message.from_user.id).first()
        if not user:
            user = TelegramUser(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                language_code=message.from_user.language_code,
                current_status=AnalysisStatus.WAITING_FOR_CONSENT,
                start_payload=payload,
                campaign=campaign,
            )
            db.add(user)
            db.flush()
        else:
            user.username = message.from_user.username
            user.first_name = message.from_user.first_name
            user.last_name = message.from_user.last_name
            user.current_status = AnalysisStatus.WAITING_FOR_CONSENT
            user.start_payload = payload or user.start_payload
            if campaign:
                user.campaign = campaign
        lead = user.lead
        if not lead:
            lead = Lead(telegram_user_id=user.id, status=AnalysisStatus.WAITING_FOR_CONSENT, source=payload)
            db.add(lead)
        else:
            lead.status = AnalysisStatus.WAITING_FOR_CONSENT
            lead.source = payload or lead.source
        db.add(EventLog(telegram_user_id=user.id, lead_id=lead.id if lead.id else None, event_type="start", payload={"source": payload}))
        settings = get_bot_settings(db)
        db.commit()
        await state.clear()
        await message.answer(settings.welcome_text)
        await message.answer(settings.consent_text, reply_markup=consent_keyboard())
    finally:
        db.close()

