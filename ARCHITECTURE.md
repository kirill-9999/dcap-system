markdown
# 🏗️ ARCHITECTURE.md — Архитектура DCAP

> **Обновляется архитектором при изменениях архитектуры.**
> Текущее состояние — в `STATE.md`. План и бэклог — в `ROADMAP.md`.

**Обновлено:** 11.09.2026
**Версия архитектуры:** v3.7.0

---

## 🏗️ СТРУКТУРА ПРОЕКТА
dcap-system/
├── manager/ # FastAPI :8000 (control-plane)
│ └── src/
│ ├── main.py # точка входа
│ ├── api/ # resources, tasks, findings, catalog, scanner,
│ │ # permissions, audit, auth, retention, webui
│ ├── auth/ # JWT, AD, RBAC (День 30, 33)
│ ├── core/ # security (mTLS), secrets, rate_limit
│ ├── retention/ # архивация и очистка данных (День 35)
│ ├── connectors/
│ │ ├── permissions/ # local/ad/mixed (День 33)
│ │ └── audit/ # windows_audit
│ ├── services/ # access_service, access_config
│ ├── db/ # models.py, session.py, init_roles.py
│ │ └── migrations/ # Alembic (env.py, versions/)
│ ├── cache/ # redis_client.py (кэш/rate-limit, fail-open)
│ ├── workers/ # Celery app/tasks/beat (День 36-37)
│ └── metrics.py # Prometheus (День 39)
│
├── scanner/ # Python-сканер (тяжёлый, на хосте)
│ └── src/
│ ├── managed_scanner.py
│ ├── heartbeat.py # HeartbeatThread (День 39)
│ ├── metrics.py # Prometheus :9101 (День 39)
│ ├── core/ # orchestrator, state_manager, metrics
│ ├── classifiers/ # PII, Credentials, Code (с OCR)
│ ├── connectors/ # filesystem.py
│ └── handlers/ # finding_collector.py
│
├── scanner-rust/ # 🆕 v3.1.0: Rust-ядро (BACKLOG-036)
│ ├── Cargo.toml
│ └── src/
│ ├── main.rs
│ ├── walker.rs # обход ФС (local + CIFS + NFS)
│ ├── prefilter.rs # regex-префильтр
│ ├── entropy.rs # entropy-анализ
│ ├── bridge/ipc.rs # JSON-RPC к Python sidecar
│ ├── cifs.rs # pavao + libsmbclient
│ ├── nfs.rs # nfs-rs (авто-монтирование)
│ ├── heartbeat.rs # HTTP heartbeat
│ ├── metrics.rs # Prometheus :9101
│ └── reporter.rs # отправка в Manager
│
├── scanner-python/ # 🆕 v3.1.0: Python sidecar (BACKLOG-036)
│ ├── src/
│ │ ├── sidecar.py # IPC-сервер (JSON-RPC)
│ │ ├── ocr.py # Tesseract wrapper
│ │ ├── pii.py # Presidio wrapper
│ │ ├── credentials.py # (fallback)
│ │ └── code.py # (fallback)
│ ├── vendor/
│ │ └── tesseract/ # portable Tesseract (Windows)
│ └── requirements.txt
│
├── audit-agent-windows/ # Windows-агент (лёгкий)
│ ├── main.py, collector.py, buffer.py, sender.py
│ ├── service.py # Windows-служба
│ └── config.json
│
├── audit-agent-linux/ # Linux-агент (inotify)
│ ├── main.py, collector.py, buffer.py, sender.py, heartbeat.py
│ ├── metrics.py # Prometheus :9102 (День 39)
│ ├── service/ # systemd unit, install.sh
│ └── start.sh, stop.sh, status.sh
│
├── audit-agent-s3/ # S3/MinIO агент (v3.0.0)
│ ├── src/ # main, collector, buffer, sender,
│ │ # converters, heartbeat, state, metrics
│ ├── config/ # config.json
│ ├── scripts/ # start.sh, stop.sh, status.sh, restart.sh
│ └── tests/ # unit + integration + load
│
├── webui/ # каноничный UI :8001
│ ├── src/
│ │ ├── main.py # FastAPI приложение (Jinja2)
│ │ ├── api/ # routes.py (прокси в Manager)
│ │ └── static/ # CSS, JS, vendor
│ ├── templates/ # Jinja2 шаблоны
│ └── config/config.json
│
├── shared/
│ ├── event_schema.py # UnifiedEvent (Pydantic)
│ ├── cert_utils.py # утилиты для сертификатов
│ └── security.py # константы безопасности
│
├── scripts/
│ ├── generate_certs.py # генерация сертификатов
│ ├── rotate_certs.py # ротация сертификатов
│ ├── migrate_sqlite_to_postgres.py # миграция данных
│ ├── deploy.sh, stop.sh, logs.sh, status.sh, healthcheck.sh
│ ├── monitoring-status.sh # статус мониторинга (День 39)
│ └── init_ad_test_data.py # тестовые AD данные
│
├── monitoring/ # Prometheus/Grafana/Alertmanager (День 39)
│ ├── prometheus/
│ │ ├── prometheus.yml
│ │ └── alerts.yml
│ ├── alertmanager/
│ │ └── alertmanager.yml
│ └── grafana/
│ └── provisioning/
│ ├── datasources/prometheus.yml
│ └── dashboards/
│ ├── dashboards.yml
│ ├── dcap-overview.json
│ └── dcap-scanner.json
│
├── tests/
│ ├── e2e/ # E2E тесты
│ ├── chaos/ # Chaos тесты
│ └── load/ # Нагрузочное тестирование
│
├── docs/
│ ├── deployment.md # инструкции по развертыванию
│ ├── monitoring.md # мониторинг (День 39)
│ └── security_checklist.md # чеклист безопасности
│
├── alembic.ini # Alembic
├── docker-compose.yml # полный стек
├── docker-compose.prod.yml # production overrides
├── docker-compose.ad.yml # AD тестовый стенд
├── SECURITY.md # политика безопасности
├── STATE.md # 🆕 текущее состояние (обновляет кодер)
├── ROADMAP.md # 🆕 план + бэклог
├── ARCHITECTURE.md # 🆕 этот файл
├── AGENTS.md # инструкции для LLM
├── README.md # описание проекта
└── (удалены: project_plan.md, project_context.md)

