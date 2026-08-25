arkdown
# PROJECT_CONTEXT.md — DCAP System
**Обновлено:** 2026-08-16
**Версия:** v2.0.1
**Статус:** ✅ Windows-стек полностью готов

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
│ │ ├── permissions.py # /api/permissions/* (Дни 9-13)
│ │ └── audit.py # /api/audit/* (День 16)
│ ├── connectors/
│ │ ├── permissions/ # коллекторы прав (local/remote/ad)
│ │ └── audit/ # чтение Security Log (wevtutil)
│ ├── services/
│ │ ├── access_service.py
│ │ └── access_config.py
│ └── db/
│ ├── models.py # + AuditAgent, AuditLog (День 16)
│ └── session.py
├── scanner/ # агент сканирования (тяжелый)
│ ├── src/
│ │ ├── managed_scanner.py
│ │ ├── core/ # orchestrator, state_manager, metrics
│ │ ├── classifiers/ # PII, Credentials, Code
│ │ └── connectors/ # filesystem, s3
│ └── config/
│ └── scanner_config.json
├── audit-agent/ # легкий агент аудита (День 17)
│ ├── main.py # точка входа
│ ├── config.json # конфигурация агента
│ ├── collector.py # чтение Security Log (wevtutil)
│ ├── buffer.py # SQLite-буфер
│ ├── sender.py # отправка в Manager
│ └── requirements.txt # requests
├── webui/ # дашборд (каноничный, инлайн в main.py)
│ ├── main.py # актуальный WebUI (:8001)
│ ├── run_webui.py — точка входа (в корне репо)
│ ├── static/vendor/ # локальные bootstrap/fontawesome/chart.js
│ └── api/ # routes.py, schemas.py
│
│ Легаси-файлы удалены (День 19.5): main_final/simple/static.py,
│ static/index*.html, static/js/*.js, static/css/*, templates/.
│ Manager на :8000 — чистое API, / редиректит на :8001.
├── test_files/ # тестовые данные (17 файлов)
├── prompts/ # ТЗ и отчеты по дням
│ ├── templates/
│ ├── tz/
│ ├── archive/
│ └── reports/
└── logs/ # журналы

text

### Аудит (Audit)

Система аудита состоит из:
1. **Агентов сбора** — легкие компоненты на файловых серверах:
   - **Windows:** чтение Security Log через `wevtutil` (реализовано, День 17)
   - **Linux:** чтение `auditd` (планируется, BACKLOG-007, v2.1.0)
   - **S3/MinIO:** чтение Server Access Logs (планируется, BACKLOG-008, v3.0.0)
2. **Manager** — прием событий от агентов, хранение в `AuditLog`, анализ
3. **WebUI** — просмотр аудит-событий

**Единый формат событий** используется для всех источников (BACKLOG-009).

---

## 🗄️ МОДЕЛИ БД

### AuditAgent (День 16)

```python
class AuditAgent(Base):
    __tablename__ = "audit_agents"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    hostname = Column(String(200), nullable=False)
    ip_address = Column(String(45), nullable=True)
    status = Column(String(20), default="offline")   # offline, online, error, updating
    version = Column(String(20), default="1.0.0")
    config = Column(JSON, default={
        "read_interval": 60,
        "batch_size": 100,
        "buffer_size": 10000,
        "event_filters": [],
        "paths": []
    })
    last_heartbeat = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_error = Column(Text, nullable=True)
    events_sent = Column(Integer, default=0)
    events_failed = Column(Integer, default=0)
    last_event_at = Column(DateTime, nullable=True)

    audit_logs = relationship("AuditLog", back_populates="agent")
AuditLog (День 16)
python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("audit_agents.id"), nullable=True, index=True)

    event_type = Column(String(50), nullable=False)      # read, write, delete, move, rename
    event_source = Column(String(50), default="agent")   # agent, scanner, api, system
    user = Column(String(200), nullable=True)
    user_sid = Column(String(100), nullable=True)
    file_path = Column(String(500), nullable=False)
    old_path = Column(String(500), nullable=True)
    source_host = Column(String(100), nullable=True)

    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    agent = relationship("AuditAgent", back_populates="audit_logs")
🔌 API ЭНДПОИНТЫ
Агенты аудита (День 16)
Метод	Эндпоинт	Назначение
POST	/api/audit/agents/register	Регистрация агента
POST	/api/audit/agents/heartbeat	Heartbeat агента
POST	/api/audit/events	Прием событий от агента
GET	/api/audit	Просмотр событий с фильтрацией
GET	/api/audit/stats	Статистика по аудиту
⚠️ ОГРАНИЧЕНИЯ ПЛАТФОРМЫ
Нет Active Directory: ad.py — заглушка, локальный сбор прав через icacls/net localgroup.

Аудит Windows: работает через wevtutil, требует прав администратора. На Windows 10 Home настройка через auditpol + SACL (без secpol.msc).

Агент аудита: легкий (~50 MB), без Tesseract/spaCy/Presidio.

🗓️ ПЛАН ПО ВЕРСИЯМ
Версия	Статус	Описание
v1.0.0	✅	Базовая DCAP (обнаружение + классификация + каталог)
v2.0.0	✅	Управление доступом (Дни 9-14) + Аудит Windows (Дни 16-17)
v2.0.1	✅	Windows-стек полностью готов (WebUI аудита, отчеты, тестирование)
v2.1.0	📋	Агент аудита для Linux + Унифицированный формат событий
v3.0.0	📋	Агент аудита для S3/MinIO + Webhook + Масштабирование
📊 СТАТУС ВЫПОЛНЕНИЯ
Блок	Задач	Выполнено	Прогресс
Базовый функционал	8	8	██████████ 100%
Управление доступом	7	7	██████████ 100%
Аудит (Windows)	2	2	██████████ 100%
Аудит (Linux)	3	0	░░░░░░░░░░ 0%
Интеграции	4	0	░░░░░░░░░░ 0%
Масштабирование	5	0	░░░░░░░░░░ 0%
text
