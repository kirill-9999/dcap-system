#!/bin/bash
# scripts/monitoring-status.sh
# Проверка мониторинга DCAP (День 39): targets Prometheus, health Grafana, алерты.
#
# Использование:
#   ./scripts/monitoring-status.sh          # полный вывод
#   ./scripts/monitoring-status.sh -q       # только проблемы (для cron)

set -u

QUIET=""
while [ $# -gt 0 ]; do
    case "$1" in
        -q|--quiet) QUIET="1" ;;
        *) echo "Usage: $0 [-q|--quiet]" >&2; exit 2 ;;
    esac
    shift
done

PROMETHEUS="http://localhost:9090"
GRAFANA="http://localhost:3000"
ALERTMANAGER="http://localhost:9093"

FAILED=0

say() {
    if [ -z "$QUIET" ]; then
        echo "$@"
    fi
}

# ==== 1. Targets Prometheus ====
say "============================================"
say "  DCAP System — Monitoring Status"
say "============================================"
say ""

if curl -sf "$PROMETHEUS/-/healthy" > /dev/null 2>&1; then
    say "✅ Prometheus: healthy"
else
    say "❌ Prometheus: unhealthy (не запущен? docker compose up -d)"
    FAILED=1
    [ -n "$QUIET" ] && echo "prometheus: down"
fi

if curl -sf "$GRAFANA/api/health" > /dev/null 2>&1; then
    say "✅ Grafana: healthy  →  http://localhost:3000"
else
    say "❌ Grafana: unhealthy"
    [ -n "$QUIET" ] && echo "grafana: down"
fi

if curl -sf "$ALERTMANAGER/-/healthy" > /dev/null 2>&1; then
    say "✅ Alertmanager: healthy  →  http://localhost:9093"
else
    say "❌ Alertmanager: unhealthy"
    [ -n "$QUIET" ] && echo "alertmanager: down"
fi

# ==== 2. Targets (up/down) ====
TARGETS=$(curl -sf "$PROMETHEUS/api/v1/targets" 2>/dev/null | \
    python -c "import sys,json; d=json.load(sys.stdin); [print(f\"{t['labels'].get('job','?'):12} {t['labels'].get('instance','?'):30} {t['health']}\") for t in d.get('data',{}).get('activeTargets',[])]" 2>/dev/null)

if [ -n "$TARGETS" ]; then
    say "----- Prometheus targets -----"
    say "job           instance                                 health"
    say "$TARGETS"
    DOWN=$(echo "$TARGETS" | awk '$NF != "up" {print}')
    if [ -n "$DOWN" ]; then
        say "❌ Есть targets не в статусе UP:"
        say "$DOWN"
        [ -n "$QUIET" ] && echo "$DOWN" | while read -r l; do echo "target down: $l"; done
        FAILED=1
    else
        say "✅ Все targets UP"
    fi
else
    say "⚠️ Не удалось получить targets Prometheus"
fi

# ==== 3. Алерты ====
ALERTS=$(curl -sf "$ALERTMANAGER/api/v2/alerts" 2>/dev/null | \
    python -c "import sys,json; d=json.load(sys.stdin); [print(f\"{a['labels'].get('alertname','?'):24} {a.get('status',{}).get('state','?'):10} {a['labels'].get('severity','?'):8} {a['annotations'].get('summary','')}\") for a in d]" 2>/dev/null)

if [ -n "$ALERTS" ]; then
    say "----- Активные алерты Alertmanager -----"
    say "$ALERTS"
    FIRING=$(echo "$ALERTS" | awk '$2 == "firing" {print}')
    if [ -n "$FIRING" ]; then
        [ -n "$QUIET" ] && echo "$FIRING" | while read -r l; do echo "alert firing: $l"; done
    fi
else
    say "✅ Активных алертов нет"
fi

say ""
if [ "$FAILED" -eq 0 ]; then
    say "✅ Мониторинг в порядке"
else
    say "❌ Есть проблемы мониторинга"
    exit 1
fi