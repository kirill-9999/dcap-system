# PROJECT_CONTEXT.md — DCAP System
**Обновлено:** 2026-08-14
**Версия:** v2.0.0-alpha
**Статус:** 🚧 Разработка модуля управления доступом (Дни 9-15): Дни 9-14 ✅, День 15 (тестирование) впереди

---

## 🏗️ АРХИТЕКТУРА ПРОЕКТА

### Компоненты
```
dcap-system/
├── manager/                    # Manager (control-plane): FastAPI :8000
│   ├── src/
│   │   ├── main.py             # FastAPI app, раздаёт WebUI static + /api/*
│   │   ├── api/                # REST-роутеры
│   │   │   ├── resources.py    # /api/resources ✅
│   │   │   ├── tasks.py        # /api/tasks ✅
│   │   │   ├── findings.py     # /api/findings ✅
│   │   │   ├── catalog.py      # /api/catalog ✅
│   │   │   ├── scanner.py      # /api/scanner ✅
│   │   │   └── permissions.py  # /api/permissions/* ✅ (День 13)
│   │   ├── connectors/permissions/   # коллекторы прав, паттерн Strategy ✅ (День 10)
│   │   │   ├── base.py         # базовый интерфейс коллектора
│   │   │   ├── local.py        # icacls / net localgroup (Windows)
│   │   │   ├── remote.py       # сбор прав удалённо (через Scanner)
│   │   │   ├── ad.py           # заглушка для будущего AD
│   │   │   ├── factory.py      # фабрика коллекторов по режиму
│   │   │   └── test_collector.py
│   │   ├── services/
│   │   │   ├── access_service.py   # синхронизация, анализ, алерты ✅ (Дни 11-12)
│   │   │   └── access_config.py    # конфигурация режимов сбора прав
│   │   ├── core/
│   │   │   └── scheduler.py    # фоновый планировщик заданий
│   │   ├── db/
│   │   │   ├── models.py       # ✅ базовые модели + Access* (День 9)
│   │   │   ├── session.py      # ✅ SQLite: manager/dcap.db
│   │   │   └── migrations/     # SQL-миграции, run_migration.py
│   │   └── proto_gen/          # gRPC-стабы (остался только __pycache__)
│   └── tests/                  # пусто
├── scanner/                    # агент сканирования
│   ├── src/
│   │   ├── managed_scanner.py  # ✅ REST-клиент Manager
│   │   ├── config_loader.py    # загрузка scanner/config/scanner_config.json
│   │   ├── modes/              # standalone / managed / hybrid
│   │   └── offline/            # offline-режим: очередь, хранение, синхронизация
│   ├── core/                   # orchestrator, dispatcher, state/memory/resource менеджеры ✅
│   ├── classifiers/            # ✅ PII, Credentials, Code + OCR-воркеры
│   ├── connectors/             # filesystem, S3
│   ├── handlers/               # finding_collector.py
│   ├── utils/                  # document_extractor, file_hasher, OCR
│   ├── config/scanner_config.json
│   └── state/state.json
├── webui/                      # дашборд
│   ├── main.py                 # ✅ актуальный WebUI (весь HTML инлайн в Python)
│   ├── api/                    # routes.py (читает БД напрямую) + /api/access/* (День 14), schemas.py
│   ├── static/                 # index.html, css/, js/
│   ├── templates/              # устаревшие Jinja-шаблоны
│   ├── run_webui.py            # запуск webui.main:app на :8001
│   ├── main_final.py / main_simple.py / main_static.py   # ❌ устаревшие эксперименты
│   └── config.py               # настройки WebUI (порт, БД)
├── catalog/                    # каталог папок (folders_catalog.jsonl)
├── test_files/                 # тестовые данные (PII: docx/pdf/txt/png/xlsx)
├── logs/                       # журналы failed_files (JSONL)
├── prompts/                    # ТЗ/отчёты по дням, шаблоны
├── init_db.py                  # инициализация БД (создаёт manager/dcap.db)
├── init_db_data.py, fix_db.py  # утилиты БД
├── run_scanner.py              # запуск сканера
├── test_models.py, test_parse.py   # тестовые скрипты
├── Makefile                    # ⚠️ фикция: требует docker-compose.yml, которого нет
└── structure.txt               # ⚠️ устарел (пути services/collectors/ уже нет)
```

