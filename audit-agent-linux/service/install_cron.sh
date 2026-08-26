#!/bin/bash
# Установка агента через crontab (для WSL и сред без systemd)

set -e

AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$AGENT_DIR/start.sh"

echo "Установка агента в crontab (WSL режим)..."

(crontab -l 2>/dev/null || echo "") | grep -v "$SCRIPT" | { cat; echo "@reboot $SCRIPT > /dev/null 2>&1 &"; } | crontab -

echo "Агент добавлен в crontab (запуск при старте системы)"
echo ""
echo "Проверить: crontab -l"
echo "Остановить: pkill -f 'audit-agent-linux/main.py'"
echo "Удалить из crontab: ./uninstall_cron.sh"
