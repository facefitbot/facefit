from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile

from app.bot.progress import get_progress_message, progress_text, should_apply_stage
from app.core.config import settings
from app.db.models import AiJobLog, AnalysisRequest
from app.db.session import SessionLocal
from app.storage.local import local_storage
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _log_job(analysis_id: int | None, stage: str, status: str, message: str | None = None, payload: dict | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(AiJobLog(analysis_id=analysis_id, stage=stage, status=status, message=message, payload=payload or {}))
        db.commit()
    finally:
        db.close()


async def _send_ready_message(telegram_id: int, protocol_image_path: str, report_url: str, protocol_version: str) -> None:
    if not settings.telegram_bot_token:
        return
    if protocol_version != "final_v1":
        raise RuntimeError("Expected final_v1 face protocol for new analysis")
    if not protocol_image_path or not Path(protocol_image_path).exists():
        raise RuntimeError("Expected final_v1 PNG at face_protocol_image_path")

    bot = Bot(settings.telegram_bot_token)
    try:
        await bot.send_chat_action(telegram_id, ChatAction.UPLOAD_PHOTO)
        await bot.send_photo(
            telegram_id,
            FSInputFile(protocol_image_path),
            caption="Ваш face-протокол готов. Подробный отчет откроется по ссылке ниже.",
        )
    finally:
        await bot.session.close()


async def edit_progress_message(bot: Bot, chat_id: int, message_id: int, text: str) -> bool:
    try:
        await bot.send_chat_action(chat_id, ChatAction.TYPING)
        await bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id)
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return True
        logger.warning("Could not edit Telegram progress message: %s", exc)
        return False


async def _send_after_photo(telegram_id: int, image_path: str) -> None:
    if not settings.telegram_bot_token:
        return
    bot = Bot(settings.telegram_bot_token)
    try:
        await bot.send_photo(
            telegram_id,
            FSInputFile(image_path),
            caption=(
                "Возможная визуализация результата при регулярной работе 3 месяца. "
                "Это не гарантия результата, а мягкий ориентир."
            ),
        )
    finally:
        await bot.session.close()


async def _send_after_photo_pending_message(telegram_id: int) -> None:
    if not settings.telegram_bot_token:
        return
    bot = Bot(settings.telegram_bot_token)
    try:
        await bot.send_message(
            telegram_id,
            "Визуализация результата еще формируется. Если потребуется, мы доработаем ее отдельно.",
        )
    finally:
        await bot.session.close()


async def _send_after_photo_retry_message(telegram_id: int) -> None:
    if not settings.telegram_bot_token:
        return
    bot = Bot(settings.telegram_bot_token)
    try:
        await bot.send_message(
            telegram_id,
            "After-photo не получилось сгенерировать достаточно заметно и реалистично. "
            "Я не отправляю исходное фото вместо результата — визуализацию нужно перезапустить или доработать отдельно.",
        )
    finally:
        await bot.session.close()


@celery_app.task(name="app.workers.tasks_telegram.send_analysis_ready_message_task", bind=True)
def send_analysis_ready_message_task(self, analysis_id: int, report_url: str) -> None:
    db = SessionLocal()
    try:
        analysis = db.query(AnalysisRequest).filter(AnalysisRequest.id == analysis_id).first()
        if not analysis or not analysis.telegram_user:
            return
        if analysis.face_protocol_version != "final_v1":
            raise RuntimeError("Expected final_v1 face protocol for new analysis")
        if not analysis.face_protocol_image_path:
            raise RuntimeError("Expected final_v1 PNG path was empty")
        protocol_png_abs = local_storage.abs_path(analysis.face_protocol_image_path)
        asyncio.run(
            _send_ready_message(
                analysis.telegram_user.telegram_id,
                protocol_png_abs,
                report_url,
                analysis.face_protocol_version,
            )
        )
        asyncio.run(_replace_progress_with_result(analysis.id, analysis.telegram_user.telegram_id, report_url))
        _log_job(analysis.id, "telegram_send", "success", "Final protocol and report link sent")
    except Exception as exc:
        logger.exception("Telegram final protocol send failed")
        _log_job(analysis_id, "telegram_send", "failed", str(exc))
        raise
    finally:
        db.close()


