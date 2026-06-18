#!/bin/bash
# wait-for-postgres.sh - ожидание PostgreSQL без netcat
# Использует wget или прямое psql подключение

set -e

HOST="$1"
PORT="$2"
shift 2

TIMEOUT=30
WAIT_LOOP=0

echo "Waiting for PostgreSQL at $HOST:$PORT..."

while ! pg_isready -h "$HOST" -p "$PORT" -U dcap > /dev/null 2>&1; do
    WAIT_LOOP=$((WAIT_LOOP + 1))
    if [ $WAIT_LOOP -ge $TIMEOUT ]; then
        echo "Timeout waiting for PostgreSQL"
        exit 1
    fi
    echo "PostgreSQL not ready yet... (${WAIT_LOOP}/${TIMEOUT})"
    sleep 1
done

echo "PostgreSQL is ready!"
exec "$@"