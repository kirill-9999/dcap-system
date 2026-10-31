#!/bin/bash
# scripts/deploy.sh
# Полный деплой DCAP (День 38).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "============================================"
echo "  DCAP System — Deployment"
echo "============================================"

# 1. Проверка .env
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "   Copy .env.example to .env and configure"
    exit 1
fi

# 2. Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose not installed"
    exit 1
fi

# 3. Проверка сертификатов (если mTLS включен)
if grep -q "MTLS_ENABLED=true" .env 2>/dev/null; then
    if [ ! -d "certs/ca" ]; then
        echo "⚠️  mTLS enabled but certificates not found"
        echo "   Run: python scripts/generate_certs.py"
        exit 1
    fi
fi

# 4. Сборка образов
echo ""
echo "📦 Building Docker images..."
docker compose build

# 5. Запуск
echo ""
echo "🚀 Starting services..."
docker compose up -d

# 6. Ожидание готовности
echo ""
echo "⏳ Waiting for services..."
sleep 15

# 7. Проверка статуса
echo ""
echo "📊 Service status:"
docker compose ps

# 8. Healthcheck
echo ""
echo "🏥 Healthcheck..."
./scripts/healthcheck.sh

echo ""
echo "============================================"
echo "  ✅ DCAP deployed successfully!"
echo "============================================"
echo ""
echo "  WebUI:    http://localhost:${WEBUI_PORT:-8001}"
echo "  Manager:  http://localhost:${MANAGER_PORT:-8000}"
echo "  Flower:   http://localhost:${FLOWER_PORT:-5555}"
echo ""
echo "  S3-агент (profile agents): docker compose --profile agents up -d"
echo ""