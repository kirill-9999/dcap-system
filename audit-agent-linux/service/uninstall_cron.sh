#!/bin/bash
# Удаление агента из crontab

AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$AGENT_DIR/start.sh"

echo "Удаление агента из crontab..."

(crontab -l 2>/dev/null || echo "") | grep -v "$SCRIPT" | crontab -

echo "Агент удален из crontab"
