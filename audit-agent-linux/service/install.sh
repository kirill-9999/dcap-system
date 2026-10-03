#!/bin/bash
# Установка systemd-сервиса для Linux-агента аудита

set -e

SERVICE_NAME="dcap-audit-agent"
SERVICE_FILE="dcap-audit-agent.service"
INSTALL_DIR="/etc/systemd/system"

# Каталог агента — родительский для каталога со скриптом (service/ -> корень агента)
AGENT_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_HOME="$(cd "$AGENT_HOME" && pwd -P)"
DCAP_USER="${SUDO_USER:-$(id -un)}"

# Интерпретатор: venv агента при наличии, иначе системный python3
if [ -x "$AGENT_HOME/venv/bin/python" ]; then
    DCAP_PYTHON="$AGENT_HOME/venv/bin/python"
else
    DCAP_PYTHON="$(command -v python3)"
fi

if [ ! -f "$AGENT_HOME/config.json" ]; then
    echo "Ошибка: не найден $AGENT_HOME/config.json (конфиг обязателен)."
    exit 1
fi

echo "Установка $SERVICE_NAME..."
echo "  пользователь: $DCAP_USER"
echo "  каталог:      $AGENT_HOME"
echo "  python:       $DCAP_PYTHON"

if ! command -v systemctl &> /dev/null; then
    echo "systemd не найден. Используйте install_cron.sh для WSL."
    exit 1
fi

# Подстановка плейсхолдеров в юнит перед установкой
TMP_UNIT="$(mktemp)"
sed -e "s|__DCAP_USER__|$DCAP_USER|g" \
    -e "s|__DCAP_HOME__|$AGENT_HOME|g" \
    -e "s|__DCAP_PYTHON__|$DCAP_PYTHON|g" \
    "$AGENT_HOME/service/$SERVICE_FILE" > "$TMP_UNIT"

sudo cp "$TMP_UNIT" "$INSTALL_DIR/$SERVICE_NAME.service"
sudo chmod 644 "$INSTALL_DIR/$SERVICE_NAME.service"
rm -f "$TMP_UNIT"

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

echo "Сервис установлен."
echo ""
echo "Управление:"
echo "  sudo systemctl start $SERVICE_NAME"
echo "  sudo systemctl stop $SERVICE_NAME"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
