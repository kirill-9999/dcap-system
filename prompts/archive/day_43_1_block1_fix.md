ТЗ на доработку — финальные баги Блока 1 (v3.13.4)
Приоритет: 🟡 важный (не блокирует Блок 2, но нужно закрыть)
Оценка: ~1-2 часа
Ветка: fix/block_1_issues (или текущая feature/day_40.4_fragments_export)
Предыдущая версия: v3.13.3
Целевая версия: v3.13.4

📋 Сводка багов для фикса
ID	Баг	Серьёзность	Файл
BUG-017.1	healthcheck postgres_exporter = celery-команда	🟡	docker-compose.yml:314-319
BUG-017.2	нет healthcheck у redis_exporter / celery_exporter	🟢	docker-compose.yml
W-43.1	STATE_TEST_SESSION.md в коммите (случайно)	🟢	.gitignore
DOC-001	отчёт говорит «42 файла», реально 40	🟢	day_43_block1_fix_report.md
Из них критичных нет. Все — гигиена и мониторинг.

🔴 BUG-017.1 — healthcheck postgres_exporter
Проблема
В docker-compose.yml:314-319:

yaml
postgres_exporter:
  image: prometheuscommunity/postgres-exporter:latest
  container_name: dcap-postgres-exporter
  # ... existing ...
  healthcheck:
    test: ["CMD-SHELL", "celery -A manager.src.workers.celery_app:app inspect ping --timeout=10 || exit 1"]   ← ❌
    interval: 30s
    timeout: 10s
    start_period: 15s
    retries: 3
Healthcheck выполняет celery-команду в контейнере postgres_exporter, где нет celery/manager/broker. Healthcheck всегда fails → контейнер (unhealthy), хотя экспортер работает.

Источник бага: копипаст из celery_worker (строки 117-121).

Фикс
Вариант A (рекомендую) — убрать healthcheck полностью:

yaml
postgres_exporter:
  image: prometheuscommunity/postgres-exporter:latest
  container_name: dcap-postgres-exporter
  environment:
    DATA_SOURCE_NAME: "postgresql://..."
  ports:
    - "${PG_EXPORTER_PORT:-9187}:9187"
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  networks:
    - dcap-network
  # healthcheck: ← УДАЛИТЬ ВЕСЬ БЛОК
  <<: *default-restart
  logging: *default-logging
Обоснование: образ prometheuscommunity/postgres-exporter — на scratch/distroless, нет wget/curl/sh. Любой healthcheck упадёт.

Вариант B — healthcheck через бинарник экспортера:

yaml
healthcheck:
  test: ["CMD", "/bin/postgres_exporter", "--version"]
  interval: 30s
  timeout: 10s
  start_period: 15s
  retries: 3
⚠️ Проверить путь бинарника:

powershell
docker exec dcap-postgres-exporter which postgres_exporter
Рекомендую A — просто и надёжно.

Проверка
powershell
docker compose up -d postgres_exporter
docker compose ps postgres_exporter
# Ожидаем: Up (без unhealthy)
🟢 BUG-017.2 — нет healthcheck у redis_exporter / celery_exporter
Проблема
redis_exporter и celery_exporter — без healthcheck:

text
dcap-celery-exporter     Up 27 minutes                ← нет статуса
dcap-redis-exporter      Up 27 minutes                ← нет статуса
Это не баг, но для консистентности — можно добавить healthcheck.

Фикс (опционально)
redis_exporter — healthcheck через /metrics:

yaml
redis_exporter:
  # ...
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:9121/metrics >/dev/null 2>&1 || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 3
celery_exporter — healthcheck через /metrics:

yaml
celery_exporter:
  # ...
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:9808/metrics >/dev/null 2>&1 || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 3
⚠️ Проверить, есть ли wget в образах:

powershell
docker exec dcap-redis-exporter which wget
docker exec dcap-celery-exporter which wget
Если нет — оставить без healthcheck (как сейчас). Это не баг.

Рекомендую: не трогать — если работает, не чинить. Зафиксировать как «known: без healthcheck».

🟢 W-43.1 — STATE_TEST_SESSION.md в коммите
Проблема
STATE_TEST_SESSION.md (208 строк) попал в коммит 80c3728 — вероятно, git add -A. Это рабочий документ сессии, не часть релиза.

Фикс
Добавить в .gitignore:

gitignore
# Session/testing docs (не коммитить)
STATE_TEST_SESSION*.md
prompts/reports/*.md
prompts/archive/*.md
Удалить из индекса (не с диска):

powershell
git rm --cached STATE_TEST_SESSION.md
git commit -m "chore: STATE_TEST_SESSION.md — untrack (session doc)"
⚠️ Осторожно: если файл уже в истории (80c3728), git rm --cached уберёт только из текущего коммита. Из истории — нужно git filter-repo (не рекомендую).

Рекомендую:

.gitignore — добавить.

git rm --cached — сделать.

Не переписывать историю — не критично.

🟢 DOC-001 — отчёт говорит «42 файла», реально 40
Проблема
В отчёте day_43_block1_fix_report.md, секция 7:

результат: 80c3728 на ветке feature/day_40.4_fragments_export (42 файла, +1624/-343)

Реально — 40 файлов (см. git show --stat 80c3728).

Фикс
Обновить отчёт:

diff
- результат: 80c3728 на ветке feature/day_40.4_fragments_export (42 файла, +1624/-343)
+ результат: 80c3728 на ветке feature/day_40.4_fragments_export (40 файлов, +1624/-343)
Или точную цифру посчитать:

powershell
git show --stat 80c3728 | Select-String "\|" | Measure-Object -Line
📋 Порядок работы
Шаг 1 — BUG-017.1 (5 мин)
Открыть docker-compose.yml, строки 314-319.

Удалить блок healthcheck: для postgres_exporter.

docker compose up -d postgres_exporter.

docker compose ps postgres_exporter → Up (без unhealthy).

Шаг 2 — W-43.1 (2 мин)
Добавить STATE_TEST_SESSION*.md в .gitignore.

git rm --cached STATE_TEST_SESSION.md.

Шаг 3 — DOC-001 (2 мин)
Посчитать точное число файлов в 80c3728.

Обновить отчёт.

Шаг 4 (опционально) — BUG-017.2 (5 мин)
Проверить wget в redis_exporter/celery_exporter.

Если есть — добавить healthcheck.

Если нет — оставить как есть, зафиксировать в отчёте.

Шаг 5 — Коммит
powershell
git add docker-compose.yml .gitignore STATE_TEST_SESSION.md prompts/reports/day_43_block1_fix_report.md
git commit -m "fix: Блок 1 (v3.13.4) — BUG-017.1 (postgres_exporter healthcheck), гигиена

Docker:
- BUG-017.1: убран celery-healthcheck у postgres_exporter (копипаст из celery_worker),
  контейнер теперь Up без unhealthy

Гигиена:
- W-43.1: STATE_TEST_SESSION.md — untrack (session doc, .gitignore)
- DOC-001: отчёт — точное число файлов (40, не 42)"
git log --oneline -1
Шаг 6 — Верификация
powershell
# BUG-017.1
docker compose ps postgres_exporter
# Ожидаем: Up (без unhealthy)

# W-43.1
git status --short
# Ожидаем: пусто (или только untracked)

# DOC-001
Select-String -Path prompts\reports\day_43_block1_fix_report.md -Pattern "файл"
✅ Критерии приёмки
#	Критерий	Проверка
1	postgres_exporter — Up без (unhealthy)	docker compose ps postgres_exporter
2	redis_exporter — Up (без unhealthy)	docker compose ps redis_exporter
3	celery_exporter — Up (без unhealthy)	docker compose ps celery_exporter
4	STATE_TEST_SESSION.md — в .gitignore, не в индексе	git status --short
5	Отчёт — точное число файлов	git show --stat 80c3728 | Measure-Object
6	Коммит v3.13.4 создан	git log --oneline -1
📎 Ссылки
docker-compose.yml:314-319 — healthcheck postgres_exporter

docker-compose.yml:117-121 — healthcheck celery_worker (откуда копипаст)

day_43_block1_fix_report.md — отчёт v3.13.3

STATE_TEST_SESSION.md — документ сессии

🚫 Что НЕ делать
❌ Не переписывать историю (filter-repo, rebase -i) — STATE_TEST_SESSION.md в 80c3728 не критично.

❌ Не трогать redis_exporter/celery_exporter, если wget нет — «не чинить работающее».

❌ Не добавлять healthcheck postgres_exporter через wget — образа нет wget.

📝 Отчёт после фикса
Файл: prompts/reports/day_43_1_block1_fix_report.md

Структура:

BUG-017.1 — что сделано, проверка

W-43.1 — .gitignore, git rm --cached

DOC-001 — точное число файлов

BUG-017.2 — статус (сделано / отложено, почему)

Критерии приёмки — все ✅

Коммит — хеш, сообщение