---

## 📋 ВЕРСИИ И СТАТУС

| Версия | Статус | Описание |
|--------|--------|----------|
| **v1.0.0** | ✅ **ГОТОВА** | Базовая DCAP (обнаружение + классификация + каталог) |
| **v2.0.0-alpha** | 🚧 **В РАЗРАБОТКЕ** | Модуль управления доступом (Дни 9-15) |
| **v2.0.0-beta** | ⚪ ПЛАНИРУЕТСЯ | Аудит и журналирование (Дни 16-22) |
| **v2.1.0** | ⚪ ПЛАНИРУЕТСЯ | Распределенная система (Дни 23-34) |
| **v3.0.0** | ⚪ ПЛАНИРУЕТСЯ | Промышленная DCAP (Дни 35-49) |

---

## 🗄️ МОДЕЛИ БД (manager/src/db/models.py)

### Существующие таблицы

| Таблица | Назначение | Статус |
|---------|-----------|--------|
| `resources` | Источники данных (+ поля управления доступом) | ✅ |
| `scanners` | Зарегистрированные сканеры | ✅ |
| `scan_tasks` | Задания на сканирование | ✅ |
| `findings` | Находки (PII, Credentials, Code) | ✅ |
| `catalog_entries` | Каталог папок с метками | ✅ |
| `failed_files` | Файлы с ошибками | ✅ |
| `schedules` | Расписания сканирования | ✅ |
| `access_entries` | Записи прав доступа к ресурсам | ✅ (День 9) |
| `permission_changes` | История изменений прав | ✅ (День 9) |
| `access_alerts` | Алерты по доступам | ✅ (День 9) |

### Resource — расширение под управление доступом (День 9, реализовано)

```python
# manager/src/db/models.py

class Resource(Base):
    __tablename__ = "resources"
    # Базовые поля
    id = Column(Integer, primary_key=True)
    path = Column(String(500), nullable=False, unique=True)
    type = Column(String(50), default="FILESYSTEM")
    status = Column(String(20), default="ACTIVE")
    last_scanned_at = Column(DateTime, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scan_config = Column(JSON, nullable=True)
    scan_interval = Column(Integer, default=3600)
    schedule_enabled = Column(Boolean, default=False)
    cron_expression = Column(String(100), nullable=True)

    # ✅ Поля управления доступом (День 9)
    owner = Column(String(200), nullable=True)              # DOMAIN\User или LOCAL\User
    owner_sid = Column(String(100), nullable=True)          # SID владельца
    permissions = Column(JSON, default={})                  # {"user": "read", "group": "write"}
    permission_last_synced = Column(DateTime, nullable=True)
    is_sensitive = Column(Boolean, default=False)
    classification_level = Column(String(20), default="public")  # public/internal/confidential/restricted
    permission_source = Column(String(50), default="local")      # local / ad / custom
    domain = Column(String(100), nullable=True)

    # Связи
    access_entries    = relationship("AccessEntry",    back_populates="resource", cascade="all, delete-orphan")
    permission_changes = relationship("PermissionChange", back_populates="resource", cascade="all, delete-orphan")
    access_alerts     = relationship("AccessAlert",    back_populates="resource", cascade="all, delete-orphan")
```

Дополнительно реализованы модели `AccessEntry`, `PermissionChange`, `AccessAlert` (см. `manager/src/db/models.py`, строки ~176-354).

---

## 🔌 ИНТЕРФЕЙСЫ

### REST API (Manager :8000)

