# Infrastructure — Bella Vladi Face Protocol (Production)

Документ для продакшен-развёртывания. Цель: воронка на ~5–10k пользователей, соло-оператор,
бюджет Google Cloud ~$300 кредитов, минимум ops-нагрузки, надёжность «не упало ночью».

> TL;DR: **НЕ Cloud Run.** Один Compute Engine VM с docker-compose (backend + воркеры +
> redis + postgres) + **персистентный диск** для файлов и БД + **Cloudflare Pages** для фронта.
> Самый дешёвый, простой и надёжный вариант под эту нагрузку и этот код. Без изменений кода.

---

## 0. Важное про нагрузку (читать первым)

«5–10k пользователей» в Telegram-воронке — это **суммарно за всё время**, а не одновременно.
Лиды приходят неделями. Реальная конкурентность — единицы запросов в минуту на пике.

Бутылочное горлышко системы — **латентность внешних AI API** (OpenAI / Gemini / Replicate),
а не твой CPU. Один запрос-анализ висит секунды-десятки секунд, ожидая ответа AI.
Поэтому масштабирование решается **числом Celery-воркеров**, а не мощным железом.

Вывод: тебе **не нужен** Kubernetes, автоскейл или дорогие managed-сервисы.
Нужен один нормальный VM с персистентным диском.

---

## 1. Почему НЕ Cloud Run

Твоя цель «чтобы не упало» правильная, но Cloud Run — неподходящий инструмент:

| Проблема | Почему критично для этого проекта |
|---|---|
| Cloud Run = «запрос → ответ», скейл в ноль | Celery-воркеры это **постоянные процессы**. Без HTTP-трафика Cloud Run убьёт инстанс, воркеры умрут. Фундаментальная несовместимость с очередями. |
| Образ backend ~2 ГБ (mediapipe, jax, opencv, playwright, chromium) | Cold start 5–15 сек. Telegram webhook словит таймаут. |
| `min-instances=1` чтобы убрать cold start | Платишь 24/7 → теряешь весь смысл Cloud Run. |
| Pipeline работает с локальным диском (`abs_path`) | Cloud Run даёт эфемерную ФС; файлы между запросами/инстансами не переживут. |

Cloud Run хорош для **stateless лёгких бурстовых HTTP-API**.
Здесь — **stateful асинхронный ML-pipeline**. Это другой класс задач.

---

## 2. Рекомендуемая архитектура

```
                 ┌──────────────────────┐
   Пользователь  │   Cloudflare Pages    │   ← фронт (React/Vite build, статика, бесплатно)
   (браузер)  ──▶│   admin + /report/... │
                 └──────────┬───────────┘
                            │ /api/* (fetch на backend-домен)
                            ▼
                 ┌──────────────────────┐
   Telegram    ──▶│  Cloudflare (TLS/CDN) │   ← проксирует домен, бесплатный HTTPS, защита
   webhook        └──────────┬───────────┘
                            ▼
        ┌─────────────────────────────────────────────┐
        │   Compute Engine VM  (e2-standard-2, Debian) │
        │   docker compose -f .. -f docker-compose.prod│
        │                                              │
        │   backend (FastAPI, uvicorn, webhook+API)    │
        │   worker_analysis / report / after_photo /   │
        │     telegram                                 │
        │   redis     (broker + progress state)        │
        │   postgres  (данные)                         │
        │                                              │
        │   /mnt/data  ← персистентный диск:           │
        │      /mnt/data/postgres   (БД)               │
        │      /mnt/data/storage    (фото, PNG, after) │
        └─────────────────────────────────────────────┘
                  снапшоты диска = бэкап
```

### Распределение по сервисам

| Компонент | Где | Почему |
|---|---|---|
| **Frontend** (admin + public report) | **Cloudflare Pages** | Статика. Бесплатно, CDN, авто-TLS. |
| **Backend API + webhook** | VM (docker-compose) | Stateful, тяжёлый образ, должен быть всегда поднят. |
| **Celery workers** ×4 | VM (docker-compose) | Постоянные процессы. Co-located с backend — общий образ. |
| **Redis** | VM (docker-compose) | Broker + ephemeral progress-state. Потеря некритична. |
| **PostgreSQL** | VM (docker-compose) | Данные лидов. На персистентном диске + cron pg_dump в бэкап. |
| **Файлы** (фото, PNG, after-photo) | **Персистентный диск** VM | Pipeline читает/пишет реальные файлы (`abs_path`). Диск переживает пересоздание VM, снапшотится. |
| **TLS / домен / защита** | Cloudflare | Бесплатный HTTPS, нужен для Telegram webhook. |

