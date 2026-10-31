#!/bin/bash
# audit-agent-s3/scripts/stop.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPONENT_NAME="s3-agent"

PID_FILE="$PROJECT_ROOT/data/$COMPONENT_NAME.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "$COMPONENT_NAME is not running (no PID file)"
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping $COMPONENT_NAME (PID: $PID)..."
    kill "$PID"
    sleep 2
    if kill -0 "$PID" 2>/dev/null; then
        echo "Force killing..."
        kill -9 "$PID"
    fi
    rm -f "$PID_FILE"
    echo "$COMPONENT_NAME stopped"
else
    echo "$COMPONENT_NAME is not running (stale PID file)"
    rm -f "$PID_FILE"
fi
