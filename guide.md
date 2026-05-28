# GUIDE — деплой Bella Vladi Face Protocol с нуля

Пошаговый гайд для новичка. Доводим проект до прода:
- **Backend + воркеры + Redis + Postgres** → одна VM в Google Cloud (docker-compose).
- **Файлы и БД** → персистентный диск (переживает пересоздание VM, снапшотится).
- **Frontend (админка + публичный отчёт)** → Cloudflare Pages (бесплатно, CDN).
- **HTTPS для бэкенда** → Cloudflare Tunnel (без открытых портов и без возни с сертификатами).

> Архитектурное «почему» — в `infrastructure.md`. Здесь — только «как». Делай по порядку.

Легенда: `ЗАМЕНИ_...` — подставь своё значение. `$ ` — команда в терминале.

---

## Карта того, что получится

```
   Браузер / Telegram
        │
        ├─ https://app.ЗАМЕНИ_ДОМЕН.com   → Cloudflare Pages (фронт: админка + /report/:token)
        │                                     │ fetch
        └─ https://api.ЗАМЕНИ_ДОМЕН.com   ───┘ → Cloudflare Tunnel → VM:backend:8000
                                                  │
                                   ┌──────────────┴───────────────┐
                                   │ VM (Compute Engine)          │
                                   │ docker compose:              │
                                   │   backend, 4 воркера,        │
                                   │   redis, postgres,           │
                                   │   cloudflared (туннель)      │
                                   │ /mnt/data (персистентный диск)│
                                   │   ├ postgres/  (база)        │
                                   │   └ storage/   (фото, PNG)   │
                                   └──────────────────────────────┘
```

Два домена:
- `app.ЗАМЕНИ_ДОМЕН.com` — фронт (Cloudflare Pages).
- `api.ЗАМЕНИ_ДОМЕН.com` — бэкенд (через туннель на VM).

---

## 0. Что нужно подготовить заранее

1. **Аккаунт Google Cloud** с активированными $300 кредитами и привязанной картой (для проверки).
2. **Аккаунт Cloudflare** (бесплатный).
3. **Домен**, заведённый в Cloudflare (NS Cloudflare). Если домена нет — купи любой и добавь в Cloudflare (это бесплатно для управления DNS).
4. **Telegram bot token** от @BotFather.
5. **Ключи AI** — `GEMINI_API_KEY` и/или `OPENAI_API_KEY` (по тому, что используешь). Можно стартовать в mock-режиме без них.
6. На своём компьютере установлен **gcloud CLI** (или будешь всё делать через веб-консоль GCP — тоже ок).

> Если `gcloud` не установлен: можно выполнять все команды в **Cloud Shell** прямо в браузере (кнопка `>_` вверху консоли console.cloud.google.com). Там gcloud уже есть.

---

## Часть A. Google Cloud: VM + персистентный диск

### A1. Создать проект и включить API
```bash
$ gcloud auth login
$ gcloud projects create bella-vladi-prod --name="Bella Vladi"
$ gcloud config set project bella-vladi-prod
$ gcloud services enable compute.googleapis.com
```
> Если `projects create` ругается на billing — привяжи billing-аккаунт в консоли: Billing → Link a billing account.

### A2. Создать VM
```bash
$ gcloud compute instances create bella-app \
    --project=bella-vladi-prod \
    --zone=europe-west1-b \
    --machine-type=e2-standard-2 \
    --image-family=debian-12 --image-project=debian-cloud \
    --boot-disk-size=30GB
```
- `e2-standard-2` = 2 vCPU, 8 ГБ RAM (нужно из-за chromium/playwright + mediapipe).
- Зону `europe-west1-b` можешь поменять на ближе к аудитории.

### A3. Создать и подключить персистентный диск (для файлов и БД)
```bash
$ gcloud compute disks create bella-data --size=50GB --type=pd-standard --zone=europe-west1-b
$ gcloud compute instances attach-disk bella-app --disk=bella-data --zone=europe-west1-b
```

### A4. Зайти на VM по SSH
```bash
$ gcloud compute ssh bella-app --zone=europe-west1-b
```
Дальше все команды (до части E) выполняются **внутри VM**.