> Когда понадобится GCS: только при переезде на **несколько хостов**. Тогда — не «STORAGE_DRIVER=s3»
> (этот путь не подключён и потребовал бы переписать pipeline), а **общий сетевой том**
> или вынос файлового слоя. На масштабе одной воронки этого не будет.

---

## 3. Что с фотками (детально)

### Как это работает в коде (важно понимать)
- Весь pipeline жёстко использует `LocalStorage` (`from app.storage.local import local_storage`).
  Он пишет/читает **реальные файлы на диске** через `abs_path()` — Playwright делает скриншот
  HTML с диска, opencv/mediapipe валидируют фото с диска, PIL открывает файлы.
- `S3Storage` в `storage/s3.py` существует, но **ни к чему не подключён** (`STORAGE_DRIVER`
  нигде не читается). Это задел на будущее, не рабочий путь. На него не рассчитывай.
- **Раздача файлов уже приватная и правильная.** `public_url()` отдаёт не прямой линк, а
  `/api/media/<HMAC-подписанный-токен>` с TTL 1 час (`core/media.py` → `routes_media.py`
  проверяет подпись). Это и есть «signed URLs» — **чинить нечего, уже сделано как надо.**

### Проблема, которую решаем
Файлы лежат на диске. Если диск эфемерный (как named docker-volume на загрузочном диске VM),
при пересоздании VM **фото и PNG исчезнут**.

### Решение: GCE Persistent Disk
Отдельный персистентный диск, примонтированный в `/mnt/data`, bind-mount в контейнеры:
- **Durable**, переживает пересоздание VM (если не помечен auto-delete).
- **Снапшоты диска = бэкап** фоток и БД.
- **Ноль изменений в коде** — `STORAGE_DRIVER` остаётся `local`.

```bash
# создать и примонтировать диск (один раз)
gcloud compute disks create bella-data --size=50GB --zone=europe-west1-b
gcloud compute instances attach-disk bella-app --disk=bella-data --zone=europe-west1-b
# на VM: форматнуть (только при первом подключении!) и примонтировать
sudo mkfs.ext4 -F /dev/disk/by-id/google-bella-data        # ⚠️ ТОЛЬКО на новом диске
sudo mkdir -p /mnt/data && sudo mount /dev/disk/by-id/google-bella-data /mnt/data
echo '/dev/disk/by-id/google-bella-data /mnt/data ext4 discard,defaults,nofail 0 2' | sudo tee -a /etc/fstab
sudo mkdir -p /mnt/data/postgres /mnt/data/storage
```
`docker-compose.prod.yml` уже переопределяет волюмы `postgres_data` и `backend_storage`
на bind-mount к `/mnt/data`.

### Приватность — обязательно
Фото лиц = чувствительные ПДн.
- Доступ к файлам только через подписанный `/api/media/...` (уже так). Не открывай каталог наружу.
- Снапшоты диска шифруются Google по умолчанию.
- Желательно добавить периодическую чистку старых фото (cron, напр. удалять файлы старше 90 дней
  из `/mnt/data/storage` для исходных фото) — снижает риск утечки и расход места.

---

## 4. Размер VM и стоимость

| Ресурс | Конфиг | ~$/мес | Заметка |
|---|---|---|---|
| Compute Engine | **e2-standard-2** (2 vCPU, 8 ГБ) | ~$49 | Рекомендую как старт. 8 ГБ нужно из-за playwright/chromium + mediapipe. |
| — экономный | e2-medium (2 vCPU, 4 ГБ) | ~$25 | Хватит при низкой конкурентности, мониторь RAM (chromium прожорлив). |
| Persistent Disk | 50 ГБ standard | ~$2 | Файлы + БД. Снапшоты — копейки. |
| Снапшоты диска | — | ~$1–2 | Бэкап. |
| Cloudflare Pages | — | $0 | Бесплатно. |
| Egress | низкий | ~$1–5 | |

