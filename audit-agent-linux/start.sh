#!/bin/bash
cd "$(dirname "$0")"
mkdir -p logs buffer
nohup python3 main.py >> logs/agent.out 2>&1 &
echo $! > agent.pid
echo "Агент запущен, PID: $(cat agent.pid)"