text

---

## 🔐 АУТЕНТИФИКАЦИЯ И БЕЗОПАСНОСТЬ

### Режимы аутентификации (День 30, 33)

| Режим | Описание |
|-------|----------|
| **local** | JWT + Bcrypt, встроенные пользователи (разработка) |
| **hybrid** | SPNEGO → fallback JWT (тестирование) |
| **windows_integrated** | Только SPNEGO (production AD) |

### Ролевая модель (День 33)

| Роль | Описание | AD группа |
|------|----------|-----------|
| **Admin** | Полный доступ | DCAP_Admins |
| **Auditor** | Аудит и мониторинг | DCAP_Auditors |
| **Scanner** | Запуск сканирования | DCAP_Scanners |
| **Viewer** | Только чтение | (все остальные) |

### mTLS (День 34)

- **relaxed** — если сертификаты не найдены, работает на plain HTTP
- **strict** — Manager не стартует без PKI
- Поддерживается во всех компонентах (Manager, WebUI, агенты, сканер)
- CRL для отзыва сертификатов

---

## 📊 СБОР ПРАВ ДОСТУПА

### Способы сбора

| Способ | Компонент | Источник |
|--------|-----------|----------|
| **Local** | LocalConnector | icacls (Windows), getfacl (Linux) |
| **AD** | ADConnector | LDAP, разрешение SID → имя |
| **Агенты** | Audit Agent (Windows/Linux) | win32security, getfacl |
| **Scanner** | Scanner (fallback) | LocalConnector |

### API

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| POST | `/api/audit/permissions` | Прием прав от агента |
| GET | `/api/permissions/resources/{id}` | Получение прав для ресурса |
| GET | `/api/permissions/resolve/{sid}` | Разрешение SID → имя |

---

## 🗄️ МОДЕЛИ БД (ОСНОВНЫЕ)

### User (auth/models.py)

