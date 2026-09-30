# День 50 — BUG-102: Retention и sweep_scheduled_scans падали на Mapper[Finding] (v3.13.27)

**Дата:** 30.09.2026
**ТЗ:** `TZ_FIX_BUG102_CELERY_MAPPER.md` (Блок 7 — Retention)
**Ветка:** `develop`
**Версия:** v3.13.26 → **v3.13.27**
**Приоритет:** 🔴 critical — retention не работал вообще

---

## 1. Итог

| ID | Баг | Статус |
|----|-----|--------|
| BUG-102 🔴 | Celery-воркер падал на `Mapper[Finding]` ... `'User'`; `run_retention` формально `succeeded`, но все 5 шагов возвращали `error`; `sweep_scheduled_scans` не запускал сканы | ✅ |

- Реализовано: **TASK-072** (фикс), **TASK-073** (тесты).
- Прогон: **304 → 317 unit passed** (+13), E2E **46/6 → 47 passed / 6 skipped** (+1).
- Блок 7 (Retention) закрыт.
- Найдено «заодно» (п. ТЗ «Проверить заодно»): тот же дефект ещё в 4 модулях — `retention/archiver.py`, `retention/cleaner.py`, `retention/exporter.py`, `services/access_service.py`.

---

## 2. Причина

Тот же класс, что BUG-096, но в другом модуле.

`manager/src/db/models.py:180`:

```python
reviewer = relationship("User", foreign_keys=[reviewed_by])
```

Связь объявлена **строкой**, а сам `User` определён в другом модуле —
`manager/src/auth/models.py`. SQLAlchemy ищет класс `User` в том же модуле
(`manager.src.db.models`), не находит и падает:

```
When initializing mapper Mapper[Finding(findings)],
expression 'User' failed to locate a name ('User')
```

В BUG-096 это чинили в `manager/src/api/findings.py` (там импортировали `User`).
В `manager/src/workers/tasks.py` импорта не было — а Celery-воркер в этот модуль
не заходит: `auth.models` в его графе импортов не тянется.

Ключевые свойства, из-за которых баг выглядел так противоречиво:

1. **Каскадность.** Падает инициализация mapper'ов **всего** registry: после первого
   сбоя `Mapper[Finding]` любая последующая попытка даёт «One or more mappers
   failed to initialize - can't proceed».
2. **`run_retention` не поднимает исключение.** Каждый шаг обёрнут в свой
   `try/except`, ловит ошибку и возвращает `{"archived": 0, "error": "..."}`.
   Итог — `status: completed`, лог `Retention run completed (dry_run=False)`,
   а работы не было. Именно поэтому баг прожил незамеченным до блока 7.
3. **Зависимость от контекста.** В процессе Manager (FastAPI) `auth.models`
   импортируется — там `auth.router` подключён, поэтому API-путь работал.
   Падало только то, что выполняется в воркере.

---

## 3. Решение

Вариант C из ТЗ (`manager/src/db/__init__.py`) **отклонён**: `auth.models`
импортирует `Base` из `db.models`, поэтому при первом импорте `auth.models`
получается частичный цикл. Проверено, а не предположено.

Реализованы Вариант A (основной) + Вариант B (страховка):

| Файл | Правка | Роль |
|------|--------|------|
| `manager/src/workers/tasks.py` | `from manager.src.auth.models import User  # noqa: F401` | **основной фикс** — точка входа воркера |
| `manager/src/workers/celery_app.py` | `configure_mappers()` + импорт обеих групп моделей | страховка (fail-fast) |
| `manager/src/retention/archiver.py` | импорт `User` | «заодно» |
| `manager/src/retention/cleaner.py` | импорт `User` | «заодно» |
| `manager/src/retention/exporter.py` | импорт `User` | «заодно» |
| `manager/src/services/access_service.py` | импорт `User` | «заодно» |

Замечание к Варианту B: `celery_app.py` и **без** фикса подтягивал `User`
транзитивно (это видно тестом `test_modules_importable_standalone[...celery_app]`,
который на коде без фикса проходит). Поэтому `configure_mappers()` там — не
лечение, а гарантия: при любом будущем изменении графа импортов воркер упадёт
на старте с внятной ошибкой, а не на середине retention-цикла.

Комментарии в коде объясняют, **почему** импорт нужен (а не просто «unused import»),
и содержат ссылку на то, что цикла нет: `db.models` не тянет retention,
`auth.models` тянет только `db.models`.

---

## 4. Тесты

### 4.1 Главная проблема тестирования

