#!/bin/bash
# scripts/run-tests.sh
# Запуск тестов по режимам (stand / E2E / Chaos / Load / All / Quick).
# Требования: pytest + requirements-dev.txt, для e2e/chaos/load — запущенный стек.
#
# День 53.3-test-stand-fix: стенд поднимает сам скрипт (TEST-NOTE-10.6/10.7):
#   - `stand`  — чистая БД (down -v) + up -d --wait (ждём healthcheck Manager);
#   - `all`    — то же, затем e2e + load + chaos;
#   - `e2e`/`quick`/`load`/`chaos` — стенд не трогают (итеративная отладка).
set -e

MODE=${1:-all}
COMPOSE_FILE="docker-compose.test.yml"
MANAGER_HEALTH="http://localhost:18000/api/health"
WEBUI_HEALTH="http://localhost:18001/health"

# TEST-NOTE-10.7 (53.3-test-stand-fix): чистим персистентный том
# postgres_test_data перед прогоном. Иначе копятся pending-задачи и «мёртвые»
# сканеры: сканер разбирает очередь FIFO, свежая задача ждёт >240 с и падает
# по таймауту. --remove-orphans сносит контейнеры, оставшиеся от экспериментов.
stand_down() {
  echo "[stand] docker compose -f $COMPOSE_FILE down -v --remove-orphans"
  docker compose -f "$COMPOSE_FILE" down -v --remove-orphans || true
}

# TEST-NOTE-10.6 (53.3-test-stand-fix): ждём healthcheck, а не sleep.
# Основной путь — `up -d --wait` (Compose v2.1+): возвращается, когда все
# сервисы healthy, т.е. Alembic-миграции Manager уже прошли. Если Compose
# не знает флаг --wait — fallback: up -d + polling по /api/health.
stand_up() {
  local build_flag=""
  if [ "${2:-}" = "--build" ]; then
    build_flag="--build"
  fi

  echo "[stand] docker compose -f $COMPOSE_FILE up -d $build_flag --wait"
  local out rc
  set +e
  out=$(docker compose -f "$COMPOSE_FILE" up -d $build_flag --wait 2>&1)
  rc=$?
  set -e
  if [ $rc -eq 0 ]; then
    echo "$out"
    echo "[stand] стенд healthy"
    return 0
  fi
  if echo "$out" | grep -qiE "unknown (flag|option|short flag)"; then
    echo "[stand] Compose не поддерживает --wait — fallback: up -d + polling"
    docker compose -f "$COMPOSE_FILE" up -d $build_flag
    local i
    for i in $(seq 1 60); do
      if curl -sf "$MANAGER_HEALTH" > /dev/null 2>&1 \
         && curl -sf "$WEBUI_HEALTH" > /dev/null 2>&1; then
        echo "[stand] стенд healthy (polling)"
        return 0
      fi
      sleep 2
    done
    echo "[stand] ОШИБКА: стенд не стал healthy за 120 с"
    return 1
  fi
  echo "$out"
  echo "[stand] ОШИБКА: стенд не поднялся (см. вывод выше)"
  return 1
}

stand_full() {
  stand_down
  stand_up "" "${1:-}"
}

case $MODE in
  stand)
    # Только стенд: чистая БД + healthcheck. ./scripts/run-tests.sh stand --build
    stand_full "${2:-}"
    ;;
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
    # Стенд с чистой БД (TEST-NOTE-10.7), затем тесты.
    # Chaos идёт ПОСЛЕДНИМ: он разрушительный (останавливает контейнеры),
    # а load/e2e должны работать на стабильном стеке.
    stand_full
    pytest tests/e2e/ tests/load/ -v --timeout=600
    pytest tests/chaos/ -v --timeout=600
    ;;
  quick)
    pytest tests/e2e/ -v --timeout=120 -m "e2e and not slow"
    ;;
  *)
    echo "Usage: $0 [stand [--build]|e2e|chaos|load|all|quick]"
    exit 1
    ;;
esac
