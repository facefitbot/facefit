from __future__ import annotations

import io
from datetime import datetime, timezone

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from PIL import Image

from app.bot.keyboards import problems_keyboard
from app.bot.states import FaceProtocolStates
from app.db.models import AnalysisRequest, AnalysisStatus, CampaignSource, TelegramUser
from app.db.repositories import get_bot_settings
from app.db.session import SessionLocal
from app.storage.local import local_storage

router = Router()


def _is_valid_photo(data: bytes) -> bool:
    try:
        image = Image.open(io.BytesIO(data))
        width, height = image.size
        return width >= 500 and height >= 500
    except Exception:
        return False


@router.message(FaceProtocolStates.waiting_for_photo)
async def receive_photo(message: Message, state: FSMContext) -> None:
    if not message.photo:
        await message.answer("Пожалуйста, отправьте именно фото лица. Лучше анфас, при дневном свете и без сильных фильтров.")
        return
    buffer = io.BytesIO()
    await message.bot.download(message.photo[-1], destination=buffer)
    data = buffer.getvalue()
    if not _is_valid_photo(data):
        await message.answer("Фото получилось слишком маленьким или не читается. Пришлите, пожалуйста, другое фото лица анфас.")
        return

    db = SessionLocal()
    try:
        settings = get_bot_settings(db)
        user = db.query(TelegramUser).filter(TelegramUser.telegram_id == message.from_user.id).first()
        if not user or not user.lead:
            await message.answer("Давайте начнем заново: нажмите /start.")
            return
        analyses_count = db.query(AnalysisRequest).filter(AnalysisRequest.telegram_user_id == user.id).count()
        if analyses_count >= settings.analysis_limit_per_user:
            await message.answer("Лимит анализов для одного пользователя уже использован. Напишите эксперту, если нужен повторный протокол.")
            return
        relative_path = f"photos/{user.telegram_id}_{int(datetime.now(timezone.utc).timestamp())}.jpg"
        local_storage.save_bytes(relative_path, data)
        analysis = AnalysisRequest(
            telegram_user_id=user.id,
            lead_id=user.lead.id,
            status=AnalysisStatus.WAITING_FOR_PROBLEMS,
            original_photo_path=relative_path,
        )
        db.add(analysis)
        user.current_status = AnalysisStatus.WAITING_FOR_PROBLEMS
        user.lead.status = AnalysisStatus.WAITING_FOR_PROBLEMS
        if user.campaign:
            campaign: CampaignSource = user.campaign
            campaign.photo_count += 1
        db.commit()
        await state.set_state(FaceProtocolStates.waiting_for_problems)
        await state.update_data(analysis_id=analysis.id, selected_problems=[])
        await message.answer(
            "Выберите ключевые зоны, которые Вас беспокоят. Можно отметить несколько вариантов.",
            reply_markup=problems_keyboard(settings.problem_catalog or [], set()),
        )
    finally:
        db.close()

