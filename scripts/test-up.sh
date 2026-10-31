#!/bin/bash
# scripts/test-up.sh
# Полный сброс + поднятие тестового стека.
# День 53.3-test-stand-fix: логика стенда живёт в scripts/run-tests.sh (stand),
# здесь только делегирование с пересборкой образов.
set -e

cd "$(dirname "$0")/.."
exec ./scripts/run-tests.sh stand --build
