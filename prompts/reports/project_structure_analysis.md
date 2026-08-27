# Структура проекта DCAP: связи и неиспользуемые файлы

**Дата:** 28.08.2026  
**Для:** Архитектора

---

## 1. Корень проекта

### Запускаемые скрипты (entry points)

| Файл | Назначение | Вызывает |
|------|------------|----------|
| `run_scanner.py` | Запуск сканера | `scanner.src.managed_scanner.ManagedScanner`, `scanner.src.config_loader.load_config` |
| `run_webui.py` | Запуск WebUI :8001 | `webui.config.*`, uvicorn `"webui.main:app"` |
| `init_db.py` | Создание БД | `db.session.init_db` (через `sys.path.insert`) |
| `init_db_data.py` | Заполнение БД тестовыми данными | Только sqlite3 (прямой SQL) |
| `fix_db.py` | Исправление БД | Только sqlite3 (прямой SQL) |
| `test_models.py` | Тест моделей БД | `db.models.*`, `db.session.*` (через `sys.path.insert`) |
| `test_parse.py` | Тест парсинга icacls | `connectors.permissions.local.LocalPermissionCollector` (через `sys.path.insert`) |
| `test_access_management.py` | Тест API доступа | Только `requests` (REST API) |

### Конфиги и документация

| Файл | Назначение | Используется |
|------|------------|-------------|
| `AGENTS.md` | Инструкции для LLM | Да (контекст сессий) |
| `README.md` | Описание проекта | Да |
| `project_plan.md` | План проекта | Да |
| `project_context.md` | Контекст проекта | Да |
| `requirements.txt` | Зависимости Python | Да |
| `pyproject.toml` | Конфиг black/ruff/mypy | Да |
| `.gitignore` | Исключения git | Да |
| `state.json` | Состояние Windows-агента | ⚠️ **Легаси** — принадлежит audit-agent, но лежит в корне |
| `dcap.db` | БД | ⚠️ **Легаси** — устаревшая копия (AGENTS.md: "не трогать") |
| `structure.txt` | Структура проекта | ⚠️ **Устарел** (AGENTS.md: "частично устарел") |
| `WEBUI_TEST.md` | Инструкция тестирования WebUI | ⚠️ **Не упоминается** в коде |
| `RELEASE_NOTES_v2.0.1.md` | Релизные заметки v2.0.1 | ⚠️ **Инфо** — не используется кодом |
| `Makefile` | Docker-команды | ⚠️ **Фикция** (AGENTS.md: "docker-compose.yml отсутствует") |
| `backlog.txt` | Бэклог задач | ⚠️ **Инфо** — не используется кодом |
| `prompts/reports/algorithm_analysis.md` | Анализ алгоритма | ⚠️ **Справка** — не используется кодом |

### Служебные директории (gitignored)

| Директория | Назначение |
|------------|------------|
| `buffer/` | Буфер Windows-агента (runtime) |
| `catalog/` | Каталог сканера (runtime) |
| `logs/` | Логи (gitignored) |
| `temp/` | Временные скрипты (gitignored) |
| `test_files/` | Тестовые файлы (gitignored) |
| `.claude/` | Настройки Claude |
| `.pytest_cache/` | Кэш pytest |

---

## 2. Manager (`manager/src/`)

### Карта зависимостей

