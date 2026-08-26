📋 ТЗ: СИСТЕМНАЯ ИНТЕГРАЦИЯ LINUX-АГЕНТА (ДЕНЬ 24)
Файл: prompts/tz/day_24_linux_agent_service.md

🎯 ЦЕЛЬ
Интегрировать Linux-агент аудита в систему как управляемый сервис. Агент должен:

Запускаться автоматически при старте системы (через systemd или crontab)

Работать в фоновом режиме (без консоли)

Иметь управление через стандартные команды (start/stop/restart/status)

Писать логи в systemd journal и/или файл

Автоматически перезапускаться при сбоях

Важно: Учитывая возможные проблемы с systemd в WSL, предусмотреть два режима установки:

Режим A: systemd-сервис (для полноценных Linux-серверов)

Режим B: crontab + screen/tmux (для WSL и сред без systemd)

📁 ФАЙЛЫ ДЛЯ СОЗДАНИЯ/ИЗМЕНЕНИЯ
Создать/изменить в audit-agent-linux/:
text
audit-agent-linux/
├── service/
│   ├── dcap-audit-agent.service        # systemd unit-файл
│   ├── install.sh                      # Установка сервиса (systemd)
│   ├── uninstall.sh                    # Удаление сервиса
│   ├── install_cron.sh                 # Установка через crontab (WSL)
│   └── uninstall_cron.sh               # Удаление из crontab
├── start.sh                            # ✅ обновить (поддержка флага --daemon)
├── stop.sh                             # ✅ обновить
├── status.sh                           # 🆕 Проверка статуса
└── README.md                           # ✅ обновить
📋 ДЕТАЛЬНОЕ ТЗ
1. systemd-сервис (Режим A)
Создать service/dcap-audit-agent.service:

ini
[Unit]
Description=DCAP Audit Agent (Linux)
After=network.target
Wants=network.target

[Service]
Type=simple
User=kirill
WorkingDirectory=/home/kirill/dcap-system/audit-agent-linux
Environment="PYTHONUNBUFFERED=1"
Environment="MANAGER_URL=http://localhost:8000"
ExecStart=/usr/bin/python3 /home/kirill/dcap-system/audit-agent-linux/main.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=dcap-audit-agent

[Install]
WantedBy=multi-user.target
Важно: пути должны быть абсолютными.

2. Скрипт установки systemd-сервиса (service/install.sh)
bash
#!/bin/bash
# Установка systemd-сервиса для Linux-агента аудита

set -e

SERVICE_NAME="dcap-audit-agent"
SERVICE_FILE="dcap-audit-agent.service"
INSTALL_DIR="/etc/systemd/system"

echo "📦 Установка $SERVICE_NAME..."

# Проверка systemd
if ! command -v systemctl &> /dev/null; then
    echo "❌ systemd не найден. Используйте install_cron.sh для WSL."
    exit 1
fi

# Копирование unit-файла
sudo cp "$SERVICE_FILE" "$INSTALL_DIR/"
sudo chmod 644 "$INSTALL_DIR/$SERVICE_FILE"

# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable "$SERVICE_NAME"

echo "✅ Сервис установлен."
echo ""
echo "Управление:"
echo "  sudo systemctl start $SERVICE_NAME"
echo "  sudo systemctl stop $SERVICE_NAME"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
3. Скрипт удаления systemd-сервиса (service/uninstall.sh)
bash
#!/bin/bash
# Удаление systemd-сервиса

SERVICE_NAME="dcap-audit-agent"
INSTALL_DIR="/etc/systemd/system"

echo "🗑️ Удаление $SERVICE_NAME..."

sudo systemctl stop "$SERVICE_NAME" 2>/dev/null
sudo systemctl disable "$SERVICE_NAME" 2>/dev/null
sudo rm -f "$INSTALL_DIR/$SERVICE_NAME.service"
sudo systemctl daemon-reload

echo "✅ Сервис удален."
4. Установка через crontab (Режим B — для WSL)
Создать service/install_cron.sh:

bash
#!/bin/bash
# Установка агента через crontab (для WSL и сред без systemd)

set -e

AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$AGENT_DIR/start.sh"

echo "📦 Установка агента в crontab (WSL режим)..."

# Добавить в crontab
(crontab -l 2>/dev/null || echo "") | grep -v "$SCRIPT" | { cat; echo "@reboot $SCRIPT > /dev/null 2>&1 &"; } | crontab -

echo "✅ Агент добавлен в crontab (запуск при старте системы)"
echo ""
echo "Проверить: crontab -l"
echo "Остановить: pkill -f 'audit-agent-linux/main.py'"
echo "Удалить из crontab: ./uninstall_cron.sh"
5. Скрипт удаления из crontab (service/uninstall_cron.sh)
bash
#!/bin/bash
# Удаление агента из crontab

AGENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$AGENT_DIR/start.sh"

echo "🗑️ Удаление агента из crontab..."

(crontab -l 2>/dev/null || echo "") | grep -v "$SCRIPT" | crontab -

