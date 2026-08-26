#!/bin/bash
cd "$(dirname "$0")"
mkdir -p logs buffer

if [ ! -d "venv" ]; then
    echo "Создание venv..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

nohup python main.py >> logs/agent.out 2>&1 &
echo $! > agent.pid
echo "Агент запущен, PID: $(cat agent.pid)"
