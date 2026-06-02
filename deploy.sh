#!/usr/bin/env bash
#
# deploy.sh — обновить и перезапустить приложение на сервере.
#
# Запускать НА СЕРВЕРЕ под пользователем `facefit`:
#     cd /opt/facefit && ./deploy.sh
#
# Что делает:
#   1) тянет свежий код из GitHub (git pull)
#   2) пересобирает и перезапускает контейнеры
#   3) проверяет, что backend жив (/health)
#   4) (опц.) шлёт статус в Telegram, если в .env заданы TELEGRAM_*
#
set -euo pipefail

PROJECT_DIR="/opt/facefit"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.tunnel.yml"
SERVICES="backend worker_analysis worker_report worker_after_photo worker_telegram"

cd "$PROJECT_DIR"

# --- опциональные Telegram-уведомления (берём токен/чат из .env, если есть) ---
TG_TOKEN=""; TG_CHAT=""; TG_THREAD=""
if [ -f .env ]; then
  TG_TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' .env | head -1 | cut -d= -f2- || true)
  TG_CHAT=$(grep -E '^TELEGRAM_CHAT_ID='   .env | head -1 | cut -d= -f2- || true)
  TG_THREAD=$(grep -E '^TELEGRAM_THREAD_ID=' .env | head -1 | cut -d= -f2- || true)
fi
notify() {
  [ -n "$TG_TOKEN" ] && [ -n "$TG_CHAT" ] || return 0
  curl -s "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    -d chat_id="${TG_CHAT}" \
    ${TG_THREAD:+-d message_thread_id="${TG_THREAD}"} \
    -d parse_mode=HTML \
    --data-urlencode "text=$1" >/dev/null 2>&1 || true
}

# если что-то упадёт — сообщим и в Telegram
trap 'echo "❌ Деплой ПРЕРВАН на ошибке"; notify "❌ <b>Деплой упал</b> на сервере facefit"; exit 1' ERR

echo "==> 1/4 Тяну свежий код из GitHub..."
notify "🚀 <b>Деплой начат</b> на сервере facefit"
git pull --ff-only

echo "==> 2/4 Пересобираю и перезапускаю контейнеры..."
# shellcheck disable=SC2086
$COMPOSE up -d --build $SERVICES

echo "==> 3/4 Жду запуск (15 секунд)..."
sleep 15

echo "==> 4/4 Проверяю /health..."
if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
  echo "✅ Деплой успешен — backend отвечает на /health"
  notify "✅ <b>Деплой завершён</b> — backend отвечает, /health OK"
else
  echo "❌ Контейнеры запущены, но /health не отвечает. Смотри логи:"
  echo "   $COMPOSE logs --tail=50 backend"
  notify "⚠️ <b>Деплой завершён, но /health не отвечает</b> — проверь логи backend"
  exit 1
fi

echo "Готово."