```
manager/src/main.py
├── api/resources.py
├── api/tasks.py
├── api/findings.py
├── api/catalog.py
├── api/scanner.py
│   └── api/resources.py (get_default_config, deep_merge)
├── api/permissions.py
│   ├── services/access_service.py
│   │   ├── db/models.py
│   │   ├── connectors/permissions/__init__.py
│   │   │   ├── permissions/base.py
│   │   │   ├── permissions/local.py → base.py
│   │   │   ├── permissions/remote.py → base.py
│   │   │   ├── permissions/ad.py → base.py
│   │   │   └── permissions/factory.py
│   │   │       ├── permissions/base.py
│   │   │       ├── permissions/local.py
│   │   │       ├── permissions/remote.py
│   │   │       ├── permissions/ad.py
│   │   │       └── services/access_config.py
│   │   └── services/access_config.py
│   └── services/access_config.py
└── api/audit.py

db/models.py ← (leaf)
db/session.py → db/models.py
db/__init__.py → db/session.py, db/models.py
api/__init__.py → api/resources.py, api/scanner.py, api/tasks.py, api/findings.py, api/catalog.py

connectors/audit/__init__.py → connectors/audit/windows_audit.py
core/scheduler.py → db/session.py, db/models.py  ← НЕ ИСПОЛЬЗУЕТСЯ
db/migrations/run_migration.py  ← ENTRY POINT, НЕ ИСПОЛЬЗУЕТСЯ
```

### Неиспользуемые файлы manager

| Файл | Статус | Причина |
|------|--------|---------|
| `core/scheduler.py` | ❌ **Мёртвый код** | Импортирует несуществующие `get_session`, `TaskStatus`. Не импортируется ни одним файлом. |
| `connectors/audit/__init__.py` | ⚠️ **Импортирует, но не используется** | `WindowsAuditCollector` импортируется, но в `main.py` не подключается к API. |
| `connectors/audit/windows_audit.py` | ⚠️ **Дублирует агента** | Коллектор Windows-событий внутри менеджера, хотя агент (`audit-agent/`) делает это сам. |
| `connectors/permissions/test_collector.py` | ❌ **Тестовый скрипт** | Не импортируется, использует `sys.path.insert` хак. |
| `db/migrations/run_migration.py` | ⚠️ **Entry point** | Не используется автоматически, запускается вручную. |
| `connectors/permissions/remote.py` | ⚠️ **Заглушка** | Импортируется factory.py, но не имеет реальной логики (все методы pass/return {}). |

---

## 3. Scanner (`scanner/`)

### Карта зависимостей (ключевое)

```
scanner/src/managed_scanner.py (ENTRY POINT через run_scanner.py)
├── scanner/core/orchestrator.py
│   ├── scanner/core/base.py           ← ФУНДАМЕНТ: FileContext, ClassificationResult, IClassifier...
│   ├── scanner/core/state_manager.py  → core/base.py
│   ├── scanner/core/metrics.py        → core/base.py
│   ├── scanner/core/logger.py
│   ├── scanner/core/memory_manager.py
│   ├── scanner/core/catalog_manager.py → core/base.py
│   ├── scanner/core/adaptive_cache_manager.py
│   ├── scanner/utils/performance_monitor.py
│   └── scanner/utils/file_hasher.py
├── scanner/connectors/filesystem.py → core/base.py, connectors/base.py
├── scanner/handlers/finding_collector.py → core/base.py
├── scanner/src/config_loader.py
├── scanner/classifiers/pii_classifier.py (lazy)
│   ├── scanner/classifiers/ocr_worker.py
│   └── scanner/utils/document_extractor.py → utils/ocr_engine.py
├── scanner/classifiers/credentials_classifier.py (lazy) → core/base.py
└── scanner/classifiers/code_classifier.py (lazy) → core/base.py
```

### Offline-модуль (НЕ ПОДКЛЮЧЕН к managed_scanner.py)

```
scanner/src/offline/
├── queue.py      (leaf — SQLite очередь)
├── storage.py    (leaf — хранение найденных файлов)
├── detector.py   → dcap/manager_pb2.py, dcap/manager_pb2_grpc.py  ← НЕ СУЩЕСТВУЕТ в репо
└── sync.py       → dcap/manager_pb2.py, dcap/manager_pb2_grpc.py  ← НЕ СУЩЕСТВУЕТ в репо
                    + offline/queue.py + offline/detector.py
```