### A5. Отформатировать и примонтировать диск (ТОЛЬКО первый раз)
```bash
# проверь имя устройства (обычно /dev/sdb)
$ lsblk
# отформатировать — ВНИМАНИЕ: только на новом пустом диске, иначе сотрёшь данные!
$ sudo mkfs.ext4 -F -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/disk/by-id/google-bella-data
# примонтировать в /mnt/data
$ sudo mkdir -p /mnt/data
$ sudo mount -o discard,defaults /dev/disk/by-id/google-bella-data /mnt/data
# чтобы монтировался автоматически после перезагрузки
$ echo '/dev/disk/by-id/google-bella-data /mnt/data ext4 discard,defaults,nofail 0 2' | sudo tee -a /etc/fstab
# создать папки под БД и файлы
$ sudo mkdir -p /mnt/data/postgres /mnt/data/storage /mnt/data/backups
```
Проверка:
```bash
$ df -h /mnt/data       # должен показать ~50G на /mnt/data
```

### A6. Установить Docker
```bash
$ curl -fsSL https://get.docker.com | sudo sh
$ sudo usermod -aG docker $USER
$ exit          # выйти из SSH и зайти снова, чтобы группа docker применилась
```
Зайди обратно:
```bash
$ gcloud compute ssh bella-app --zone=europe-west1-b
$ docker version    # должно работать без sudo
```

---

## Часть B. Код и `.env` на VM

### B1. Получить код на VM
Вариант 1 — если репозиторий в Git:
```bash
$ git clone ЗАМЕНИ_URL_РЕПОЗИТОРИЯ bella && cd bella
```
Вариант 2 — если репозитория нет, скопировать с локального компа (выполнять **на своём компе**, не на VM):
```bash
$ gcloud compute scp --recurse --zone=europe-west1-b \
    /Users/valtzmanmagnus/Desktop/facefit bella-app:~/bella
```
Потом на VM: `cd ~/bella`.

### B2. Создать и заполнить `.env`
```bash
$ cp .env.example .env
$ nano .env
```
Заполни **обязательные** значения (остальное можно оставить дефолтным):

```env
# --- адреса (ВАЖНО: api и app — разные сабдомены) ---
BACKEND_URL=https://api.ЗАМЕНИ_ДОМЕН.com
FRONTEND_URL=https://app.ЗАМЕНИ_ДОМЕН.com
PUBLIC_APP_URL=https://app.ЗАМЕНИ_ДОМЕН.com
CORS_ORIGINS=["https://app.ЗАМЕНИ_ДОМЕН.com"]

# --- БД и Redis: внутри docker-сети, НЕ меняем хосты ---
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/bella_vladi_bot
REDIS_URL=redis://redis:6379/0

# --- безопасность: СГЕНЕРИРУЙ заново! ---
JWT_SECRET=ЗАМЕНИ_СЛУЧАЙНАЯ_СТРОКА_32+   # сгенерируй: openssl rand -hex 32
ADMIN_EMAIL=ЗАМЕНИ_свой@email.com
ADMIN_PASSWORD=ЗАМЕНИ_СИЛЬНЫЙ_ПАРОЛЬ

# --- Telegram ---
TELEGRAM_BOT_TOKEN=ЗАМЕНИ_ТОКЕН_ОТ_BOTFATHER
TELEGRAM_UPDATE_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://api.ЗАМЕНИ_ДОМЕН.com/api/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=ЗАМЕНИ_СЛУЧАЙНАЯ_СТРОКА   # openssl rand -hex 16
TELEGRAM_BOT_USERNAME=ЗАМЕНИ_имя_бота_без_@

# --- AI (можно пусто для mock-режима на старте) ---
GEMINI_API_KEY=
OPENAI_API_KEY=

# --- хранилище: локальный диск (= персистентный диск через монтирование) ---
STORAGE_DRIVER=local
LOCAL_STORAGE_PATH=/app/storage

# --- after-photo лучше выключить на старте (дорого/тяжело) ---
ENABLE_AFTER_PHOTO=false
```

Сгенерировать секреты прямо на VM:
```bash
$ openssl rand -hex 32     # для JWT_SECRET
$ openssl rand -hex 16     # для TELEGRAM_WEBHOOK_SECRET
```
Сохрани файл в nano: `Ctrl+O`, `Enter`, `Ctrl+X`.