```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(200), nullable=True)  # null для AD
    domain_user = Column(String(200), nullable=True)    # DOMAIN\username
    auth_source = Column(String(20), default="local")   # local, ad
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    roles = relationship("Role", secondary=user_roles)
Role (auth/models.py)
python
class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)  # admin, auditor, scanner, viewer
    description = Column(String(200))
    ad_group = Column(String(100))  # маппинг AD группы
AccessEntry (db/models.py)
python
class AccessEntry(Base):
    __tablename__ = "access_entries"
    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"))
    principal = Column(String(200), nullable=False)      # DOMAIN\User
    principal_type = Column(String(20), nullable=False)  # user, group
    permissions = Column(JSON, nullable=False)           # ["read", "write", ...]
    is_inherited = Column(Boolean, default=False)
    source = Column(String(50), default="local")         # windows_agent, ad, scanner
    collected_at = Column(DateTime, default=datetime.utcnow)
ScanTask (db/models.py) — обновлено в День 39
python
class ScanTask(Base):
    __tablename__ = "scan_tasks"
    id = Column(Integer, primary_key=True)
    # ... (существующие поля)
    progress = Column(JSON, nullable=True)  # День 39: files_scanned/total/percent
Архивные таблицы (День 35)
Таблица	Назначение
audit_logs_archive	Архив аудит-событий (TTL 90 дней)
findings_archive	Архив находок (TTL 180 дней)
audit_logs_archive очищается через 365 дней.

🔌 API ЭНДПОИНТЫ
Аутентификация (auth/router.py)
Метод	Эндпоинт	Назначение
POST	/api/auth/login	Логин (local или AD)
POST	/api/auth/refresh	Обновление токена
POST	/api/auth/logout	Выход
GET	/api/auth/me	Информация о пользователе
GET	/api/auth/mode	Режим аутентификации
GET	/api/auth/users	Список пользователей (Admin)
POST	/api/auth/users	Создание пользователя (Admin)
PUT	/api/auth/users/{id}	Обновление пользователя (Admin)
DELETE	/api/auth/users/{id}	Удаление пользователя (Admin)
GET	/api/auth/roles	Список ролей (Admin)
POST	/api/auth/roles	Создание роли (Admin)
Сканер (api/scanner.py) — обновлено в День 39
Метод	Эндпоинт	Назначение
POST	/api/scanner/heartbeat	Heartbeat (scanner_id, task_id, progress)
POST	/api/scanner/tasks/{id}/results	Результаты задания
GET	/api/scanner/{id}	Статус сканера
GET	/api/scanners	Список сканеров
Метрики (main.py) — День 39
Метод	Эндпоинт	Назначение
GET	/metrics	Prometheus-метрики Manager (публичный, вне /api/*)
GET	/api/health	Healthcheck
Архивация (retention/router.py)
Метод	Эндпоинт	Назначение
GET	/api/retention/policies	Получение политик хранения
POST	/api/retention/run	Ручной запуск архивации
GET	/api/retention/status	Статус последней архивации
POST	/api/retention/export	Экспорт архивных данных
📈 МОНИТОРИНГ (День 39)
Метрики
Компонент	Порт	Ключевые метрики
Manager	:8000/metrics	dcap_http_*, dcap_tasks_total, dcap_findings_total, dcap_scanner_*, dcap_celery_queue_size
Scanner	:9101	dcap_scanner_files_scanned_total, dcap_scanner_findings_total, dcap_scanner_errors_total
Linux-агент	:9102	dcap_linux_events_collected_total, dcap_linux_events_sent_total, dcap_linux_buffer_size
S3-агент	:9103	dcap_s3_events_collected_total, dcap_s3_events_sent_total, dcap_s3_buffer_size
Celery	:9808	(celery-exporter)
PostgreSQL	:9187	(postgres-exporter)
Redis	:9121	(redis-exporter)
Heartbeat-thread (День 39)
scanner/src/heartbeat.py — daemon-поток, interval 30 c, fail-open

POST /api/scanner/heartbeat с {scanner_id, status, current_task_id, progress}

Manager _mark_stale_scanners не трогает сканеры с активным заданием

ProgressPoller читает state.json каждые 15 c, шлёт прогресс

Алерты (alerts.yml)
Алерт	Условие	Severity
ScannerInactive	dcap_scanner_heartbeat_age_seconds > 120	warning
TaskFailed	increase(dcap_tasks_total{status="failed"}[5m]) > 0	critical
HighErrorRate	rate(dcap_http_requests_total{status=~"5.."}[5m]) > 0.05	critical
CeleryQueueBacklog	dcap_celery_queue_size > 100	warning
📝 КЛЮЧЕВЫЕ РЕШЕНИЯ
Архитектурные
Решение	Обоснование
Гибридная аутентификация	Поддержка local + AD, плавный переход в enterprise
mTLS relaxed/strict	Обратная совместимость с dev-средой
Secret Scanner интеграция	FP-фильтры, расширенные типы, производительность
Масштабирование (PG/Redis/Celery)	Celery Beat вместо фоновых потоков, партиционированные audit_logs
Scanner на хосте (не Docker)	Docker не может динамически монтировать пути из заданий
Heartbeat-thread (v3.7.0)	Отдельный поток — сканер не «inactive» при долгих заданиях
Rust Scanner (v3.1.0)	IPC (JSON-RPC), CIFS через pavao, NFS через nfs-rs
Rust → Python IPC	Производительность + сохранение Python-стека (Tesseract/Presidio)
Технические
Решение	Обоснование
PostgreSQL + Redis в Docker	Production-готовность, масштабируемость
Docker Secrets	Безопасное хранение секретов
Единый формат событий (UnifiedEvent)	Унификация всех источников
Текстовый лог-отчёт	Безопасный для выкладки
Prometheus + Grafana + Alertmanager	Стандартный стек мониторинга
spaCy-модели sm	Жёстко зашито в pii_classifier, lg не используется
spnego убран из requirements	Пакета нет на PyPI, реальный — pyspnego
⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ
Ограничение	Описание	План
Агентская аутентификация	mTLS реализован, JWT для машин — TODO	API-ключи для агентов (v3.0.0)
/metrics публичный	Нет JWT/basic_auth	BACKLOG-044 (production)
Прогресс сканера	Не виден в WebUI	BACKLOG-043
NOT NULL поля	Возможны скрытые баги в приёмных эндпоинтах	BACKLOG-039
NFS на Windows	Ограниченный клиент (если не через nfs-rs)	Решено в nfs-rs (v3.1.0)
Параллельный батч-сканер	Форк один (OCRWorker)	BACKLOG-040 (v3.1.0)
Актуально на: 11.09.2026
Версия архитектуры: v3.7.0