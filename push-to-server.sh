#!/usr/bin/env bash
#
# push-to-server.sh — залить локальный код на сервер по rsync и сразу
# пересобрать/перезапустить контейнеры. Запускать НА ЛОКАЛЬНОЙ МАШИНЕ:
#
#     ./push-to-server.sh                  # синк + ребилд backend и воркеров
#     ./push-to-server.sh frontend         # дополнительно ребилднуть frontend
#     ./push-to-server.sh worker_analysis  # ребилднуть только один сервис
#     NO_BUILD=1 ./push-to-server.sh       # только синк, без пересборки
#     DRY_RUN=1  ./push-to-server.sh       # показать, что синканётся, и выйти
#     PRUNE=1    ./push-to-server.sh       # + удалить на сервере файлы, которых нет локально (rsync --delete)
#
# По умолчанию ничего на сервере НЕ удаляется — файлы только добавляются и
# обновляются. Удаление устаревших файлов включается флагом PRUNE=1.
#
# Что НЕ перезаписывается на сервере (исключено из rsync): .env, .git,
# storage с готовыми PNG, node_modules, .venv, dist, __pycache__.
#
set -euo pipefail

# ── настройки ─────────────────────────────────────────────────────────────
SSH_KEY="${SSH_KEY:-$HOME/.ssh/facefit}"
REMOTE="${REMOTE:-facefit@34.107.61.101}"
REMOTE_DIR="${REMOTE_DIR:-/opt/facefit}"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Сервисы для пересборки (можно переопределить аргументами скрипта).
DEFAULT_SERVICES="backend worker_analysis worker_report worker_telegram"
SERVICES="${*:-$DEFAULT_SERVICES}"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.tunnel.yml"
SSH="ssh -i $SSH_KEY"

# ── 1) rsync кода ─────────────────────────────────────────────────────────
echo "==> 1/2 Синхронизирую код  $LOCAL_DIR  ->  $REMOTE:$REMOTE_DIR"

RSYNC_FLAGS=(-az --human-readable --info=stats1)
[ -n "${PRUNE:-}" ]   && RSYNC_FLAGS+=(--delete) && echo "    (PRUNE=1 — устаревшие файлы на сервере будут удалены)"
[ -n "${VERBOSE:-}" ] && RSYNC_FLAGS+=(-v)
[ -n "${DRY_RUN:-}" ] && RSYNC_FLAGS+=(--dry-run --verbose)

rsync "${RSYNC_FLAGS[@]}" \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude 'node_modules/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude '.DS_Store' \
  --exclude '*.log' \
  --exclude 'apps/backend/storage/' \
  --exclude 'apps/frontend/dist/' \
  -e "$SSH" \
  "$LOCAL_DIR/" "$REMOTE:$REMOTE_DIR/"

if [ -n "${DRY_RUN:-}" ]; then
  echo "DRY_RUN — пересборку пропускаю."
  exit 0
fi

if [ -n "${NO_BUILD:-}" ]; then
  echo "NO_BUILD — код залит, контейнеры не трогаю."
  exit 0
fi

# ── 2) пересборка и перезапуск на сервере ────────────────────────────────
echo "==> 2/2 Пересобираю и перезапускаю: $SERVICES"
# shellcheck disable=SC2029
$SSH "$REMOTE" "cd $REMOTE_DIR && $COMPOSE up -d --build $SERVICES"

echo "==> Проверяю /health..."
if $SSH "$REMOTE" "curl -fsS http://localhost:8000/health >/dev/null 2>&1"; then
  echo "✅ Готово — backend отвечает на /health."
else
  echo "⚠️  Контейнеры перезапущены, но /health не ответил. Логи:"
  echo "    $SSH $REMOTE \"cd $REMOTE_DIR && $COMPOSE logs --tail=50 backend\""
fi

echo
echo "ℹ️  Старые отчёты закэшированы — чтобы увидеть новый протокол,"
echo "    прогони НОВЫЙ анализ (новое фото в бот) или перегенерируй PNG."