> ⚠️ `JWT_SECRET` подписывает и админ-сессии, и ссылки на фото (`/api/media/...`). Обязательно смени с дефолта.

---

## Часть C. Запуск backend на VM

Запускаем **только нужные в проде** сервисы (без `frontend` — он на Cloudflare; без `minio` — файлы на диске; без `bot_polling` — у нас webhook):

```bash
$ docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build \
    postgres redis backend \
    worker_analysis worker_report worker_after_photo worker_telegram
```
Первый раз собирается долго (тяжёлый образ с chromium/mediapipe) — это нормально, 5–15 минут.

Backend при старте сам: применит миграции (`alembic upgrade head`), создаст админа и дефолтные настройки (`python -m app.db.seed`), поднимет API.

### C1. Проверить, что бэкенд жив (локально на VM)
```bash
$ curl http://localhost:8000/health
# ожидаем: {"ok":true,"service":"bella-vladi-face-protocol"}
$ docker compose ps                 # все сервисы Up
$ docker compose logs --tail=50 backend
```
Если `/health` отвечает — backend работает. Снаружи он пока недоступен (это сделаем туннелем в части D).

---

## Часть D. HTTPS для бэкенда через Cloudflare Tunnel (рекомендую)

Туннель даёт `https://api.домен.com` **без открытых портов на VM и без сертификатов**. Cloudflare сам терминирует HTTPS, трафик до VM идёт по защищённому туннелю.

### D1. Создать туннель в панели Cloudflare
1. Cloudflare → **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**.
2. Тип: **Cloudflared**. Назови, например, `bella-api`. **Save**.
3. На шаге «Install connector» выбери **Docker** — Cloudflare покажет команду с токеном вида
   `cloudflared tunnel run --token eyJ...`. **Скопируй сам токен** (длинная строка после `--token`).
4. Перейди на вкладку **Public Hostnames** → **Add a public hostname**:
   - Subdomain: `api`
   - Domain: `ЗАМЕНИ_ДОМЕН.com`
   - Service: **HTTP** → `backend:8000`
   - Save.

### D2. Запустить cloudflared рядом с проектом (на VM)
Положи токен в `.env` на VM:
```bash
$ echo 'CLOUDFLARE_TUNNEL_TOKEN=ЗАМЕНИ_ТОКЕН_ТУННЕЛЯ' >> .env
```
Создай файл `docker-compose.tunnel.yml` в корне проекта:
```bash
$ nano docker-compose.tunnel.yml
```
Вставь:
```yaml
services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on:
      - backend
```
Подними туннель (добавляем третий compose-файл):
```bash
$ docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.tunnel.yml up -d cloudflared
```
> Почему `backend:8000`: cloudflared в одной docker-сети с backend и видит его по имени `backend`. Никакие порты VM наружу открывать не нужно.

### D3. Проверить HTTPS снаружи
С любого компьютера:
```bash
$ curl https://api.ЗАМЕНИ_ДОМЕН.com/health
# ожидаем: {"ok":true,...}
```
Если ответ есть — бэкенд доступен по HTTPS. 🎉

<details>
<summary><b>Альтернатива (если не хочешь туннель): Caddy + Cloudflare Origin Certificate</b></summary>

1. Cloudflare → SSL/TLS → **Origin Server** → Create Certificate → сохрани `cert.pem` и `key.pem` на VM.
2. Cloudflare → SSL/TLS → Overview → режим **Full (strict)**.
3. DNS: A-запись `api` → внешний IP VM, проксирование **включено** (оранжевое облако).
4. Открой порты 80/443 в firewall GCP, поставь Caddy с `tls /path/cert.pem /path/key.pem` и `reverse_proxy backend:8000`.

Туннель проще и безопаснее (не светит IP, не открывает порты), поэтому он — основной путь.
</details>

---

## Часть E. Frontend на Cloudflare Pages

Здесь отвечаем на твой вопрос: **какая API на выдаче и куда обращается фронт.**

