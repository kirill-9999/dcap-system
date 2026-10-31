# Отчёт: День 35 — Архивация данных (retention)

**Дата:** 02.09.2026
**ТЗ:** `prompts/tz/day_35_data_retention.md`
**Роль:** Кодер
**Версия:** v3.3.0

---

## Резюме

Реализована **автоматическая архивация и очистка данных** для предотвращения переполнения БД: политики хранения (`RetentionPolicy`), архивация аудит-событий и находок в архивные таблицы (`Archiver`), очистка устаревших архивов и завершённых задач (`Cleaner`), экспорт архивов в JSON/CSV (`Exporter`), периодический запуск фоновым планировщиком, API `/api/retention/*` и раздел «Хранение данных» в WebUI.

> **Адаптации под реальную архитектуру проекта (Celery и Alembic в проекте отсутствуют):**
> - **Celery отсутствует** в `requirements.txt` и не используется нигде в коде (есть только Redis-кэш прав). Фоновая задача реализована **фоновым потоком-планировщиком** (`retention/scheduler.py`, `threading.Thread`, daemon), стартующим при запуске Manager. Замена Celery Beat — `run_retention` (синхронный модульный вызов), ручной запуск через API выполняется синхронно в потоке запроса.
> - **Alembic отсутствует.** Новые архивные таблицы (`audit_logs_archive`, `findings_archive`) создаются автоматически существующим `Base.metadata.create_all()` на старте (новые таблицы, ALTER не требуется). Файл Alembic-миграции `002_add_archive_tables.py` из ТЗ не создавался — замена на автогенерацию таблиц.
> - **Статус последнего запуска** сохранён без выделенной таблицы (ТЗ допускал «хранить в отдельной таблице»). Использован лёгкий `retention/state.py` — in-memory состояние + персист в `manager/data/retention_state.json` (каталог уже в `.gitignore`).
> - **Архивация находок** включена наряду с аудит-событиями (используется модель `FindingArchive` из ТЗ), т.к. ТЗ описывает и `archive_findings`, и модель. Для `findings` и `tasks` политика применяет и архивацию/очистку в соответствии с TTL.

---

## Ключевые решения по коду

- **Синхронный полу-цикл** вместо Celery-таски: вся логика собрана в `run_retention(dry_run)` в `retention/runtime.py`; планировщик (`scheduler.py`) зовёт её в фоновом потоке с интервалом `interval_hours`, API — напрямую.
- **Защита от параллельного запуска**: `state.get_retention_status()["running"]` — повторный вызов при уже выполняющемся цикле отклоняется (`"skipped"`).
- **Архивные модели** повторяют реальные поля `AuditLog`/`Finding` (включая `metadata_json`, `task_id`, `subcategory`, `value`, `confidence`, `context`) и добавляют `archived_at`; у обеих есть `to_dict()` для экспорта.
- **`RetentionPolicy`** читает конфиг `retention` и раздаёт TTL/даты отсечения; дефолты совпадают с ТЗ (аудит 90/365, находки 180, задачи 30, логи 30 дней / 100 МБ).
- **API `/api/retention/*`** защищён `require_admin` (роль admin) поверх middleware-аутентификации; `/export` принимает JSON-тело `{data_type, limit}` (совместимо с `api.post` WebUI).

---

## Выполненная работа

### 1. Архивные модели (MODIFIED)

- **`manager/src/db/models.py`** — добавлены **`AuditLogArchive`** (`audit_logs_archive`) и **`FindingArchive`** (`findings_archive`) с полями по реальным `AuditLog`/`Finding` + `archived_at`; у обеих — `to_dict()`. Добавлены в `__all__`. Таблицы создаются `create_all()` на старте.

### 2. Пакет `retention/` (NEW)

| Файл | Назначение |
|------|-----------|
| `manager/src/retention/__init__.py` | Пакет, реэкспорт публичных классов |
| `policies.py` | **`RetentionPolicy`**: TTL/архивный TTL/даты отсечения, `get_ttl`, `get_cutoff_date`, `get_archive_ttl`, `archive_enabled` |
| `archiver.py` | **`Archiver`**: `archive_audit_events` (перемещение старых событий в `audit_logs_archive`), `archive_findings` (в `findings_archive`); dry_run, батч `_move_to_archive` |
| `cleaner.py` | **`Cleaner`**: `clean_archive_tables` (по `archive_ttl_days`), `clean_completed_tasks` (задачи `status="completed"` старше TTL), `clean_log_rotation` (ротация лог-файлов по возрасту/размеру) |
| `exporter.py` | **`Exporter`**: `export_archived_audit_events`/`export_archived_findings` в JSON/CSV, настраиваемый путь/формат |
| `state.py` | Лёгкое состояние retention (last_run, last_result, running) + персист в JSON |
| `runtime.py` | **`run_retention(dry_run)`** — синхронный полный цикл (архивация → очистка → экспорт → ротация логов) |
| `scheduler.py` | **`start_scheduler`/`stop_scheduler`** — фоновый поток вместо Celery Beat, интервал `interval_hours` |

