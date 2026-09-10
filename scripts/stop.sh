#!/bin/bash
# scripts/stop.sh
# Остановка DCAP (День 38).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

REMOVE_VOLUMES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --volumes|-v) REMOVE_VOLUMES=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "🛑 Stopping DCAP services..."

if [ "$REMOVE_VOLUMES" = true ]; then
    echo "⚠️  Removing volumes..."
    docker compose down -v
else
    docker compose down
fi

echo "✅ DCAP stopped"