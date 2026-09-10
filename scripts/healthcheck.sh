#!/bin/bash
# scripts/healthcheck.sh
# Проверка здоровья DCAP (День 38). Возвращает 0 — всё ОК, 1 — есть сбои.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

ERRORS=0

check_service() {
    local name=$1
    local url=$2
    local port=${3:-}

    if [ -n "$port" ]; then
        url="http://localhost:${port}${url#http://localhost:${port}}"
    fi

    if curl -sf "$url" > /dev/null 2>&1; then
        echo "✅ $name: OK"
    else
        echo "❌ $name: FAILED ($url)"
        ERRORS=$((ERRORS + 1))
    fi
}

echo "🏥 Running healthcheck..."
echo ""

check_service "Manager" "http://localhost:8000/api/health"
check_service "WebUI" "http://localhost:8001/health"

if [ $ERRORS -eq 0 ]; then
    echo ""
    echo "✅ All services healthy"
    exit 0
else
    echo ""
    echo "❌ $ERRORS service(s) failed"
    exit 1
fi