### 3. API (NEW)

- **`manager/src/api/retention.py`** — роутер `/api/retention` (prefix), защита `require_admin`:
  - `GET /api/retention/policies` — текущие политики + enabled/interval
  - `POST /api/retention/run?dry_run=` — ручной запуск (синхронно)
  - `GET /api/retention/status` — статус последнего запуска + планировщик
  - `POST /api/retention/start` — запуск фонового планировщика
  - `POST /api/retention/export` — экспорт (`data_type` audit/findings, `limit`)
- **`manager/src/main.py`** — зарегистрирован `retention_router`; на старте вызывается `start_scheduler()`. Версия → **3.3.0**.

### 4. Конфигурация (MODIFIED)

- **`manager/src/config.py`** — дефолты секции `retention` (enabled, interval_hours, audit_events/findings/tasks/logs/export).
- **`manager/config/config.json`** — добавлена секция `retention` (TTL 90/365/180/30, интервал 24 ч, экспорт json в `data/archive/`).

### 5. WebUI (MODIFIED)

- **`webui/templates/settings.html`** — новый карточный блок **«Хранение данных (архивация/очистка)»**: вывод политик (TTL аудита/находок/задач, формат/путь экспорта), статистика (аудит/архив/находки/задачи), кнопки «Запустить архивацию сейчас», «Dry-run», «Экспорт аудит/находки», строка статуса последнего запуска. JS: `loadRetention()`, `runRetention(dryRun)`, `exportArchive(type)`. WebUI-прокси (`webui/api/routes.py`) автоматически форвардит `/api/retention/*` в Manager.

### 6. Прочее

- **`.gitignore`** — добавлен `data/archive/` (экспортные файлы retention).
- **`prompts/tz/day_35_data_retention.md`** → перенесён в `prompts/archive/`.

---

## Тестирование

```
python -m pytest manager/tests/test_retention.py -q   # 9 passed
python -m pytest manager/tests/ -q                     # 45 passed (все: retention+security+ad)
```

**`manager/tests/test_retention.py` (NEW, 9 тестов):**
- `RetentionProfile`: дефолтные TTL, архивный TTL, дата отсечения.
- `Archiver`: архивация аудит-событий (старое → архив, новое остаётся), dry-run не мутирует данные, архивация находок.
- `Cleaner`: очистка архивных таблиц по `archive_ttl`, очистка завершённых задач (старых `completed`), свежие не трогаются.
- `Exporter`: JSON-экспорт (файл создан, содержимое корректно), CSV-экспорт (header + строки).

### E2E-проверка на реальном Manager (`:8000`)

- Manager перезапущен с новой версией — планировщик стартовал автоматически (в `status` появился `last_run`, `running:false`).
- `GET /api/retention/policies` — политики загружены из конфига (TTL 90/180/30, archive 365, enabled, interval 24).
- `POST /api/retention/run?dry_run=true` — полный цикл без мутаций (dry_run флаги).
- `POST /api/retention/export {data_type:audit}` / `{data_type:findings}` — экспорт (пусто при отсутствии данных).
- **Полный цикл архивации:** в `audit_logs` внесена синтетическая запись 95 дней (TTL аудита 90) → `POST /api/retention/run` → событие перемещено в `audit_logs_archive` (audit_logs=0, archive=1), экспортировано в `data/archive/audit_archive_*.json`. Синтетические данные после проверки удалены, БД очищена.
- Прокси WebUI (`:8001/api/retention/policies`) — форвардится в Manager, отвечает корректно; страница `/settings` отдаёт 200.
- В `manager/dcap.db` присутствуют таблицы `audit_logs_archive`, `findings_archive`.

> **Найден и исправлен баг флага `running`:** `state.set_last_run()` сохранял состояние с `running:true` (т.к. `set_running(False)` вызывается в `finally` уже ПОСЛЕ сохранения и не персистится). После жёсткого прерывания процесса во время прогона файл `manager/data/retention_state.json` навсегда держал `running:true` → статус в API показывал «выполняется», а `run_retention` отказывался стартовать (`skipped: already running`). Исправлено: `set_last_run()` сбрасывает `running` в `False` перед сохранением, плюс при загрузке модуля устаревший флаг сбрасывается. Добавлен тест `test_stale_running_flag_does_not_block`.

