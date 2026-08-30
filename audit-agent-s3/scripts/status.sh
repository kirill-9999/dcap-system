#!/bin/bash
# audit-agent-s3/scripts/status.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPONENT_NAME="s3-agent"

PID_FILE="$PROJECT_ROOT/data/$COMPONENT_NAME.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "$COMPONENT_NAME is running (PID: $PID)"
        exit 0
    else
        echo "$COMPONENT_NAME is not running (stale PID file)"
        exit 1
    fi
else
    echo "$COMPONENT_NAME is not running"
    exit 1
fi
