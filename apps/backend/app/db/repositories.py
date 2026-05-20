from sqlalchemy.orm import Session

from app.db.models import BotSettings, PromptTemplate


def get_bot_settings(db: Session) -> BotSettings:
    settings = db.query(BotSettings).order_by(BotSettings.id.asc()).first()
    if settings:
        return settings
    settings = BotSettings(
        welcome_text="Здравствуйте! Я бот Bella Vladi. Я помогу сделать первичный визуальный face-протокол.",
        consent_text="Перед началом подтвердите, пожалуйста, что вы добровольно отправляете фото для визуального анализа.",
        photo_instruction_text="Загрузите фото лица анфас: хорошее освещение, без сильных фильтров, без очков, лицо полностью видно.",
        waiting_text="Приняла фото. Сейчас формирую первичный face-протокол. Это может занять несколько минут.",
        after_analysis_text="Ваш face-протокол готов.",
        disclaimer="Анализ не является медицинским диагнозом и используется только для персонального face-протокола.",
        problem_catalog=[],
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def get_prompt(db: Session, key: str, default: str = "") -> str:
    prompt = db.query(PromptTemplate).filter(PromptTemplate.key == key, PromptTemplate.is_active.is_(True)).first()
    return prompt.content if prompt else default