**Итого: ~$30–60/мес → $300 кредита ≈ 5–8 месяцев runway.**
(Postgres в docker — без отдельной платы за managed-БД.)

> Компромисс выбранного варианта: надёжность БД на тебе. Обязательно настрой
> **cron pg_dump → снапшот/бакет** (раздел 8), иначе потеря диска = потеря лидов.

---

## 5. Пошаговый деплой

### 5.1 Подготовка GCP
```bash
gcloud projects create bella-vladi --name="Bella Vladi"
gcloud config set project bella-vladi
gcloud services enable compute.googleapis.com
```

### 5.2 VM + персистентный диск
```bash
gcloud compute instances create bella-app \
  --machine-type=e2-standard-2 \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=30GB \
  --zone=europe-west1-b \
  --tags=http-server,https-server
```
Диск — см. раздел 3 (создать, примонтировать в `/mnt/data`, сделать каталоги).

### 5.3 Софт на VM
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # перелогиниться

git clone <repo> bella && cd bella
cp .env.example .env
nano .env                        # заполнить прод-значения (раздел 7)

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build \
  postgres redis backend \
  worker_analysis worker_report worker_after_photo worker_telegram
```
> Обрати внимание: `frontend` и `minio` в этой команде **не запускаются** (фронт на Cloudflare,
> файлы на диске). `bot_polling` тоже не нужен — работаем в webhook-режиме.

### 5.4 Frontend на Cloudflare Pages
- Подключить репозиторий, root = `apps/frontend`.
- Build command: `npm run build`, output: `dist`.
- Env: `VITE_API_URL=https://api.твойдомен.com`.

### 5.5 Домены и TLS
- `app.домен.com` → Cloudflare Pages (фронт).
- `api.домен.com` → HTTPS-доступ к бэкенду. **Рекомендуемый способ — Cloudflare Tunnel**
  (без открытых портов и без сертификатов; пошагово в `guide.md`, часть D).
  Альтернатива — Caddy на VM + Cloudflare Origin Certificate + режим Full (strict).
- ⚠️ НЕ используй режим Cloudflare «Flexible» (трафик Cloudflare→VM пойдёт плейнтекстом —
  а там пароль админа и фото лиц). Только Tunnel или Full (strict).
- HTTPS на `api` обязателен: фронт на Pages отдаётся по https, и браузер заблокирует
  любые запросы на `http://` (mixed content).

### 5.6 Telegram webhook
```env
BACKEND_URL=https://api.домен.com
TELEGRAM_WEBHOOK_URL=https://api.домен.com/api/telegram/webhook
TELEGRAM_UPDATE_MODE=webhook
TELEGRAM_WEBHOOK_SECRET=<random>
```
Backend сам ставит webhook на старте (есть Redis-lock от гонки нескольких uvicorn-воркеров).
Проверка:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

---

## 6. `docker-compose.prod.yml` (overlay) — уже создан

