#!/bin/bash
# scripts/run-tests.sh
# Запуск тестов по режимам (E2E / Chaos / Load / All / Quick).
# Требования: pytest + requirements-dev.txt, для e2e/chaos/load — запущенный стек.
set -e

MODE=${1:-all}

case $MODE in
  e2e)
    pytest tests/e2e/ -v --timeout=300
    ;;
  chaos)
    pytest tests/chaos/ -v --timeout=600 -m chaos
    ;;
  load)
    pytest tests/load/ -v --timeout=300 -m load
    ;;
  all)
    # Chaos идёт ПОСЛЕДНИМ: он разрушительный (останавливает контейнеры),
    # а load/e2e должны работать на стабильном стеке.
    pytest tests/e2e/ tests/load/ -v --timeout=600
    pytest tests/chaos/ -v --timeout=600
    ;;
  quick)
    pytest tests/e2e/ -v --timeout=120 -m "e2e and not slow"
    ;;
  *)
    echo "Usage: $0 [e2e|chaos|load|all|quick]"
    exit 1
    ;;
esac