#!/bin/bash
# Установка systemd-сервиса для Linux-агента аудита

set -e

SERVICE_NAME="dcap-audit-agent"
SERVICE_FILE="dcap-audit-agent.service"
INSTALL_DIR="/etc/systemd/system"

echo "Установка $SERVICE_NAME..."

if ! command -v systemctl &> /dev/null; then
    echo "systemd не найден. Используйте install_cron.sh для WSL."
    exit 1
fi

sudo cp "$SERVICE_FILE" "$INSTALL_DIR/"
sudo chmod 644 "$INSTALL_DIR/$SERVICE_FILE"

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo "Сервис установлен."
echo ""
echo "Управление:"
echo "  sudo systemctl start $SERVICE_NAME"
echo "  sudo systemctl stop $SERVICE_NAME"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
