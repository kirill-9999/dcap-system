#!/bin/bash
# scripts/test-up.sh
# Полный сброс + поднятие тестового стека.
# -v удаляет volume postgres (чистая БД), redis tmpfs теряется автоматически.
set -e

docker compose -f docker-compose.test.yml down -v 2>/dev/null || true
docker compose -f docker-compose.test.yml up -d --build
echo "Waiting for services..."
until curl -sf http://localhost:18000/api/health > /dev/null 2>&1; do sleep 2; done
until curl -sf http://localhost:18001/health > /dev/null 2>&1; do sleep 2; done
echo "✅ Test stack ready"