Проверка «в том же процессе pytest» **не способна поймать этот баг**. `User`
нужен в registry глобально и появляется там при первом же импорте любого
API-модуля. К моменту, когда тест доберётся до `configure_mappers()`, registry
уже «вылечен» — тест прошёл бы и на сломанном коде. Это не гипотеза: первая
версия тестов именно так и вела себя.

Отсюда решение: **регрессионные проверки запускаются в чистом подпроцессе**,
который импортирует ровно то, что импортирует Celery-воркер.

### 4.2 Отладка теста: FalseReferenceError вместо BUG-102

Первая версия функционального сценария строила схему через
`Base.metadata.create_all` прямо в подпроцессе. Это дало **не ту ошибку**:

```
sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column
'findings.reviewed_by' could not find table 'users' ...
```

Причина: таблица `users` попадает в `MetaData` только при импорте
`manager.src.auth.models`, а его импорт — это ровно то «лечение», которого мы
избегаем. Тест падал, но не по причине бага: он проверял бы работоспособность
фикса, а не наличие регрессии.

Итоговая схема: **родительский процесс** (где `auth.models` и так импортирован)
готовит SQLite-файл со всей схемой и одной записью `Schedule`, а сценарий в
подпроцессе открывает этот файл, не импортируя `auth.models`. Теперь падение —
настоящий BUG-102.

### 4.3 Состав `tests/unit/test_celery_mapper_v31327.py` (13 тестов)

| Группа | Тесты | Что проверяет |
|--------|--------|---------------|
| `TestCeleryMapperInit` | `test_worker_context_mapper_init` | чистый импорт `tasks` + `configure_mappers()` — главная регрессия |
| | `test_finding_mapper_initialized` | `Finding.reviewer` резолвится в `User` |
| | `test_modules_importable_standalone` ×6 | каждый из 6 модулей инициализирует mapper'ы сам |
| | `test_user_model_imported_before_finding` | статическая проверка импорта (чтобы баг не вернулся) |
| `TestRetentionScenarios` | `test_run_retention_no_mapper_error` | все 5 шагов без `error` на реальной БД |
| | `test_sweep_scheduled_scans_no_mapper_error` | sweep без `{'error': ...}` |
| | `test_scanned_task_dispatched_to_queue` | задача уходит в очередь `scanner_tasks` |
| | `test_no_mapper_errors_in_worker_stderr` | нет следов mapper-ошибки в выводе |

### 4.4 Проверка «тесты ловят баг»

Прогон с **откатом всех 6 исходных файлов** (`git stash push`):

```
8 failed, 1 passed, 4 errors
```

- 8 упавших — импорт-регрессии;
- 4 `errors` — сценарии; падение сценария сопровождается **настоящим** сообщением
  `RETENTION={"archived_audit": {"archived": 0, "error": "When initializing mapper
  Mapper[Finding(findings)], expression 'User' failed to locate a name ('User')...
  }}` — ровно то, что описано в ТЗ;
- 1 прошедший — `celery_app` standalone (см. п. 3: этот модуль и до фикса
  подтягивал `User` транзитивно).

С фиксом: `13 passed`.

---

## 5. E2E — и почему тест из ТЗ пришлось расширить

ТЗ предлагал `POST /api/retention/run?dry_run=true`. Проверка кода показала,
что этот эндпоинт выполняет retention **синхронно в процессе Manager**
(`manager/src/api/retention.py:39`), а не через Celery. В процессе Manager
`auth.models` импортирован — значит **этот тест прошёл бы и на сломанном коде**
и BUG-102 не поймал бы (это и есть TEST-NOTE-7.4 из ТЗ).

Через Celery задача уходит только через `POST /api/retention/start`
(`run_retention_task.delay`). Поэтому `tests/e2e/test_retention_e2e.py` проверяет
оба пути: контракт и 5 шагов без ошибок (пункт ТЗ) + постановку задачи в очередь
Celery с непустым `task_id` (путь, который падал). Если брокер недоступен —
`pytest.skip`, а не падение.

Честное ограничение: **результат выполнения воркером через API не проверяется**.
`retention.state` хранится в файле `data/retention_state.json` **внутри
контейнера воркера**, а том `manager/data` с воркером не смонтирован, поэтому
Manager состояние воркера не видит. Worker-сторона подтверждена чтением логов
(п. 6). Вынесено в TEST-NOTE-7.2.

---

## 6. Live-проверка (стенд, v3.13.27)

Пересобраны `manager`, `celery_worker`, `celery_beat`.

**1. Версия**
```
GET /api/health → {"status":"healthy","version":"3.13.27"}
```

