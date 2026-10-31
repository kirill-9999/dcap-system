#!/bin/bash
# audit-agent-s3/scripts/restart.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/stop.sh"
sleep 2
"$SCRIPT_DIR/start.sh" --daemon "$@"