### Modes (НЕ ПОДКЛЮЧЕНЫ к managed_scanner.py)

```
scanner/src/modes/
├── base.py       (leaf — абстрактный ScannerMode)
├── standalone.py → modes/base.py, offline/queue.py, offline/storage.py, offline/detector.py
├── managed.py    → modes/base.py, offline/queue.py, offline/storage.py, offline/detector.py, offline/sync.py
└── hybrid.py     → modes/base.py, modes/managed.py, modes/standalone.py, offline/detector.py
```

### Неиспользуемые файлы scanner

| Файл | Статус | Причина |
|------|--------|---------|
| `core/test_source.py` | ❌ **Мёртвый код** | Не импортируется. Тестовый источник данных. |
| `core/dispatcher.py` | ❌ **Мёртвый код** | Не импортируется. Динамический загрузчик классификаторов (не используется orchestrator). |
| `core/config_manager.py` | ❌ **Мёртвый код** | Не импортируется. Дублирует `config_loader.py`. |
| `core/resource_manager.py` | ❌ **Мёртвый код** | Не импортируется. Управление ресурсами ( не задействован). |
| `core/memory_profiler.py` | ❌ **Мёртвый код** | Не импортируется. Профилировщик памяти. |
| `utils/ocr_pool.py` | ❌ **Мёртвый код** | Не импортируется. Пул OCR-воркеров. |
| `utils/safe_ocr_worker.py` | ❌ **Мёртвый код** | Не импортируется. Безопасный OCR-воркер. |
| `classifiers/model_worker.py` | ❌ **Мёртвый код** | Не импортируется. ML-классификатор. |
| `connectors/s3_connector.py` | ❌ **Заглушка v3.0** | Не импортируется. S3/MinIO коннектор (запланирован на v3.0). |
| `src/offline/detector.py` | ❌ **Не работает** | Импортирует несуществующий `dcap/manager_pb2` (gRPC). |
| `src/offline/sync.py` | ❌ **Не работает** | Импортирует несуществующий `dcap/manager_pb2`. |
| `src/offline/queue.py` | ⚠️ **Используется modes/** | Подключен к modes/ (managed, standalone), но modes/ не используются. |
| `src/offline/storage.py` | ⚠️ **Используется modes/** | Аналогично. |
| `src/modes/*.py` | ❌ **Альтернативная архитектура** | Полная архитектура режимов (standalone/managed/hybrid), но `run_scanner.py` использует `ManagedScanner` напрямую. |
| `connectors/base.py` | ⚠️ **Используется** | Импортируется filesystem.py и s3_connector.py. s3 не используется — но base нужен filesystem. |

---

## 4. Audit-Agent Windows (`audit-agent/`)

### Карта зависимостей

```
audit-agent/main.py (ENTRY POINT)
├── collector.py       (WindowsAuditCollector)
├── buffer.py          (BufferManager — SQLite)
├── sender.py          (Sender — send_events, send_heartbeat)
└── heartbeat.py       (HeartbeatSender)

audit-agent/service.py (ENTRY POINT — Windows-служба)
├── main.py            (AuditAgent, main)
└── config_loader.py   (load_config)

audit-agent/config_loader.py
```

### Неиспользуемые файлы

| Файл | Статус | Причина |
|------|--------|---------|
| `config_loader.py` | ⚠️ **Дублирование** | Используется только `service.py`. `main.py` загружает конфиг напрямую через `json.load` (стр. 53-55). Два разных способа загрузки конфига. |
| `heartbeat.py` | ⚠️ **Дублирование** | `HeartbeatSender` импортируется `main.py`, но heartbeat **также** отправляется через `sender.send_heartbeat()`. Два механизма heartbeat. |

---

## 5. Audit-Agent Linux (`audit-agent-linux/`)

### Карта зависимостей

```
audit-agent-linux/main.py (ENTRY POINT)
├── collector.py   (InotifyCollector — watchdog)
├── buffer.py      (BufferManager — SQLite)
└── sender.py      (Sender — send_events, send_heartbeat)
```

### Неиспользуемые файлы

| Файл | Статус | Причина |
|------|--------|---------|
| `heartbeat.py` | ❌ **Мёртвый код** | Не импортируется `main.py`. Heartbeat реализован инлайн в `main.py` (стр. 95-104) через `sender.send_heartbeat()`. |

---

## 6. WebUI (`webui/`)

### Карта зависимостей

```
webui/main.py (ENTRY POINT через run_webui.py)
├── webui/config.py       (WEBUI_HOST, WEBUI_PORT, DEBUG, DATABASE_URL)
└── webui/api/routes.py   (API-эндпоинты)
    ├── webui/api/schemas.py  (Pydantic-модели)
    └── webui/config.py       (DATABASE_URL)

webui/run_webui.py — ДУБЛИКАТ корневого run_webui.py
```

### Дублирование

| Файл корня | Файл в webui/ | Разница |
|------------|---------------|---------|
| `run_webui.py` | `webui/run_webui.py` | Корневой использует `webui.config.*`. `webui/run_webui.py` хардкодит `host=0.0.0.0, port=8001, reload=True` |

### Неиспользуемые файлы

| Файл | Статус | Причина |
|------|--------|---------|
| `webui/run_webui.py` | ⚠️ **Дубликат** | Корневой `run_webui.py` — каноничный (AGENTS.md). `webui/run_webui.py` — легаси. |
| `webui/api/__init__.py` | ❌ **Отсутствует** | Нет `__init__.py` в `webui/api/`. Работает за счёт абсолютных импортов, но ненадёжно. |
| `api/schemas.py` | ⚠️ **Частично дублирует** | Определяет Pydantic-модели (`FindingResponse`, `TaskResponse` и др.), но `routes.py` возвращает `dict` напрямую (не через схемы). Схемы импортируются, но **не используются** в response-модели. |

---

## 7. Shared (`shared/`)

| Файл | Статус | Причина |
|------|--------|---------|
| `event_schema.py` | ❌ **Мёртвый код** | Определяет `UnifiedEvent` (Pydantic). Не импортируется **ни одним файлом** в проекте. Создан для Day 25 (UnifiedEvent format), но не подключен к ни одному компоненту. |

---

## 8. Tests (`tests/`)

| Файл | Статус | Причина |
|------|--------|---------|
| `tests/integration/test_api.py` | ⚠️ **Не запускается** | Только `requests` + `pytest`. Не импортирует проект. Нетpytest в requirements. |
| `tests/integration/test_audit.py` | ⚠️ **Не запускается** | Аналогично. |
| `tests/integration/test_e2e.py` | ⚠️ **Не запускается** | Аналогично. |
| `tests/integration/test_scanner.py` | ⚠️ **Не запускается** | Аналогично. |
| `tests/integration/test_webui.py` | ⚠️ **Не запускается** | Аналогично. |
| `tests/integration/conftest.py` | ⚠️ **Не запускается** | Аналогично. |
| `tests/integration/README.md` | ⚠️ **Документация** | Описание тестов. |

AGENTS.md: "Pytest отсутствует (папка `manager/tests/` пуста). Тесты — обычные скрипты: `test_models.py`, `test_parse.py`." Файлы в `tests/integration/` — вероятно, легаси-заготовки.

---

## 9. Сводная таблица неиспользуемых файлов

### Мёртвый код (удалить)

| # | Файл | Компонент | Причина |
|---|------|-----------|---------|
| 1 | `scanner/core/test_source.py` | Scanner | Не импортируется |
| 2 | `scanner/core/dispatcher.py` | Scanner | Не импортируется |
| 3 | `scanner/core/config_manager.py` | Scanner | Не импортируется, дублирует config_loader |
| 4 | `scanner/core/resource_manager.py` | Scanner | Не импортируется |
| 5 | `scanner/core/memory_profiler.py` | Scanner | Не импортируется |
| 6 | `scanner/utils/ocr_pool.py` | Scanner | Не импортируется |
| 7 | `scanner/utils/safe_ocr_worker.py` | Scanner | Не импортируется |
| 8 | `scanner/classifiers/model_worker.py` | Scanner | Не импортируется |
| 9 | `scanner/src/offline/detector.py` | Scanner | Импортирует несуществующий dcap/manager_pb2 |
| 10 | `scanner/src/offline/sync.py` | Scanner | Импортирует несуществующий dcap/manager_pb2 |
| 11 | `shared/event_schema.py` | Shared | Не импортируется ни одним файлом |
| 12 | `audit-agent-linux/heartbeat.py` | Linux Agent | Не импортируется main.py (heartbeat инлайн) |
| 13 | `manager/src/core/scheduler.py` | Manager | Импортирует несуществующие get_session, TaskStatus |

### Неиспользуемые режимы (альтернативная архитектура)

| # | Файл | Компонент | Причина |
|---|------|-----------|---------|
| 14 | `scanner/src/modes/base.py` | Scanner | Modes не используются run_scanner.py |
| 15 | `scanner/src/modes/managed.py` | Scanner | Modes не используются run_scanner.py |
| 16 | `scanner/src/modes/standalone.py` | Scanner | Modes не используются run_scanner.py |
| 17 | `scanner/src/modes/hybrid.py` | Scanner | Modes не используются run_scanner.py |
| 18 | `scanner/src/offline/queue.py` | Scanner | Используется только modes/ |
| 19 | `scanner/src/offline/storage.py` | Scanner | Используется только modes/ |

### Заглушки (оставить для v3.0)

| # | Файл | Компонент | Причина |
|---|------|-----------|---------|
| 20 | `scanner/connectors/s3_connector.py` | Scanner | Запланирован на v3.0 (S3/MinIO) |
| 21 | `manager/src/connectors/permissions/remote.py` | Manager | Заглушка, все методы pass |

### Дубликаты и легаси

| # | Файл | Компонент | Причина |
|---|------|-----------|---------|
| 22 | `webui/run_webui.py` | WebUI | Дубликат корневого `run_webui.py` |
| 23 | `state.json` (корень) | Root | Принадлежит audit-agent, лежит в корне |
| 24 | `dcap.db` (корень) | Root | Устаревшая копия БД |
| 25 | `structure.txt` | Root | Устарел (AGENTS.md) |
| 26 | `Makefile` | Root | Фикция — docker-compose.yml отсутствует |
| 27 | `WEBUI_TEST.md` | Root | Не упоминается в коде |

### Тестовые скрипты (не мёртвый код, а утилиты)

| # | Файл | Компонент | Причина |
|---|------|-----------|---------|
| 28 | `init_db_data.py` | Root | Тестовое заполнение БД |
| 29 | `fix_db.py` | Root | Разовая утилита |
| 30 | `test_models.py` | Root | Ручной тест |
| 31 | `test_parse.py` | Root | Ручной тест |
| 32 | `test_access_management.py` | Root | Ручной тест |
| 33 | `manager/connectors/permissions/test_collector.py` | Manager | Ручной тест |
| 34 | `tests/integration/*.py` (6 файлов) | Tests | Pytest-заготовки (pytest не установлен) |

---

## 10. Проблемы зависимостей

### Разрывы связей

| Проблема | Где | Описание |
|----------|-----|----------|
| **Offline-модуль не подключен** | `scanner/src/offline/` → `managed_scanner.py` | Модуль реализован, но ManagedScanner его не использует. Результаты теряются. |
| **Modes не используются** | `scanner/src/modes/` → `run_scanner.py` | Полная альтернативная архитектура, но точка входа — ManagedScanner напрямую. |
| **gRPC-зависимости отсутствуют** | `offline/detector.py`, `offline/sync.py` | Импортируют `dcap/manager_pb2` — директория `dcap/` не существует в репо. |
| **heartbeat.py дублируется** | `audit-agent/` | И `HeartbeatSender`, и `Sender.send_heartbeat()` — два механизма heartbeat. |
| **config_loader дублируется** | `audit-agent/` | `main.py` загружает JSON напрямую, `config_loader.py` используется только `service.py`. |
| **shared/event_schema.py не подключен** | `shared/` → все компоненты | `UnifiedEvent` определён, но не используется нигде. |
| **scheduler.py сломан** | `manager/src/core/scheduler.py` | Импортирует `get_session` и `TaskStatus`, которых нет в models/session. |

### Два стиля импортов (конфликт)

| Стиль | Где используется | Пример |
|-------|------------------|--------|
| **Абсолютный** `manager.src.*` / `webui.*` | `manager/src/**`, `webui/**` | `from manager.src.db import models` |
| **sys.path.insert** | Корневые скрипты, `test_collector.py` | `sys.path.insert(0, "manager/src")` → `from db.session import ...` |
| **Short path** `core.*` / `utils.*` | `scanner/core/**`, `scanner/classifiers/**` | `from core.base import FileContext` |

---

## 11. Структура файлов WebUI (для полноты)

```
webui/
├── main.py                    # ENTRY POINT: Jinja2 routes (7 страниц + API)
├── config.py                  # WEBUI_HOST, WEBUI_PORT, DEBUG, DATABASE_URL
├── run_webui.py               # ⚠️ Дубликат корневого
├── __init__.py
├── api/
│   ├── routes.py              # REST API (GET/POST)
│   └── schemas.py             # Pydantic-модели (частично не используются)
├── templates/                 # Jinja2 шаблоны
│   ├── base.html
│   ├── dashboard.html
│   ├── resources.html
│   ├── findings.html
│   ├── scanners.html
│   ├── catalog.html
│   ├── audit.html
│   └── access.html
└── static/
    ├── css/
    │   ├── variables.css
    │   ├── main.css
    │   ├── theme-dark.css
    │   └── components/ (7 файлов)
    ├── js/
    │   ├── api.js
    │   ├── main.js
    │   ├── theme.js
    │   └── dashboard.js
    └── vendor/
        ├── css/ (bootstrap.min.css, fontawesome.min.css)
        ├── js/ (chart.umd.min.js)
        └── webfonts/ (6 файлов)
```

---

## 12. Итого: что использовать при очистке

### Безусловно удалить (13 файлов)
```
scanner/core/test_source.py
scanner/core/dispatcher.py
scanner/core/config_manager.py
scanner/core/resource_manager.py
scanner/core/memory_profiler.py
scanner/utils/ocr_pool.py
scanner/utils/safe_ocr_worker.py
scanner/classifiers/model_worker.py
scanner/src/offline/detector.py
scanner/src/offline/sync.py
shared/event_schema.py
audit-agent-linux/heartbeat.py
manager/src/core/scheduler.py
```

### Удалить (дубликаты, легаси) (5 файлов)
```
webui/run_webui.py
state.json (корень)
dcap.db (корень)
structure.txt
Makefile
```

### Оставить, но отметить как legasy/placeholder (4 файла)
```
scanner/connectors/s3_connector.py        — v3.0 placeholder
manager/connectors/permissions/remote.py  — заглушка
scanner/src/modes/*.py                    — альтернативная архитектура (рефакторинг)
scanner/src/offline/queue.py, storage.py  — используются modes/
```

### Тестовые скрипты (оставить, не мёртвый код) (8 файлов)
```
init_db_data.py, fix_db.py, test_models.py, test_parse.py, test_access_management.py
manager/connectors/permissions/test_collector.py
tests/integration/*.py (pytest-заготовки)
```
