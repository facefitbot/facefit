from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from redis import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

PROGRESS_TTL_SECONDS = 60 * 60 * 6


@dataclass(frozen=True)
class ProgressMessage:
    chat_id: int
    message_id: int


STAGE_ORDER = {
    "queued": 10,
    "analysis": 20,
    "protocol_copy": 30,
    "render": 40,
    "report": 50,
    "ready": 100,
}


STAGE_TEXT = {
    "queued": (
        "Bella Vladi Face Protocol\n\n"
        "Шаг 1 из 5\n"
        "Фото принято. Заявка в очереди на AI-анализ.\n\n"
        "Я буду обновлять это сообщение по мере готовности."
    ),
    "analysis": (
        "Bella Vladi Face Protocol\n\n"
        "Шаг 2 из 5\n"
        "AI анализирует фото: тип кожи, морфотип, зоны внимания и выбранные проблемы.\n\n"
        "Обычно это занимает несколько минут."
    ),
    "protocol_copy": (
        "Bella Vladi Face Protocol\n\n"
        "Шаг 3 из 5\n"
        "Собираю персональные формулировки для протокола: коротко, по делу и по вашему фото."
    ),
    "render": (
        "Bella Vladi Face Protocol\n\n"
        "Шаг 4 из 5\n"
        "Рендерю финальный PNG-протокол в формате premium beauty journal."
    ),
    "report": (
        "Bella Vladi Face Protocol\n\n"
        "Шаг 5 из 5\n"
        "Готовлю подробный web-отчет и ссылку для просмотра."
    ),
}


def progress_text(stage: str, report_url: str | None = None) -> str:
    if stage == "ready":
        base = (
            "Bella Vladi Face Protocol\n\n"
            "Готово. Ваш face-протокол сформирован.\n\n"
            "PNG-протокол отправлен отдельным сообщением.\n"
            "After-photo пришлю отдельно, если генерация займет больше времени."
        )
        if report_url:
            base += f"\n\nПодробный отчет:\n{report_url}"
        return base
    return STAGE_TEXT.get(stage, STAGE_TEXT["queued"])


def _redis() -> Redis | None:
    if not settings.redis_url:
        return None
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _message_key(analysis_id: int) -> str:
    return f"analysis:{analysis_id}:progress_message"


def _stage_key(analysis_id: int) -> str:
    return f"analysis:{analysis_id}:progress_stage"


def save_progress_message(analysis_id: int, chat_id: int, message_id: int, stage: str = "queued") -> None:
    client = _redis()
    if not client:
        return
    try:
        client.setex(
            _message_key(analysis_id),
            PROGRESS_TTL_SECONDS,
            json.dumps({"chat_id": chat_id, "message_id": message_id}),
        )
        client.setex(_stage_key(analysis_id), PROGRESS_TTL_SECONDS, str(STAGE_ORDER.get(stage, 0)))
    except Exception:
        logger.warning("Could not save Telegram progress message", exc_info=True)
    finally:
        client.close()


def get_progress_message(analysis_id: int) -> ProgressMessage | None:
    client = _redis()
    if not client:
        return None
    try:
        raw = client.get(_message_key(analysis_id))
        if not raw:
            return None
        payload = json.loads(raw)
        return ProgressMessage(chat_id=int(payload["chat_id"]), message_id=int(payload["message_id"]))
    except Exception:
        logger.warning("Could not read Telegram progress message", exc_info=True)
        return None
    finally:
        client.close()


def should_apply_stage(analysis_id: int, stage: str) -> bool:
    client = _redis()
    if not client:
        return True
    next_order = STAGE_ORDER.get(stage, 0)
    try:
        current_order = int(client.get(_stage_key(analysis_id)) or 0)
        if next_order < current_order:
            return False
        client.setex(_stage_key(analysis_id), PROGRESS_TTL_SECONDS, str(next_order))
        return True
    except Exception:
        logger.warning("Could not update Telegram progress stage", exc_info=True)
        return True
    finally:
        client.close()
