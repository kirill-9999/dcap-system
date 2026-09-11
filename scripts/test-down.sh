#!/bin/bash
# scripts/test-down.sh
# Остановка изолированного тестового стека (без удаления образов).
set -e

docker compose -f docker-compose.test.yml down
echo "✅ Test stack stopped"