Базовый `docker-compose.yml` — для локалки. Prod-overlay переопределяет только прод-отличия.
Запуск: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d ...` (см. 5.3).

Что делает overlay:
- `restart: unless-stopped` на всех сервисах → авто-подъём после краша / перезагрузки VM.
- `mem_limit` на каждый сервис → chromium/playwright не съедят всю RAM хоста.
- Переопределяет волюмы `postgres_data` и `backend_storage` на **bind-mount к `/mnt/data`**
  (персистентный диск). Код и base-файл не меняются — только физическое расположение данных.

Дополнительно (вне overlay, уже внесено в base): порт Redis привязан к `127.0.0.1`,
чтобы не торчал в сеть.

---

## 7. Прод-чеклист `.env` (безопасность)

| Переменная | Действие |
|---|---|
| `JWT_SECRET` | Заменить на случайные 32+ символа (`openssl rand -hex 32`). **Также подписывает media-токены** — особенно важно. |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Сменить с дефолтных `admin@bellavladi.local` / `admin12345`. |
| `STORAGE_DRIVER` | Оставить `local` (файлы на персистентном диске). |
| `CORS_ORIGINS` | Только реальный домен фронта, не `*`. |
| `TELEGRAM_WEBHOOK_SECRET` | Задать случайный. |
| `ENABLE_AFTER_PHOTO` | На первом трафике рекомендую `false` (дорогой и тяжёлый шаг — генерация картинок). Включить когда основное стабильно. |
| `AFTER_PHOTO_PROVIDER` | ⚠️ В `config.py` дефолт `replicate`, в `.env.example` — `openai`. Зафиксировать явно под выбранного провайдера. |
| Concurrency | `ANALYSIS_WORKER_CONCURRENCY=2-4`, `TELEGRAM_WORKER_CONCURRENCY=4`. Поднимать по нагрузке. |

> ⚠️ В коде нет fail-fast при дефолтном `JWT_SECRET`. Перед публичным трафиком **обязательно**
> проверь, что секреты сменены — иначе и админка, и media-подписи уязвимы.

---

## 8. Мониторинг, бэкапы и «чтобы не упало»

1. **Авто-рестарт**: `restart: unless-stopped` (контейнеры) + GCE сам перезапускает VM при сбое хоста.
2. **Uptime-check** на `https://api.домен.com/health` (эндпоинт уже есть):
   - бесплатно: [Healthchecks.io](https://healthchecks.io) или UptimeRobot → пуш в Telegram при падении.
3. **Sentry** для ошибок backend/воркеров (внедрить — в README значится как план).
4. **Логи**: `docker compose logs -f` либо logging-driver → Cloud Logging.
5. **Длина очередей** (ранний сигнал затыка pipeline):
   ```bash
   docker compose exec redis redis-cli llen analysis
   docker compose exec redis redis-cli llen after_photo
   ```
   Растёт `analysis` и не разгребается → добавить воркеров.
6. **Бэкап БД** (критично — Postgres у тебя self-hosted):
   ```bash
   # cron на VM, ежедневно
   docker compose exec -T postgres pg_dump -U postgres bella_vladi_bot | gzip > /mnt/data/backups/db_$(date +%F).sql.gz
   ```
   Плюс **снапшоты персистентного диска** по расписанию:
   ```bash
   gcloud compute disks snapshot bella-data --zone=europe-west1-b \
     --snapshot-names=bella-data-$(date +%F)
   ```
   (можно автоматизировать через snapshot schedule policy).
7. **Диск**: алерт на заполнение `/mnt/data`.

### Масштабирование под пик
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --scale worker_analysis=3 --scale worker_telegram=2
```
8 ГБ на e2-standard-2 это вывезет. Упрёшься — вертикально до e2-standard-4.

---

## 9. Технический долг (опционально, не блокеры)

Из анализа кода — что стоит улучшить, но без чего можно стартовать:

1. **Сменить дефолтные секреты** (раздел 7) — это **блокер** перед публичным трафиком.
2. **`@app.on_event("startup")`** — deprecated в FastAPI, мигрировать на `lifespan`. Скоро сломается.
3. **Тяжёлый образ**: `worker_telegram` не нужны mediapipe/opencv/playwright. Опционально —
   отдельный лёгкий Dockerfile (экономия RAM). Не блокер.
4. **Рассинхрон README ↔ config** по `AFTER_PHOTO_PROVIDER` — зафиксировать.
5. **Удалить legacy renderers** (`protocol_v2/3/4`, `face_zone_protocol`) и неиспользуемый
   `S3Storage` — чистка мёртвого кода.

> Чего делать НЕ надо: трогать `public_url()` / media-подписи (уже корректно) и переводить
> хранилище на S3/GCS (не нужно на одной VM, потребовало бы переписать pipeline).

---

## 10. Итоговое решение (что делать прямо сейчас)

1. ✅ Фронт → **Cloudflare Pages**.
2. ✅ Backend + воркеры + redis + postgres → **один Compute Engine e2-standard-2**
   через `docker-compose.yml + docker-compose.prod.yml` (а **не** Cloud Run).
3. ✅ Файлы и БД → **персистентный диск `/mnt/data`** (переживает VM, снапшотится).
4. ✅ TLS/домен/webhook → **Cloudflare**.
5. ✅ Бэкапы → cron pg_dump + снапшоты диска.
6. ✅ Мониторинг → health-check + uptime-алерт в Telegram + Sentry.
7. ✅ Пройти прод-чеклист `.env` (секреты!).

Надёжность, простота для одного человека, ~5–8 месяцев на $300 кредита, **ноль изменений в коде**.
Cloud Run / GKE / переезд на GCS — переусложнение, которое здесь не нужно.
```
