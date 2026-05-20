from fastapi import APIRouter, Header, HTTPException, Request

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update

from app.bot.main import build_dispatcher
from app.core.config import settings

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    if not settings.telegram_bot_token:
        return {"ok": False, "detail": "TELEGRAM_BOT_TOKEN is not configured"}
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")

    bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = build_dispatcher()
    try:
        payload = await request.json()
        update = Update.model_validate(payload, context={"bot": bot})
        await dispatcher.feed_update(bot, update)
        return {"ok": True}
    finally:
        await bot.session.close()