### Как фронт общается с API (важно понять)
- В сборку фронта «зашивается» переменная **`VITE_API_URL`**. Весь код шлёт запросы на `${VITE_API_URL}/api/...` (см. `apps/frontend/src/api/client.ts`).
- Поэтому при сборке на Cloudflare Pages мы задаём `VITE_API_URL=https://api.ЗАМЕНИ_ДОМЕН.com`.
- Тогда:
  - админка → `https://api.домен.com/api/...` (с токеном в заголовке `Authorization`),
  - публичный отчёт `/report/:token` → `https://api.домен.com/api/reports/:token` (без токена, он публичный),
  - картинки (фото/PNG) приходят абсолютными ссылками `https://api.домен.com/api/media/<подпись>` и грузятся напрямую с бэка.
- CORS на бэкенде уже разрешит `https://app.домен.com` (мы задали `CORS_ORIGINS`/`FRONTEND_URL`/`PUBLIC_APP_URL`).

> ⚠️ Если НЕ задать `VITE_API_URL` — фронт по умолчанию решит, что API на том же домене (`app.домен.com`), где бэкенда нет, и **все запросы упадут с 404**. Это пункт №1 в чек-листе ошибок.

### E1. Создать проект в Cloudflare Pages
1. Cloudflare → **Workers & Pages** → **Create** → **Pages** → **Connect to Git** → выбери репозиторий.
   (Если репозитория в Git нет — см. E4 «деплой без Git».)
2. Настройки сборки:
   - **Framework preset:** None (или Vite).
   - **Root directory:** `apps/frontend`
   - **Build command:** `npm run build`
   - **Build output directory:** `dist`
3. **Environment variables** → добавь:
   - `VITE_API_URL` = `https://api.ЗАМЕНИ_ДОМЕН.com`
4. **Save and Deploy.**

### E2. SPA-роутинг (уже подготовлено)
В репозитории есть файл `apps/frontend/public/_redirects` с правилом `/*  /index.html  200`.
Vite копирует его в `dist`, и Cloudflare Pages начинает отдавать `index.html` на все клиентские
маршруты (`/login`, `/report/:token`, `/admin/*`). Без него прямой заход на `/report/abc` давал бы 404.

### E3. Привязать домен `app`
1. В проекте Pages → **Custom domains** → **Set up a custom domain** → `app.ЗАМЕНИ_ДОМЕН.com`.
2. Cloudflare сам добавит DNS и выдаст HTTPS. Готово.

### E4. (Если нет Git) деплой через Wrangler
На своём компе:
```bash
$ cd apps/frontend
$ npm install
$ VITE_API_URL=https://api.ЗАМЕНИ_ДОМЕН.com npm run build
$ npx wrangler pages deploy dist --project-name=bella-admin
```

---

## Часть F. Telegram webhook

`TELEGRAM_WEBHOOK_URL` уже в `.env`. Backend ставит webhook автоматически при старте.
Чтобы переустановить (например, после смены домена) — перезапусти backend:
```bash
$ docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend
```
Проверка, что Telegram видит webhook:
```bash
$ curl "https://api.telegram.org/botЗАМЕНИ_ТОКЕН/getWebhookInfo"
# смотри: "url": "https://api.домен.com/api/telegram/webhook", "pending_update_count": 0
```
Если `url` пустой или с ошибкой — смотри `docker compose logs backend | grep -i webhook`.

---

## Часть G. Финальная проверка end-to-end

1. **Backend:** `curl https://api.домен.com/health` → ok.
2. **Админка:** открой `https://app.домен.com/login`, войди под `ADMIN_EMAIL`/`ADMIN_PASSWORD`. Видишь дашборд → фронт↔бэк↔CORS работают.
3. **Бот:** напиши боту `/start` в Telegram, пройди сценарий (согласие → имя → фото → зоны).
4. **Очереди:** на VM смотри, как разгребается:
   ```bash
   $ docker compose exec redis redis-cli llen analysis
   $ docker compose logs -f worker_analysis
   ```
5. **Отчёт:** бот пришлёт PNG + ссылку `https://app.домен.com/report/<token>`. Открой — отчёт и фото грузятся.

Если все 5 пунктов прошли — ты в проде. 🎉

---

## Часть H. Бэкапы и мониторинг (не пропускай!)

У тебя Postgres self-hosted, поэтому бэкапы — на тебе.

