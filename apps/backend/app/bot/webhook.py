from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from redis import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)
WEBHOOK_SETUP_LOCK_KEY = "telegram:webhook:setup_lock"


def resolve_telegram_webhook_url() -> str | None:
    if settings.telegram_webhook_url:
        return settings.telegram_webhook_url
    if settings.backend_url.startswith("https://"):
        return f"{settings.backend_url.rstrip('/')}/api/telegram/webhook"
    return None


async def setup_telegram_webhook() -> None:
    if settings.telegram_update_mode != "webhook":
        logger.info("Telegram update mode is %s; webhook setup skipped", settings.telegram_update_mode)
        return
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN is not configured; webhook setup skipped")
        return

    webhook_url = resolve_telegram_webhook_url()
    if not webhook_url:
        logger.warning("TELEGRAM_WEBHOOK_URL is not configured and BACKEND_URL is not public HTTPS")
        return

    if settings.redis_url:
        try:
            redis_client = Redis.from_url(settings.redis_url)
            if not redis_client.set(WEBHOOK_SETUP_LOCK_KEY, "1", nx=True, ex=60):
                logger.info("Telegram webhook setup skipped; another process owns the setup lock")
                redis_client.close()
                return
            redis_client.close()
        except Exception:
            logger.warning("Could not acquire Telegram webhook setup lock; continuing without lock", exc_info=True)

    bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        try:
            await bot.set_webhook(
                webhook_url,
                drop_pending_updates=settings.telegram_webhook_drop_pending_updates,
                secret_token=settings.telegram_webhook_secret,
                allowed_updates=["message", "callback_query"],
            )
            logger.info("Telegram webhook configured: %s", webhook_url)
        except Exception:
            logger.warning("Telegram webhook setup failed; application startup will continue", exc_info=True)
    finally:
        await bot.session.close()


async def delete_telegram_webhook_for_polling() -> None:
    if not settings.telegram_bot_token:
        return
    bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("Telegram webhook deleted; polling can start")
    finally:
        await bot.session.close()