### Проверка сборки

- `python -c "import manager.src.main; import manager.src.api.retention"` — без ошибок (SPNEGO-warning ожидаем, AD заглушка).
- `python -m pytest manager/tests/ -q` — **45 passed**.

---

## Файлы

**NEW:**
- `manager/src/retention/__init__.py`
- `manager/src/retention/policies.py`
- `manager/src/retention/archiver.py`
- `manager/src/retention/cleaner.py`
- `manager/src/retention/exporter.py`
- `manager/src/retention/state.py`
- `manager/src/retention/runtime.py`
- `manager/src/retention/scheduler.py`
- `manager/src/api/retention.py`
- `manager/tests/test_retention.py`
- `prompts/reports/day_35_report.md` (этот отчёт)

**Modified:**
- `manager/src/db/models.py` (+ `AuditLogArchive`, `FindingArchive`)
- `manager/src/config.py` (дефолты секции `retention`)
- `manager/config/config.json` (секция `retention`)
- `manager/src/main.py` (регистрация retention_router, автозапуск планировщика, версия 3.3.0)
- `webui/templates/settings.html` (блок «Хранение данных» + JS)
- `.gitignore` (+ `data/archive/`)
- `AGENTS.md` (версия v3.3.0, статус, строка релиза)

**Moved:**
- `prompts/tz/day_35_data_retention.md` → `prompts/archive/day_35_data_retention.md`

---

## Запуск (ручное тестирование)

```powershell
# 1. Запуск Manager (планировщик архивации стартует автоматически)
python run_manager.py

# 2. WebUI
python run_webui.py   # → http://127.0.0.1:8001/settings → «Хранение данных»

# 3. API (Bearer JWT admin)
# логин: POST /api/auth/login {"username":"admin","password":"admin123"} → access_token

# политики
curl.exe -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/retention/policies

# ручной запуск (dry-run и реальный)
curl.exe -X POST -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/retention/run?dry_run=true"
curl.exe -X POST -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/retention/run"

# статус / запуск планировщика
curl.exe -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/retention/status
curl.exe -X POST -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/retention/start

# экспорт архива в data/archive/*.json (или csv — см. конфиг retention.export.format)
curl.exe -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{\"data_type\":\"audit\",\"limit\":1000}' http://127.0.0.1:8000/api/retention/export
```

**Настройка политик:** `manager/config/config.json` → `retention` (TTL в днях, `archive_enabled`, `export.format` json/csv, `export.path`, `interval_hours`). Экспортные файлы и статус retention (`manager/data/`) в `.gitignore`.

---

## Команда коммита

На ветке `feature/day_35_retention`:

```powershell
git checkout -b feature/day_35_retention
git add -A
git commit -m "feat: День 35 — Архивация данных (retention)

- Архивные таблицы: audit_logs_archive, findings_archive
- Политики хранения (RetentionPolicy, TTL из конфига)
- Архивация аудит-событий и находок (Archiver, dry-run)
- Очистка архивов и завершённых задач (Cleaner) + ротация логов
- Экспорт архивов в JSON/CSV (Exporter)
- Планировщик: фоновый поток вместо Celery Beat (interval_hours)
- API /api/retention/*: policies, run, status, start, export (require_admin)
- WebUI: раздел «Хранение данных» в настройках
- Версия v3.3.0, тесты manager/tests/test_retention.py (8)"
```

---

## Обратная связь архитектору

- **Celery в проекте отсутствует** (ни в `requirements.txt`, ни в коде). Периодическая архивация реализована **фоновым потоком** в процессе Manager (как и предыдущий «планировщик вместо Celery» подход в других местах). Если требуется полноценный Celery+Bеat — это отдельная инфраструктурная работа, текущая реализация для одиночного Manager покрывает потребность.
- **Alembic не используется** — вместо файла миграции архивные таблицы создаются `create_all()`. Для реальной БД это безопасно (только новые таблицы).
- **Статус последнего запуска** хранится в JSON (`manager/data/retention_state.json`), а не в БД — минимальный вес, ТЗ допускал любой вариант.
- **Архивация находок** включена наравне с аудит-событиями (модель `FindingArchive` из ТЗ использована). Если по ТЗ находки должны только удаляться (без архива) — достаточно выставить `findings` без архивации (сейчас архивируются всегда при наличии TTL).
- **Прокси WebUI** автоматически пропустил `/api/retention/*` — отдельной правки `webui/api/routes.py` не потребовалось.