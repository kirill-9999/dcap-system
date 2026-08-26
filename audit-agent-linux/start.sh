#!/bin/bash
# Запуск Linux-агента аудита
# Использование:
#   ./start.sh          # обычный запуск
#   ./start.sh --daemon # запуск в фоне (nohup)

set -e

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

if [ ! -f "config.json" ]; then
    echo "config.json не найден"
    exit 1
fi

mkdir -p logs buffer

if [ "$1" = "--daemon" ] || [ "$1" = "-d" ]; then
    echo "Запуск в фоновом режиме..."
    nohup python main.py >> logs/agent.out 2>&1 &
    echo $! > agent.pid
    echo "Агент запущен, PID: $(cat agent.pid)"
else
    echo "Запуск в консольном режиме..."
    python main.py
fi