#### Базовые эндпоинты (✅ ГОТОВЫ)

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| GET | `/api/health` | Проверка здоровья |
| GET | `/api/resources` | Список ресурсов |
| POST | `/api/resources` | Создать ресурс |
| DELETE | `/api/resources/{id}` | Удалить ресурс |
| POST | `/api/resources/{id}/scan` | Запустить сканирование |
| GET | `/api/resources/{id}/config` | Получить конфиг |
| PUT | `/api/resources/{id}/config` | Обновить конфиг |
| GET | `/api/tasks` | Список заданий |
| GET | `/api/tasks/{id}` | Детали задания |
| DELETE | `/api/tasks/{id}` | Удалить задание |
| GET | `/api/findings` | Список находок |
| GET | `/api/findings/{id}` | Находка |
| DELETE | `/api/findings/{id}` | Удалить находку |
| GET | `/api/findings/stats` | Статистика находок |
| GET | `/api/catalog` | Каталог папок |
| GET | `/api/catalog/tree` | Дерево папок |
| GET | `/api/catalog/stats` | Статистика каталога |
| GET | `/api/catalog/search` | Поиск по каталогу |

#### Scanner API (✅ ГОТОВЫ)

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| POST | `/api/scanner/register` | Регистрация сканера |
| POST | `/api/scanner/heartbeat` | Heartbeat |
| GET | `/api/scanner/tasks/pending` | Получить задание |
| POST | `/api/scanner/tasks/{id}/results` | Отправить результаты |
| GET | `/api/scanner/tasks/assigned` | Назначенные задания |
| POST | `/api/scanner/tasks/{id}/release` | Освободить задание |
| GET | `/api/scanner/{id}` | Информация о сканере |

#### Permissions API (✅ РЕАЛИЗОВАН — День 13)

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| GET | `/api/permissions/mode` | Текущий режим сбора прав |
| POST | `/api/permissions/mode` | Установить режим (local/remote) |
| POST | `/api/permissions/sync` | Синхронизировать права |
| GET | `/api/permissions/resources/{id}` | Права доступа к ресурсу |
| GET | `/api/permissions/resources/{id}/effective` | Эффективные права |
| GET | `/api/permissions/resources/{id}/excessive` | Избыточные права |
| GET | `/api/permissions/resources/{id}/inheritance` | Анализ наследования |
| GET | `/api/permissions/resources/{id}/report` | Полный отчет |
| GET | `/api/permissions/resources/{id}/trends` | Тренды прав |
| GET | `/api/permissions/alerts` | Алерты по доступам |
| GET | `/api/permissions/alerts/stats` | Статистика алертов |
| PUT | `/api/permissions/alerts/{id}` | Обновить статус алерта |
| POST | `/api/permissions/alerts/{id}/generate` | Сгенерировать алерты вручную |

---

## 🎯 ТЕКУЩАЯ ЗАДАЧА (ДНИ 9-15)

**Цель:** реализовать модуль управления доступом (Access Management) для DCAP-системы.

| День | Задача | Описание | Статус |
|------|--------|----------|--------|
| День 9 | Модель данных | AccessEntry, AccessAlert, PermissionChange, расширение Resource | ✅ |
| День 10 | Коннектор прав | LocalPermissionCollector (icacls, net user), remote, ad-заглушка, factory | ✅ |
| Дни 11-12 | Сервис | AccessService (синхронизация, анализ, алерты) | ✅ |
| День 13 | API | Эндпоинты /api/permissions/* | ✅ |
| День 14 | WebUI | Страница «Управление доступом» (таблица прав, фильтры, алерты) | ✅ |
| День 15 | Тестирование | Проверка всех сценариев | ⚪ ВПЕРЕДИ |

---

## ⚠️ ВАЖНЫЕ ОГРАНИЧЕНИЯ

- Нет Active Directory — разработка ведется на Windows 10 без AD
- Архитектура должна быть расширяемой — возможность добавить AD в будущем
- Паттерн Strategy — для коллекторов прав доступа
- Локальные пользователи/группы — через `net user` и `net localgroup`, права — через `icacls`