### H1. Ежедневный дамп БД (cron на VM)
```bash
$ crontab -e
```
Добавь строку (дамп в 3:30 ночи в папку на персистентном диске):
```cron
30 3 * * * cd /home/$USER/bella && docker compose exec -T postgres pg_dump -U postgres bella_vladi_bot | gzip > /mnt/data/backups/db_$(date +\%F).sql.gz
```

### H2. Снапшоты диска по расписанию (бэкап и фото, и БД)
На своём компе/Cloud Shell:
```bash
$ gcloud compute resource-policies create snapshot-schedule bella-daily \
    --region=europe-west1 --max-retention-days=14 \
    --start-time=02:00 --daily-schedule
$ gcloud compute disks add-resource-policies bella-data \
    --resource-policies=bella-daily --zone=europe-west1-b
```

### H3. Мониторинг «упало/не упало»
- Заведи бесплатный аккаунт на **healthchecks.io** или **UptimeRobot**, добавь проверку `https://api.домен.com/health` с алертом в Telegram/почту.
- Авто-рестарт контейнеров уже включён (`restart: unless-stopped` в prod-overlay), VM сама перезапускается при сбое хоста.

### H4. Масштабирование под пик (если очередь копится)
```bash
$ docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    up -d --scale worker_analysis=3 --scale worker_telegram=2
```

---

## Часть I. Обновление кода (релизы)
```bash
$ cd ~/bella
$ git pull                      # или заново scp, если без Git
$ docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build \
    backend worker_analysis worker_report worker_after_photo worker_telegram
```
Фронт обновляется сам при push в Git (если подключил Pages к репозиторию).

---

## Troubleshooting (частые проблемы)

| Симптом | Причина | Решение |
|---|---|---|
| Админка открывается, но запросы падают / белый экран | Не задан `VITE_API_URL` при сборке Pages | Добавь env `VITE_API_URL=https://api.домен.com` в Pages и пере-задеплой |
| В консоли браузера `Mixed Content` / `blocked:mixed` | `VITE_API_URL` указывает на `http://...` | Должно быть `https://api.домен.com` |
| `CORS error` в консоли | `CORS_ORIGINS`/`FRONTEND_URL` не совпадают с доменом фронта | Выстави их точно в `https://app.домен.com`, перезапусти backend |
| Прямой заход на `/report/abc` → 404 | Нет `_redirects` в `dist` | Проверь, что `apps/frontend/public/_redirects` попал в сборку |
| `getWebhookInfo` пустой / ошибка SSL | Туннель/HTTPS не поднят или `BACKEND_URL` не https | Проверь `curl https://api.домен.com/health`, потом `restart backend` |
| Картинки в отчёте не грузятся | `BACKEND_URL` не задан/не https → media-ссылки битые | Выстави `BACKEND_URL=https://api.домен.com`, перезапусти backend |
| Фото/база пропали после пересоздания VM | Данные были не на персистентном диске | Проверь `df -h /mnt/data` и что volume'ы смотрят в `/mnt/data` (prod-overlay) |
| Bot молчит | Нет `TELEGRAM_BOT_TOKEN` или webhook не стоит | Логи `docker compose logs backend`, проверь токен и `getWebhookInfo` |

Полезные команды:
```bash
$ docker compose ps
$ docker compose logs -f backend
$ docker compose logs -f worker_analysis
$ docker compose exec redis redis-cli llen analysis
$ df -h /mnt/data
```

---

## Финальный чек-лист перед трафиком

- [ ] `JWT_SECRET` и `ADMIN_PASSWORD` сменены с дефолтных
- [ ] `BACKEND_URL` / `FRONTEND_URL` / `PUBLIC_APP_URL` / `CORS_ORIGINS` указывают на реальные https-домены
- [ ] `curl https://api.домен.com/health` отвечает ok
- [ ] Админка логинится на `https://app.домен.com/login`
- [ ] `VITE_API_URL` задан в Cloudflare Pages
- [ ] Бот проходит полный сценарий и присылает отчёт
- [ ] `getWebhookInfo` показывает правильный url, `pending_update_count` не растёт
- [ ] Настроены cron-дамп БД и снапшоты диска
- [ ] Подключён uptime-мониторинг `/health` с алертом
- [ ] (опц.) `ENABLE_AFTER_PHOTO` включишь после стабилизации основного потока
```
