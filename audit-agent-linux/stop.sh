#!/bin/bash
if [ -f agent.pid ]; then
    kill $(cat agent.pid) 2>/dev/null && echo "Агент остановлен"
    rm -f agent.pid
else
    echo "PID-файл не найден"
fi
