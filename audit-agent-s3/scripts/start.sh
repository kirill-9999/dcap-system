#!/bin/bash
# audit-agent-s3/scripts/start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPONENT_NAME="s3-agent"

cd "$PROJECT_ROOT"

DAEMON=false
CONFIG_FILE="config/config.json"

while [[ $# -gt 0 ]]; do
    case $1 in
        --daemon|-d) DAEMON=true; shift ;;
        --config|-c) CONFIG_FILE="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [--daemon] [--config CONFIG_FILE]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Создание директорий
mkdir -p data/state data/buffer logs

if [ "$DAEMON" = true ]; then
    echo "Starting $COMPONENT_NAME as daemon..."
    nohup python -m src.main --config "$CONFIG_FILE" >> logs/s3_agent.log 2>&1 &
    echo $! > data/s3_agent.pid
    echo "$COMPONENT_NAME started (PID: $!)"
else
    echo "Starting $COMPONENT_NAME in console mode..."
    python -m src.main --config "$CONFIG_FILE"
fi
