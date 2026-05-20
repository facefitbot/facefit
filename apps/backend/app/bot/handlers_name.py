from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.states import FaceProtocolStates
from app.db.models import AnalysisStatus, TelegramUser
from app.db.repositories import get_bot_settings
from app.db.session import SessionLocal

router = Router()


@router.message(FaceProtocolStates.waiting_for_name)
async def receive_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()[:120]
    if len(name) < 2:
        await message.answer("Напишите, пожалуйста, имя текстом, чтобы я красиво подписала протокол.")
        return
    db = SessionLocal()
    try:
        user = db.query(TelegramUser).filter(TelegramUser.telegram_id == message.from_user.id).first()
        settings = get_bot_settings(db)
        if user and user.lead:
            user.lead.name = name
            user.lead.status = AnalysisStatus.WAITING_FOR_PHOTO
            user.current_status = AnalysisStatus.WAITING_FOR_PHOTO
            db.commit()
        await state.set_state(FaceProtocolStates.waiting_for_photo)
        await message.answer(settings.photo_instruction_text)
    finally:
        db.close()