async def _replace_progress_with_result(analysis_id: int, telegram_id: int, report_url: str) -> None:
    if not settings.telegram_bot_token:
        return
    if not should_apply_stage(analysis_id, "ready"):
        return
    progress = get_progress_message(analysis_id)
    bot = Bot(settings.telegram_bot_token)
    try:
        if progress:
            edited = await edit_progress_message(
                bot,
                progress.chat_id,
                progress.message_id,
                progress_text("ready", report_url),
            )
            if edited:
                return
        await bot.send_message(
            telegram_id,
            f"Подробный отчет: {report_url}\n\nAfter-photo пришлю отдельным сообщением, если генерация займет больше времени.",
        )
    finally:
        await bot.session.close()


@celery_app.task(name="app.workers.tasks_telegram.update_analysis_progress_task", bind=True)
def update_analysis_progress_task(self, analysis_id: int, stage: str) -> None:
    if not settings.telegram_bot_token:
        return
    if not should_apply_stage(analysis_id, stage):
        return
    progress = get_progress_message(analysis_id)
    if not progress:
        return
    try:
        asyncio.run(_edit_analysis_progress(progress.chat_id, progress.message_id, progress_text(stage)))
        _log_job(analysis_id, "telegram_progress", "success", stage)
    except Exception as exc:
        logger.warning("Telegram progress update failed: %s", exc)
        _log_job(analysis_id, "telegram_progress", "failed", str(exc), {"stage": stage})


async def _edit_analysis_progress(chat_id: int, message_id: int, text: str) -> None:
    bot = Bot(settings.telegram_bot_token)
    try:
        await edit_progress_message(bot, chat_id, message_id, text)
    finally:
        await bot.session.close()


@celery_app.task(name="app.workers.tasks_telegram.send_after_photo_message_task", bind=True)
def send_after_photo_message_task(self, analysis_id: int) -> None:
    db = SessionLocal()
    try:
        analysis = db.query(AnalysisRequest).filter(AnalysisRequest.id == analysis_id).first()
        if not analysis or not analysis.telegram_user or not analysis.after_photo_final_path:
            return
        final_abs = local_storage.abs_path(analysis.after_photo_final_path)
        if not Path(final_abs).exists():
            raise RuntimeError("Approved after-photo file was not found")
        asyncio.run(_send_after_photo(analysis.telegram_user.telegram_id, final_abs))
        _log_job(analysis.id, "telegram_after_photo", "success", "After-photo sent")
    except Exception as exc:
        logger.exception("Telegram after-photo send failed")
        _log_job(analysis_id, "telegram_after_photo", "failed", str(exc))
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks_telegram.send_after_photo_pending_message_task", bind=True)
def send_after_photo_pending_message_task(self, analysis_id: int) -> None:
    _send_after_photo_status_message(analysis_id, "pending")


@celery_app.task(name="app.workers.tasks_telegram.send_after_photo_retry_message_task", bind=True)
def send_after_photo_retry_message_task(self, analysis_id: int) -> None:
    _send_after_photo_status_message(analysis_id, "retry")


def _send_after_photo_status_message(analysis_id: int, kind: str) -> None:
    db = SessionLocal()
    try:
        analysis = db.query(AnalysisRequest).filter(AnalysisRequest.id == analysis_id).first()
        if not analysis or not analysis.telegram_user:
            return
        if kind == "retry":
            asyncio.run(_send_after_photo_retry_message(analysis.telegram_user.telegram_id))
        else:
            asyncio.run(_send_after_photo_pending_message(analysis.telegram_user.telegram_id))
        _log_job(analysis.id, f"telegram_after_photo_{kind}", "success", datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        logger.exception("Telegram after-photo status message failed")
        _log_job(analysis_id, f"telegram_after_photo_{kind}", "failed", str(exc))
        raise
    finally:
        db.close()


def enqueue_analysis_ready_message(analysis_id: int, report_url: str) -> None:
    send_analysis_ready_message_task.apply_async(args=[analysis_id, report_url], queue="telegram")


def enqueue_analysis_progress_update(analysis_id: int, stage: str) -> None:
    update_analysis_progress_task.apply_async(args=[analysis_id, stage], queue="telegram")


def enqueue_after_photo_message(analysis_id: int) -> None:
    send_after_photo_message_task.apply_async(args=[analysis_id], queue="telegram")


def enqueue_after_photo_pending_message(analysis_id: int) -> None:
    send_after_photo_pending_message_task.apply_async(args=[analysis_id], queue="telegram")


def enqueue_after_photo_retry_message(analysis_id: int) -> None:
    send_after_photo_retry_message_task.apply_async(args=[analysis_id], queue="telegram")
