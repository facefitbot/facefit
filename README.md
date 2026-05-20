# Bella Vladi Face Protocol MVP

Production-ready MVP Telegram-бота и web-админки для визуального face-протокола Bella Vladi.

## Что внутри

- FastAPI backend, aiogram 3 bot, Celery workers
- PostgreSQL, Redis, optional MinIO/S3-compatible storage
- SQLAlchemy 2.0 models + Alembic migration
- OpenAI Vision/report wrapper, Gemini fallback placeholder, Replicate Flux image-to-image wrapper
- Dev mock mode без AI ключей
- React/Vite/TypeScript/Tailwind admin panel
- Public report `/report/:publicToken`
- RAG база знаний из `knowledge_base.md` и system prompt из `system_prompt.md`

## Быстрый старт через Docker

```bash
cp .env.example .env
docker compose up -d
```

Backend: http://localhost:8000  
Admin/Public frontend: http://localhost:5173  
MinIO console: http://localhost:9001

## Локальный запуск backend

```bash
cd apps/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload
```

Worker:

```bash
cd apps/backend
source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

Bot:

```bash
cd apps/backend
source .venv/bin/activate
python -m app.bot.main
```

Через Docker бот запускается отдельно, чтобы `docker compose up -d` не падал в mock mode без Telegram token:

```bash
docker compose --profile bot up -d bot
```

Frontend:

```bash
cd apps/frontend
npm install
npm run dev
```

## Переменные окружения

Скопируйте `.env.example` в `.env`.

Минимально для mock mode:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/bella_vladi_bot
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=change-me
ADMIN_EMAIL=admin@bellavladi.local
ADMIN_PASSWORD=admin12345
TELEGRAM_BOT_TOKEN=
OPENAI_API_KEY=
OPENAI_ANALYSIS_MODEL=
OPENAI_REPORT_MODEL=
REPLICATE_API_TOKEN=
REPLICATE_FLUX_MODEL=
```

Для production добавьте:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BOT_USERNAME`
- `OPENAI_API_KEY`
- `OPENAI_ANALYSIS_MODEL`
- `OPENAI_REPORT_MODEL`
- `REPLICATE_API_TOKEN`
- `REPLICATE_FLUX_MODEL`
- при необходимости `GEMINI_API_KEY`, `GEMINI_MODEL`
- `PUBLIC_APP_URL` с публичным доменом фронтенда
- надежный `JWT_SECRET`
- S3/MinIO переменные, если `STORAGE_DRIVER=s3`

Model id не хардкодятся. Если точный id неизвестен, оставьте placeholder в `.env`.

## Админка

URL: http://localhost:5173/login

Seed-логин:

- email: `admin@bellavladi.local`
- password: `admin12345`

В админке доступны:

- Dashboard с воронкой и графиками
- Leads, фильтры, CSV export, заметки, теги
- Analysis detail, JSON viewer, AI логи, retry/regenerate
- Knowledge Base upload: PDF/DOCX/TXT/Markdown
- Prompt Templates editor
- Broadcast composer и история
- Campaign deep-links
- Settings: тексты бота, CTA, moderation, AI key status

## Как протестировать Telegram-бота

1. Создайте бота через BotFather.
2. Добавьте `TELEGRAM_BOT_TOKEN` и `TELEGRAM_BOT_USERNAME` в `.env`.
3. Запустите backend, worker и bot.
4. Откройте Telegram и отправьте `/start`.
5. Пройдите flow: согласие → имя → фото → мультивыбор проблем → анализ.

Если OpenAI/Replicate ключи пустые, включится mock mode:

- анализ вернется локальным структурированным JSON
- фото-протокол с overlay будет создан через Pillow
- public report откроется
- after-photo будет мягкой локальной имитацией через Pillow

## Где менять промпты

Админка → `Промпты`.

Seed создает:

- `analysis_system`
- `short_protocol`
- `protocol_slide_copy`
- `detailed_report`
- `after_photo`
- `after_photo_negative`
- `bot_tone`
- `disclaimer`

Также дефолтный system prompt лежит в `apps/backend/app/ai/default_system_prompt.md`, база знаний — в `apps/backend/app/knowledge/default_knowledge_base.md`.

## Где смотреть заявки и отчеты

- Заявки: `Admin → Лиды`
- Анализы и JSON: `Admin → Анализы`
- Public report link: `Admin → Отчеты` или карточка анализа
- AI ошибки: `Admin → Анализ → AI логи`, также агрегируются в Dashboard

## Protocol v4 renderer

Preview:

```bash
python -m app.reports.protocol_v4.preview
```

Smoke-test renderer/call-chain:

```bash
python -m app.reports.protocol_v4.smoke_test
```

`protocol_v4` рендерит 3 PNG 1080x1350 через Jinja2 HTML/CSS/SVG и Playwright screenshot. Визуальная система: clean AI face scan, боковые rails, тонкие leader lines, insight layout и 90-day timeline. Старые `protocol_image.py`, `protocol_v2` и `protocol_v3` оставлены только как legacy guard: при вызове они падают.

Очистка dev-кэша протоколов без удаления исходных фото:

```bash
python -m app.reports.protocol_v4.clean_protocol_cache
```

Полный Docker-перезапуск после изменений renderer:

```bash
docker compose down
docker compose up -d --build
```

Локальный перезапуск без Docker:

```bash
pkill -f celery || true
pkill -f uvicorn || true
pkill -f "app.bot.main" || true

cd apps/backend
alembic upgrade head
uvicorn app.main:app --reload
celery -A app.workers.celery_app worker --loglevel=info
python -m app.bot.main
```

В новых протоколах в логах должен появляться маркер:

```text
PROTOCOL_V4_RENDERER_ACTIVE
```

Если старый renderer случайно попадет в call chain, он должен упасть с:

```text
LEGACY_FACE_PROTOCOL_RENDERER_IS_DISABLED_USE_PROTOCOL_V4
```

## Production checklist

- заменить `JWT_SECRET`
- заменить seed пароль администратора
- подключить реальные AI model ids через `.env`
- настроить публичный домен и HTTPS
- настроить webhook или стабильный polling для Telegram
- включить S3-compatible storage вместо локального диска
- настроить backup PostgreSQL и lifecycle для фото
- добавить observability: Sentry/Prometheus/log aggregation
