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

echo ""
echo "============================================"
echo "  Monitoring (День 39)"
echo "============================================"

# Prometheus
if curl -sf http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus: healthy"
else
    echo "❌ Prometheus: unhealthy"
fi

# Grafana
if curl -sf http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "✅ Grafana: healthy"
else
    echo "❌ Grafana: unhealthy"
fi

# Alertmanager
if curl -sf http://localhost:9093/-/healthy > /dev/null 2>&1; then
    echo "✅ Alertmanager: healthy"
else
    echo "❌ Alertmanager: unhealthy"
fi

# Экспортеры
for svc in postgres_exporter:9187 redis_exporter:9121 celery_exporter:9808; do
    name="${svc%%:*}"
    port="${svc##*:}"
    if curl -sf "http://localhost:${port}/metrics" > /dev/null 2>&1; then
        echo "✅ ${name}: healthy"
    else
        echo "❌ ${name}: unhealthy"
    fi
done