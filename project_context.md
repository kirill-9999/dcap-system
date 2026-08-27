arkdown
# PROJECT_CONTEXT.md — DCAP System
**Обновлено:** 2026-08-27
**Версия:** v2.1.0
**Статус:** ✅ Windows + Linux аудит готов

---

## 🏗️ АРХИТЕКТУРА ПРОЕКТА

### Компоненты
dcap-system/
├── manager/ # Manager (control-plane): FastAPI :8000
│ └── src/
│ ├── main.py # точка входа
│ ├── api/
│ │ ├── resources.py # /api/resources
│ │ ├── tasks.py # /api/tasks
│ │ ├── findings.py # /api/findings
│ │ ├── catalog.py # /api/catalog
│ │ ├── scanner.py # /api/scanner
│ │ ├── permissions.py # /api/permissions/*
│ │ └── audit.py # /api/audit/*
│ ├── connectors/
│ │ ├── permissions/ # коллекторы прав (local/remote/ad)
│ │ └── audit/ # чтение Security Log (wevtutil)
│ ├── services/
│ │ ├── access_service.py
│ │ └── access_config.py
│ └── db/
│ ├── models.py # + AuditAgent, AuditLog
│ └── session.py
├── scanner/ # агент сканирования (тяжелый)
├── audit-agent-windows/ # легкий агент аудита (Windows)
│ ├── main.py # точка входа (цикл)
│ ├── collector.py # wevtutil Security Log, XML-парсинг
│ ├── buffer.py # SQLite-буфер
│ ├── sender.py / heartbeat.py # HTTP в Manager
│ ├── config_loader.py # конфиг с дефолтами
│ ├── service.py # Windows-служба (pywin32)
│ └── config.json # конфигурация
├── audit-agent-linux/ # легкий агент аудита (Linux)
│ ├── main.py # точка входа
│ ├── collector.py # watchdog (inotify), SSH-события
│ ├── buffer.py # SQLite-буфер
│ ├── sender.py / heartbeat.py # HTTP в Manager
│ ├── config_loader.py # конфиг с дефолтами
│ ├── config.json # конфигурация
│ ├── start.sh # запуск (daemon/console/test)
│ └── dcap-audit.service # systemd-сервис
├── shared/
│ └── event_schema.py # единая Pydantic-схема UnifiedEvent
├── webui/ # дашборд (каноничный, инлайн в main.py)
│ ├── main.py # актуальный WebUI (:8001)
│ ├── run_webui.py — точка входа (в корне репо)
│ ├── static/vendor/ # локальные bootstrap/fontawesome/chart.js
│ └── api/ # routes.py, schemas.py
├── test_files/ # тестовые данные
└── prompts/ # ТЗ и отчеты по дням

text

### Аудит (Audit)

Система аудита состоит из:
1. **Агентов сбора** — легкие компоненты на файловых серверах:
   - **Windows:** чтение Security Log через `wevtutil` (День 17)
   - **Linux:** мониторинг через watchdog/inotify + SSH-события (День 23-24)
   - **S3/MinIO:** планируется (BACKLOG-011, v3.0.0)
2. **Manager** — прием событий от агентов, хранение в `AuditLog`, анализ
3. **WebUI** — просмотр аудит-событий с фильтрацией по источнику

**Единый формат событий** (`shared/event_schema.py`) используется для всех источников.

---

## 🗄️ МОДЕЛИ БД

### AuditAgent

```python
class AuditAgent(Base):
    __tablename__ = "audit_agents"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    hostname = Column(String(200), nullable=False)
    ip_address = Column(String(45), nullable=True)
    status = Column(String(20), default="offline")
    version = Column(String(20), default="1.0.0")
    config = Column(JSON, default={...})
    last_heartbeat = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_error = Column(Text, nullable=True)
    events_sent = Column(Integer, default=0)
    events_failed = Column(Integer, default=0)
    last_event_at = Column(DateTime, nullable=True)
```

### AuditLog

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("audit_agents.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False)
    event_source = Column(String(50), default="agent")
    user = Column(String(200), nullable=True)
    user_sid = Column(String(100), nullable=True)
    file_path = Column(String(500), nullable=False)
    old_path = Column(String(500), nullable=True)
    source_host = Column(String(100), nullable=True)
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
```

---

## 🔌 API ЭНДПОИНТЫ

### Агенты аудита

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| POST | `/api/audit/agents/register` | Регистрация агента |
| POST | `/api/audit/agents/heartbeat` | Heartbeat агента |
| POST | `/api/audit/events` | Прием событий от агента |
| GET | `/api/audit` | Просмотр событий с фильтрацией (event_source, agent_id) |
| GET | `/api/audit/stats` | Статистика по аудиту (включая by_source) |
| GET | `/api/audit/agents` | Список агентов |
| DELETE | `/api/audit/agents/{id}` | Удаление агента |
| DELETE | `/api/scanner/{id}` | Удаление сканера |

### Единый формат событий (UnifiedEvent)

```python
class UnifiedEvent(BaseModel):
    event_type: str           # read, write, delete, move, rename
    event_source: str         # windows_agent, linux_agent, scanner, api
    user: Optional[str]
    user_sid: Optional[str]   # Windows-only
    file_path: str
    old_path: Optional[str]
    source_host: Optional[str]
    metadata: Dict[str, Any]
    timestamp: datetime
```

---

## ⚠️ ОГРАНИЧЕНИЯ ПЛАТФОРМЫ

- Нет Active Directory: `ad.py` — заглушка.
- Аудит Windows: wevtutil, требует прав администратора.
- Аудит Linux: watchdog (inotify), работает без root для мониторинга.
- SQLite + threading: всегда `check_same_thread=False`.
- CDN: антивирусы блокируют — статика локально в `webui/static/vendor/`.

---

## 🗓️ ПЛАН ПО ВЕРСИЯМ

| Версия | Статус | Описание |
|--------|--------|----------|
| v1.0.0 | ✅ | Базовая DCAP (обнаружение + классификация + каталог) |
| v2.0.0 | ✅ | Управление доступом + Аудит Windows (ядро) |
| v2.0.1 | ✅ | Windows-стек полностью готов |
| v2.1.0 | ✅ | Linux-агент + унифицированный формат + WebUI фильтр |
| v3.0.0 | 📋 | S3/MinIO + безопасность + масштабирование |
| v3.1.0 | 📋 | Распределенная система + архивы + мониторинг |

---

## 📊 СТАТУС ВЫПОЛНЕНИЯ

| Блок | Задач | Выполнено | Прогресс |
|------|-------|-----------|----------|
| Базовый функционал | 8 | 8 | ██████████ 100% |
| Управление доступом | 7 | 7 | ██████████ 100% |
| Аудит Windows | 6 | 6 | ██████████ 100% |
| Аудит Linux | 5 | 5 | ██████████ 100% |
| Интеграции | 4 | 0 | ░░░░░░░░░░ 0% |
| Масштабирование | 5 | 0 | ░░░░░░░░░░ 0% |
