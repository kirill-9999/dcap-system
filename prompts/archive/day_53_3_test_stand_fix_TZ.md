ТЗ: День 53.3-test-stand-fix — стенд E2E: healthcheck + автоочистка + версии образов
Файл: prompts/tz/day_53_3_test_stand_fix.md
Дата: 04.10.2026
Версия: v3.13.33 → v3.13.34
Статус: ✏️ Готово к разработке
Оценка: ~30–40 мин
Приоритет: 🟡 важно (подготовка стенда перед 53.3-fs-regress; без него ручной прогон будет спотыкаться)
Родительская задача: BACKLOG-097 (follow-up) + TEST-NOTE-10.6/10.7

🎯 ЦЕЛЬ

1. Починить стенд `docker-compose.test.yml`: устранить гонку, из-за которой `manager_test` отвечает 500 после `up -d` (пока не завершатся Alembic-миграции) — **TEST-NOTE-10.6**.
2. Автоматизировать очистку `postgres_test_data` перед прогоном E2E — **TEST-NOTE-10.7**.
3. Поднять версии docker-образов агентов до актуальной (`dcap/s3-agent` и `dcap/linux-agent` отстали — `3.13.16` против `3.13.33` у Manager/WebUI).

Что НЕ входит в 53.3-test-stand-fix:
- Ручной FS-регресс — 53.3-fs-regress (следующий день).
- WebUI-редизайн — 53.4a–53.4e.
- Правки кода сканера/Manager (только compose + скрипт).
- TEST-NOTE-10.8 (2 legacy-теста WebUI требуют непустую таблицу findings) — отдельная задача, не в этом ТЗ.

📌 ПРОБЛЕМА

**TEST-NOTE-10.6.** После `docker compose -f docker-compose.test.yml up -d` Manager (`:18000`)
отвечает 500, пока не завершатся Alembic-миграции в PostgreSQL. В compose уже есть
`depends_on: postgres_test: service_healthy`, но healthcheck для Postgres проверяет
только готовность принять соединение — не факт, что `init_db`/`alembic upgrade head`
в `manager_test` уже прошли. В итоге E2E падают с `RemoteDisconnected`/500 на первых
запросах, и нужен ручной `docker compose restart manager_test`.

**TEST-NOTE-10.7.** Named volume `postgres_test_data` — персистентный, копится между
прогонами. В нём накапливаются `scan_tasks` в статусе `pending`, десятки «мёртвых»
сканеров. Сканер разбирает очередь FIFO — свежая S3-задача ждёт >240 с и падает
по таймауту. Приходится вручную `docker compose down -v` перед прогоном.

**Docker-теги.** В `docker-compose.yml` (или `.prod.yml`):
- `dcap/manager` → `${VERSION:-3.13.29}`,
- `dcap/webui` → `${VERSION:-3.13.29}`,
- `dcap/s3-agent` → `3.13.16`,
- `dcap/linux-agent` → `3.13.16`.

Агенты отстали на 17 версий. На GitHub-пакете будет путаница: «в образе старая версия».

📌 ПРЕДУСЛОВИЯ

- ✅ v3.13.35 закрыта (`53.3-fix-s3-bucket`).
- ✅ `docker-compose.test.yml` существует.
- ✅ `scripts/run-tests.sh` существует.
- ✅ `docker-compose.yml` и `docker-compose.s3.yml` содержат сервисы агентов.
- ✅ Unit-набор — 430 passed.

📁 ФАЙЛЫ (изменяются)

| Файл | Что меняется |
|------|--------------|
| `docker-compose.test.yml` | healthcheck для `manager_test` (или `depends_on` + healthcheck PG) |
| `scripts/run-tests.sh` | `down -v` перед `up` |
| `docker-compose.yml` | Теги `dcap/s3-agent` и `dcap/linux-agent` → `${VERSION:-3.13.34}` |
| `docker-compose.s3.yml` | Тег `dcap/s3-agent` → `${VERSION:-3.13.34}` |
| `docs/testing.md` | Убрать ручной `down -v` и `restart manager_test` из инструкции |
| `ROADMAP.md` | TEST-NOTE-10.6/10.7 закрыты (или переформулированы) |
| `STATE.md`, `CHANGELOG.md` | Версия `v3.13.34` |

