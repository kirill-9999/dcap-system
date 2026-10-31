#!/bin/bash
# scripts/logs.sh
# Логи DCAP (День 38).
# Использование:
#   ./scripts/logs.sh                 # последние 100 строк всех сервисов
#   ./scripts/logs.sh manager         # последние 100 строк Manager
#   ./scripts/logs.sh manager -f      # следить за логами Manager
#   ./scripts/logs.sh -n 500 -f       # 500 строк, follow

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

SERVICE=""
TAIL=100
FOLLOW=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow) FOLLOW=true; shift ;;
        -n|--tail) TAIL="$2"; shift 2 ;;
        *) SERVICE="$1"; shift ;;
    esac
done

CMD="docker compose logs --no-color --tail=$TAIL"
if [ "$FOLLOW" = true ]; then
    CMD="$CMD -f"
fi
if [ -n "$SERVICE" ]; then
    CMD="$CMD $SERVICE"
fi

$CMD