echo "✅ Агент удален из crontab"
6. Обновленный start.sh
bash
#!/bin/bash
# Запуск Linux-агента аудита
# Использование:
#   ./start.sh          # обычный запуск
#   ./start.sh --daemon # запуск в фоне (nohup)

set -e

cd "$(dirname "$0")"

# Создание venv (если нет)
if [ ! -d "venv" ]; then
    echo "🔧 Создание виртуального окружения..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Проверка наличия config.json
if [ ! -f "config.json" ]; then
    echo "❌ config.json не найден"
    exit 1
fi

# Запуск
if [ "$1" = "--daemon" ] || [ "$1" = "-d" ]; then
    echo "🚀 Запуск в фоновом режиме..."
    nohup python3 main.py >> logs/agent.out 2>&1 &
    echo $! > agent.pid
    echo "✅ Агент запущен, PID: $(cat agent.pid)"
else
    echo "🚀 Запуск в консольном режиме..."
    python3 main.py
fi
7. Обновленный stop.sh
bash
#!/bin/bash
# Остановка Linux-агента аудита

cd "$(dirname "$0")"

if [ -f "agent.pid" ]; then
    PID=$(cat agent.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "✅ Агент остановлен (PID: $PID)"
        rm -f agent.pid
    else
        echo "⚠️ Процесс не найден (PID: $PID)"
        rm -f agent.pid
    fi
else
    # Поиск по имени процесса
    PIDS=$(pgrep -f "audit-agent-linux/main.py" 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "⚠️ Найдены процессы: $PIDS"
        pkill -f "audit-agent-linux/main.py" 2>/dev/null
        echo "✅ Остановлены"
    else
        echo "❌ Агент не запущен"
    fi
fi
8. Скрипт проверки статуса (status.sh)
bash
#!/bin/bash
# Проверка статуса Linux-агента аудита

cd "$(dirname "$0")"

if [ -f "agent.pid" ]; then
    PID=$(cat agent.pid)
    if kill -0 $PID 2>/dev/null; then
        echo "✅ Агент запущен (PID: $PID)"
        echo "📊 Буфер:"
        sqlite3 buffer/buffer.db "SELECT COUNT(*) as unsent FROM events WHERE sent=0;" 2>/dev/null || echo "   buffer.db не найден"
        exit 0
    else
        echo "❌ Агент не запущен (PID-файл устарел)"
        rm -f agent.pid
        exit 1
    fi
else
    PIDS=$(pgrep -f "audit-agent-linux/main.py" 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "⚠️ Агент запущен без PID-файла (PID: $PIDS)"
    else
        echo "❌ Агент не запущен"
        exit 1
    fi
fi
9. Обновленный README.md
markdown
# Linux-агент аудита DCAP

## Установка

```bash
cd ~/dcap-system/audit-agent-linux
cp config.example.json config.json
# Отредактировать config.json
Запуск
Консольный режим (отладка)
bash
./start.sh
Фоновый режим (продакшн)
bash
./start.sh --daemon
Установка как сервис
Для systemd (полноценный Linux)
bash
cd service
./install.sh
sudo systemctl start dcap-audit-agent
Для WSL (без systemd)
bash
cd service
./install_cron.sh
Управление
Команда	Действие
./start.sh	Запуск (консоль)
./start.sh --daemon	Запуск (фон)
./stop.sh	Остановка
./status.sh	Проверка статуса
sudo systemctl start dcap-audit-agent	Запуск сервиса (systemd)
sudo systemctl stop dcap-audit-agent	Остановка сервиса
sudo journalctl -u dcap-audit-agent -f	Логи (systemd)
Логи
Файл: logs/agent.out

systemd: sudo journalctl -u dcap-audit-agent -f

Cron: tail -f logs/agent.out

text

---

## ✅ КРИТЕРИИ ПРИЕМКИ

- [ ] systemd unit-файл создан
- [ ] Установка/удаление systemd-сервиса работает
- [ ] Crontab-установка работает (WSL-режим)
- [ ] `start.sh --daemon` запускает агент в фоне
- [ ] `stop.sh` корректно останавливает агент
- [ ] `status.sh` показывает статус
- [ ] README обновлен

---

## 🧪 ТЕСТОВЫЙ СЦЕНАРИЙ

```bash
# 1. systemd-режим (если есть systemd)
cd ~/dcap-system/audit-agent-linux/service
./install.sh
sudo systemctl start dcap-audit-agent
sudo systemctl status dcap-audit-agent
sudo journalctl -u dcap-audit-agent -f

# 2. WSL-режим (crontab)
cd ~/dcap-system/audit-agent-linux/service
./install_cron.sh
crontab -l
# Проверить, что агент запускается при старте
💾 КОМАНДА ДЛЯ КОММИТА
bash
git add audit-agent-linux/service/ audit-agent-linux/start.sh audit-agent-linux/stop.sh audit-agent-linux/status.sh audit-agent-linux/README.md
git commit -m "feat: День 24 — системная интеграция Linux-агента (systemd + crontab)"
Разработчик (кодер), приступай! 🚀