**2. `POST /api/retention/run?dry_run=true`** — все 5 шагов чистые:
```
status  = completed
archived_audit     = {"archived":0}
archived_findings  = {"archived":0}
cleaned_archive    = {"audit_logs_archive":{"deleted":0,"dry_run":true},
                      "findings_archive":{"deleted":0,"dry_run":true}}
cleaned_tasks      = {"deleted":0,"dry_run":true}
exported           = {"exported":0}
```

**3. Целевой путь — Celery** (`POST /api/retention/start`), логи воркера:
```
Task manager.src.workers.tasks.run_retention[31803975-...] received
Loaded retention policies: ['audit_events', 'findings', 'tasks', 'logs']
Retention run completed (dry_run=False)
Retention (Celery) completed: {'archived_audit': {'archived': 0},
  'archived_findings': {'archived': 0}, 'cleaned_archive': {'audit_logs_archive':
  {'deleted': 0}, 'findings_archive': {'deleted': 0}}, 'cleaned_tasks':
  {'deleted': 0}, 'exported': {'exported': 0}, 'rotated_logs': {'removed': []}, ...}
Task ... run_retention[...] succeeded in 0.154s
```
Поиск `failed to locate a name|When initializing mapper` по логам воркера — **0 совпадений**.
(Здесь же — реальный прогон `dry_run=False`: архивировано/удалено 0 записей,
данные свежие, TTL 30/90/180 дней не вышли.)

**4. `sweep_scheduled_scans`** (отправлен напрямую в воркер):
```
Task manager.src.workers.tasks.sweep_scheduled_scans[dd96a8fd-...] succeeded in 0.149s:
{'dispatched': []}
```
`dispatched` пуст, потому что расписаний в БД нет; главное — нет mapper-ошибки.

**5. Прогоны:** `317 unit passed`; `47 passed, 6 skipped` E2E (0 failed, 0 errors).

---

## 7. Прочее

- Версия 3.13.26 → 3.13.27 в `.env`, `.env.example`, `docker-compose.yml`.
  Попутно исправлены **устаревшие fallback** `${VERSION:-3.13.12}` (6 мест) —
  при отсутствии `.env` образы собирались с версией трёхсот релизов назад.
- `docker-compose.override.yml` (временный, `AUTH_LOGIN_MAX_ATTEMPTS=500` для E2E)
  после прогона **удалён**, лимит логинов возвращён к дефолту 5/мин, сканер
  перезапущен.
- В рабочем дереве были незакоммиченные правки `STATE.md` / `ROADMAP.md` /
  `ARCHITECTURE.md` от архитектора (конденсация описаний). Они не откатывались и
  включены в коммит этого дня.

---

## 8. Изменённые файлы

| # | Файл | Действие | Задача |
|---|------|----------|--------|
| 1 | `manager/src/workers/tasks.py` | явный импорт `User` до первого обращения к моделям | TASK-072 |
| 2 | `manager/src/workers/celery_app.py` | `configure_mappers()` + импорт моделей (страховка) | TASK-072 |
| 3 | `manager/src/retention/archiver.py` | импорт `User` | TASK-072 |
| 4 | `manager/src/retention/cleaner.py` | импорт `User` | TASK-072 |
| 5 | `manager/src/retention/exporter.py` | импорт `User` | TASK-072 |
| 6 | `manager/src/services/access_service.py` | импорт `User` | TASK-072 |
| 7 | `tests/unit/test_celery_mapper_v31327.py` | создан (13 тестов) | TASK-073 |
| 8 | `tests/e2e/test_retention_e2e.py` | создан (1 тест) | TASK-073 |
| 9 | `.env`, `.env.example`, `docker-compose.yml` | версия → 3.13.27 | релиз |
| 10 | `CHANGELOG.md`, `STATE.md`, `ROADMAP.md` | BUG-102 → ✅, TEST-NOTE-7.1…7.5 | док |

---

## 9. Критерии приёмки

| Критерий ТЗ | Факт |
|-------------|------|
| `py_compile manager/src/workers/tasks.py` | ✅ OK |
| `pytest tests/unit/test_celery_mapper_v31327.py` | ✅ 13 passed (требовалось 4) |
| `pytest tests/e2e/test_retention_e2e.py` | ✅ 1 passed |
| Полный unit 305+ | ✅ 317 passed |
| `/api/health` → 3.13.27 | ✅ |
| `POST /api/retention/run?dry_run=true` → 5 шагов без error | ✅ |
| Логи Celery без `Mapper[Finding] ... 'User'` | ✅ 0 совпадений |
| `sweep_scheduled_scans` без mapper-ошибки | ✅ `{'dispatched': []}` |
| findings / audit_logs / scan_tasks не изменились после dry_run | ✅ количество findings идентично до/после (проверка в E2E) |
| STATE.md, ROADMAP.md, CHANGELOG.md обновлены | ✅ |