Создаются:

| Файл | Назначение |
|------|------------|
| `prompts/reports/day_53_3_test_stand_fix_report.md` | Отчёт |

🔧 ДЕТАЛЬНОЕ ТЗ

TASK-137 — `docker-compose.test.yml`: healthcheck для `manager_test`

Файл: `docker-compose.test.yml`

**Проблема:** `depends_on: postgres_test: condition: service_healthy` гарантирует, что PG принимает соединения. Но `manager_test` при старте сам накатывает миграции (`alembic upgrade head` в entrypoint) и до их завершения отвечает 500 на `/api/health`.

**Решение:** добавить `healthcheck` для `manager_test`, который проверяет `/api/health`. Внешние скрипты/E2E-фикстуры теперь могут ждать готовности через `docker compose ... ps` или через `--wait` (Compose v2.1+).

Найти в `docker-compose.test.yml` сервис `manager_test`. Добавить блок `healthcheck`:

```yaml
  manager_test:
    # ... существующие поля ...
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 5s
      timeout: 5s
      retries: 30
      start_period: 30s
Обоснование параметров:

interval: 5s — часто, потому что ждём миграции ~15–30 с.

start_period: 30s — время на старт uvicorn + alembic.

retries: 30 — суммарно до 30×5 + 30 = 180 с, с запасом.

Если в образе нет curl (slim-вариант) — заменить на wget:

yaml
      test: ["CMD", "wget", "-q", "-O", "-", "http://localhost:8000/api/health"]
⚠️ Проверить перед выбором: docker exec dcap-manager curl --version (или wget --version). Использовать тот, что есть.

Плюс (опционально) — добавить в depends_on сервисов, которые ходят в Manager из стенда, условие service_healthy:

yaml
  # для сервиса, который ждёт Manager (если есть)
  webui_test:
    depends_on:
      manager_test:
        condition: service_healthy
Если таких сервисов нет — не трогать.

TASK-138 — scripts/run-tests.sh: down -v перед up

Файл: scripts/run-tests.sh

Найти блок, который делает docker compose -f docker-compose.test.yml up -d. Добавить перед ним:

bash
# TEST-NOTE-10.7 (53.3-test-stand-fix): чистим персистентный том postgres_test_data
# перед каждым прогоном. Иначе копятся pending-задачи и «мёртвые» сканеры,
# свежая задача ждёт в очереди FIFO и падает по таймауту.
docker compose -f docker-compose.test.yml down -v --remove-orphans || true
Обоснование:

down -v — удаляет volumes (postgres_test_data, любые другие).

--remove-orphans — сносит контейнеры, которых нет в compose (защита от «зависших» после экспериментов).

|| true — не падать, если стенд не был поднят.

Важно: если в скрипте есть отдельная команда для запуска E2E без перезапуска стенда (например, для итеративной отладки) — не ломать её. down -v добавляем только в основной сценарий полного прогона.

Плюс — заменить «ждать 30 с» на «ждать healthcheck» (если был sleep):

bash
# Было:
# docker compose -f docker-compose.test.yml up -d
# sleep 30

# Стало:
docker compose -f docker-compose.test.yml up -d --wait
--wait — Compose v2.1+. Если версия Compose старая — оставить sleep + polling:

bash
docker compose -f docker-compose.test.yml up -d
for i in $(seq 1 60); do
  if curl -sf http://localhost:18000/api/health >/dev/null; then break; fi
  sleep 2
done
Решение оставить за кодером — выбрать тот вариант, что совместим с установленной версией Compose.

TASK-139 — Docker-теги агентов

Файл: docker-compose.yml и docker-compose.s3.yml

Найти:

yaml
  s3_agent:
    image: dcap/s3-agent:3.13.16
Заменить на:

yaml
  s3_agent:
    image: dcap/s3-agent:${VERSION:-3.13.34}
Аналогично для linux_agent (или как называется в compose):

yaml
  linux_agent:
    image: dcap/linux-agent:${VERSION:-3.13.34}
Обоснование: единый тег через ${VERSION:-...} — как у manager/webui. При обновлении .env все образы пересобираются одной версией.

Важно: если образы агентов не собираются в текущем compose (только image: без build:) — проверить, есть ли Dockerfile в audit-agent-s3/ и audit-agent-linux/. Если Dockerfile нет — поменять только тег (при docker compose up он подтянет latest, что тоже не идеально). Если Dockerfile есть — добавить build: рядом с image:, чтобы собиралось локально.

Проверить перед правкой:

ls audit-agent-s3/Dockerfile audit-agent-linux/Dockerfile

grep -n "s3_agent\|linux_agent" docker-compose.yml docker-compose.s3.yml

TASK-140 — docs/testing.md: убрать ручные шаги

Файл: docs/testing.md

Найти инструкцию по E2E-прогону. Удалить:

«Перед прогоном сделать docker compose -f docker-compose.test.yml down -v» — теперь автоматически в run-tests.sh.

«Если manager_test отвечает 500 — docker compose restart manager_test» — теперь healthcheck + --wait.

Добавить в начало раздела E2E:

markdown
**Стенд поднимается автоматически:**

```bash
./scripts/run-tests.sh
Скрипт делает:

docker compose -f docker-compose.test.yml down -v — чистая БД (TEST-NOTE-10.7).

docker compose -f docker-compose.test.yml up -d --wait — ждёт, пока
manager_test пройдёт healthcheck (/api/health → 200, после миграций).

Запускает pytest tests/e2e.

Ручной down -v и restart manager_test больше не нужны.

text

🧪 КРИТЕРИИ ПРИЁМКИ

| # | Критерий | Проверка |
|---|----------|----------|
| 1 | `manager_test` имеет `healthcheck` в `docker-compose.test.yml` | grep |
| 2 | `scripts/run-tests.sh` делает `down -v` перед `up` | grep |
| 3 | `docker compose -f docker-compose.test.yml up -d --wait` возвращается только после 200 на `/api/health` | ручная |
| 4 | Тег `dcap/s3-agent` в `docker-compose.yml` и `docker-compose.s3.yml` — `${VERSION:-3.13.34}` | grep |
| 5 | Тег `dcap/linux-agent` (если есть) — `${VERSION:-3.13.34}` | grep |
| 6 | `docs/testing.md` не содержит «restart manager_test» и ручной «down -v» | grep |
| 7 | TEST-NOTE-10.6/10.7 закрыты в `ROADMAP.md` | grep |
| 8 | Unit-набор зелёный | `pytest tests/unit/ -q` — 430 passed |
| 9 | E2E на чистом стенде проходит без ручных шагов | `./scripts/run-tests.sh` |

🧪 ТЕСТОВЫЙ СЦЕНАРИЙ

