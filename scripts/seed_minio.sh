#!/usr/bin/env bash
# scripts/seed_minio.sh — создаёт bucket dcap-audit-logs и загружает тестовые
# access-логи из scripts/minio-seed/access-logs/ (Блок 6.3, фикс BUG-120).
#
# Запускается на хосте (Git Bash / WSL / Linux). Использует одноразовый контейнер
# minio/mc, подключённый к внешней сети dcap-network, поэтому mc видит MinIO как
# http://minio:9000 — именно так к нему ходит S3-агент.
#
#   ./scripts/seed_minio.sh
#
# Переменные окружения (по умолчанию — dev-значения MinIO):
#   MINIO_ENDPOINT   хост MinIO изнутри docker-сети (default: minio:9000)
#   MINIO_ACCESS_KEY (default: minioadmin)
#   MINIO_SECRET_KEY (default: minioadmin)
#   MINIO_BUCKET     (default: dcap-audit-logs)
#   MINIO_PREFIX     (default: access-logs/)
set -euo pipefail

MINIO_ENDPOINT="${MINIO_ENDPOINT:-minio:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
MINIO_BUCKET="${MINIO_BUCKET:-dcap-audit-logs}"
MINIO_PREFIX="${MINIO_PREFIX:-access-logs/}"
NETWORK="${DOCKER_NETWORK:-dcap-network}"

SEED_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/minio-seed"

echo "[seed_minio] endpoint=${MINIO_ENDPOINT} bucket=${MINIO_BUCKET} prefix=${MINIO_PREFIX}"
echo "[seed_minio] network=${NETWORK} seed=${SEED_DIR}"

if [ ! -d "${SEED_DIR}/access-logs" ]; then
  echo "[seed_minio] ОШИБКА: нет каталога ${SEED_DIR}/access-logs" >&2
  exit 1
fi

docker run --rm \
  --network "${NETWORK}" \
  -v "${SEED_DIR}:/seed:ro" \
  minio/mc:latest \
  sh -c "
    set -e
    mc alias set dcap http://${MINIO_ENDPOINT} ${MINIO_ACCESS_KEY} ${MINIO_SECRET_KEY}
    mc mb --ignore-existing dcap/${MINIO_BUCKET}
    mc cp --recursive /seed/access-logs/ dcap/${MINIO_BUCKET}/${MINIO_PREFIX}
    echo '--- содержимое bucket ---'
    mc ls --recursive dcap/${MINIO_BUCKET}
  "

echo "[seed_minio] готово"
