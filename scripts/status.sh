#!/bin/bash
# scripts/status.sh
# Статус контейнеров и health DCAP (День 38).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

POSTGRES_USER="${POSTGRES_USER:-dcap}"

echo "============================================"
echo "  DCAP System — Status"
echo "============================================"
echo ""

docker compose ps

echo ""
echo "============================================"
echo "  Health"
echo "============================================"

# Проверка Manager
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ Manager: healthy"
else
    echo "❌ Manager: unhealthy"
fi

# Проверка WebUI
if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ WebUI: healthy"
else
    echo "❌ WebUI: unhealthy"
fi

# Проверка PostgreSQL
if docker compose exec -T postgres pg_isready -U "$POSTGRES_USER" > /dev/null 2>&1; then
    echo "✅ PostgreSQL: healthy"
else
    echo "❌ PostgreSQL: unhealthy"
fi

# Проверка Redis
if docker compose exec -T redis redis-cli --no-auth-warning ping > /dev/null 2>&1; then
    echo "✅ Redis: healthy"
else
    echo "❌ Redis: unhealthy"
fi