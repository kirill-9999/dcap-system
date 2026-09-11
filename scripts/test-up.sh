#!/bin/bash
# scripts/test-up.sh
# Поднятие изолированного тестового стека (docker-compose.test.yml).
set -e

docker compose -f docker-compose.test.yml up -d --build
echo "Waiting for services..."
until curl -sf http://localhost:18000/api/health > /dev/null; do sleep 2; done
until curl -sf http://localhost:18001/health > /dev/null; do sleep 2; done
echo "✅ Test stack ready"