**1. Проверка healthcheck (Manager):**
```bash
docker compose -f docker-compose.test.yml down -v --remove-orphans
docker compose -f docker-compose.test.yml up -d --wait
docker compose -f docker-compose.test.yml ps        # все healthy
curl -sf http://localhost:18000/api/health          # {"status":"healthy","version":"3.13.34"}
2. Проверка автоочистки:

bash
./scripts/run-tests.sh
Ожидание: в логе видно down -v в начале, потом up -d --wait, потом pytest.

3. Проверка тегов:

bash
grep -n "dcap/s3-agent\|dcap/linux-agent" docker-compose.yml docker-compose.s3.yml
Ожидание: ${VERSION:-3.13.34}.

4. Unit:

bash
pytest tests/unit/ -q
Ожидание: 430 passed.

📝 СВОДКА ПРАВОК

#	Файл	Действие	Задача
1	docker-compose.test.yml	+ healthcheck для manager_test	TASK-137
2	scripts/run-tests.sh	+ down -v + up -d --wait	TASK-138
3	docker-compose.yml	Теги агентов → ${VERSION:-3.13.34}	TASK-139
4	docker-compose.s3.yml	Тег s3-agent → ${VERSION:-3.13.34}	TASK-139
5	docs/testing.md	Убрать ручные шаги	TASK-140
6	ROADMAP.md, STATE.md, CHANGELOG.md	Версия + закрытие TEST-NOTE	—
⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ

TEST-NOTE-10.8 (2 legacy-теста WebUI требуют непустую findings) — не входит в это ТЗ. Отдельная микро-задача (или в 53.4d, когда будет редизайн WebUI).

--wait требует Compose v2.1+. Если версия старая — использовать polling curl в run-tests.sh.

Проверка наличия curl/wget в образе manager_test — обязательна перед выбором healthcheck. Если нет ни одного — поставить curl в manager/Dockerfile (микро-правка) или использовать python -c "import urllib.request; ...".

📋 ОТКРЫТЫЕ ВОПРОСЫ

Compose v2.1+ — у вас? Если нет — оставляем polling.

curl/wget в образе Manager — есть? Если нет — доустановить в Dockerfile (микро-правка, вне ТЗ; либо использовать Python-однострочник).

⚠️ ЧТО НЕ ДЕЛАЕМ

Не трогаем код Manager/Scanner.

Не переписываем docker-compose.yml целиком (только теги агентов).

Не делаем TEST-NOTE-10.8.

Не меняем docker-compose.prod.yml.

Не переписываем WebUI.

💾 КОМАНДА ДЛЯ КОММИТА

bash
git checkout -b feature/day_53_3_test_stand_fix

git add docker-compose.test.yml \
        docker-compose.yml \
        docker-compose.s3.yml \
        scripts/run-tests.sh \
        docs/testing.md \
        ROADMAP.md STATE.md CHANGELOG.md \
        prompts/reports/day_53_3_test_stand_fix_report.md

git commit -m "chore: День 53.3-test-stand-fix — стенд E2E (healthcheck + автоочистка + версии образов) (v3.13.34)

- docker-compose.test.yml: healthcheck для manager_test (curl/wget /api/health);
  устранён ручной 'restart manager_test' после up -d (TEST-NOTE-10.6)
- scripts/run-tests.sh: down -v --remove-orphans перед up -d;
  up -d --wait (или polling curl) вместо sleep; закрыт TEST-NOTE-10.7
- docker-compose.yml, docker-compose.s3.yml: теги dcap/s3-agent и
  dcap/linux-agent → \${VERSION:-3.13.34} (было 3.13.16 — отстали)
- docs/testing.md: убраны ручные шаги (down -v, restart manager_test)

docs: обновлены STATE.md (v3.13.34), CHANGELOG.md, ROADMAP.md
(TEST-NOTE-10.6, 10.7 — закрыты)"
📊 ОБНОВЛЕНИЕ ПЛАНА

День	Задача	Статус
53.3	E2E + WebUI-форма S3 + docs	✅ v3.13.32
53.3-fix-s3-bucket	Bucket из scan_config	✅ v3.13.35
53.3-test-stand-fix	Стенд E2E: healthcheck + автоочистка + версии	🔄 В РАБОТЕ
53.3-fs-regress	Ручной регресс FS	📋 следующий
53.4a–53.4e	WebUI-редизайн (Dovetail)	📋
📌 ПОСЛЕ ВЫПОЛНЕНИЯ

Обновить STATE.md: версия v3.13.34, следующий шаг — «53.3-fs-regress».

Обновить CHANGELOG.md — секция [3.13.34].

Обновить ROADMAP.md — 53.3-test-stand-fix ✅, TEST-NOTE-10.6/10.7 закрыты.

Переместить ТЗ в prompts/archive/day_53_3_test_stand_fix.md.

Отчёт — prompts/reports/day_53_3_test_stand_fix_report.md.

Автор ТЗ: архитектор
Дата: 04.10.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.34 — стенд docker-compose.test.yml поднимается без ручных шагов; scripts/run-tests.sh чистит том сам; теги агентов синхронизированы.