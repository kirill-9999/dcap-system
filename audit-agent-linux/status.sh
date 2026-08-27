#!/bin/bash
# Проверка статуса Linux-агента аудита

cd "$(dirname "$0")"

if [ -f "agent.pid" ]; then
    PID=$(cat agent.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "Агент запущен (PID: $PID)"
        if [ -f "data/buffer/buffer.db" ]; then
            UNSENT=$(sqlite3 data/buffer/buffer.db "SELECT COUNT(*) FROM events WHERE sent=0;" 2>/dev/null || echo "?")
            echo "Буфер: $UNSENT неотправленных событий"
        fi
        exit 0
    else
        echo "Агент не запущен (PID-файл устарел)"
        rm -f agent.pid
        exit 1
    fi
else
    PIDS=$(pgrep -f "audit-agent-linux/main.py" 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "Агент запущен без PID-файла (PID: $PIDS)"
    else
        echo "Агент не запущен"
        exit 1
    fi
fi
