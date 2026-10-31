#!/bin/bash
# Удаление systemd-сервиса

SERVICE_NAME="dcap-audit-agent"
INSTALL_DIR="/etc/systemd/system"

echo "Удаление $SERVICE_NAME..."

sudo systemctl stop "$SERVICE_NAME" 2>/dev/null
sudo systemctl disable "$SERVICE_NAME" 2>/dev/null
sudo rm -f "$INSTALL_DIR/$SERVICE_NAME.service"
sudo systemctl daemon-reload

echo "Сервис удален."
