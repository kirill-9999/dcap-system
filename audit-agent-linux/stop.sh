#!/bin/bash
# Остановка Linux-агента аудита

cd "$(dirname "$0")"

if [ -f "agent.pid" ]; then
    PID=$(cat agent.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "Агент остановлен (PID: $PID)"
        rm -f agent.pid
    else
        echo "Процесс не найден (PID: $PID, устарел)"
        rm -f agent.pid
    fi
else
    PIDS=$(pgrep -f "audit-agent-linux/main.py" 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "Найдены процессы: $PIDS"
        pkill -f "audit-agent-linux/main.py" 2>/dev/null
        echo "Остановлены"
    else
        echo "Агент не запущен"
    fi
fi
