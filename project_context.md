markdown
# PROJECT_CONTEXT.md — DCAP System

**Обновлено:** 09.09.2026  
**Версия:** v3.3.0  
**Статус:** 🟢 Релиз v3.0.0 — завершающая стадия

---

## 🏗️ АРХИТЕКТУРА ПРОЕКТА

### Компоненты
dcap-system/
├── manager/ # FastAPI :8000 (control-plane)
│ └── src/
│ ├── main.py # точка входа
│ ├── api/ # resources, tasks, findings, catalog, scanner, permissions, audit, auth, retention, webui
│ ├── auth/ # JWT, AD, RBAC (День 30, 33)
│ ├── core/ # security (mTLS), secrets
│ ├── retention/ # архивация и очистка данных (День 35)
│ ├── connectors/
│ │ ├── permissions/ # local/ad/mixed (День 33)
│ │ └── audit/ # windows_audit
│ ├── services/ # access_service, access_config
│ ├── db/ # models.py, session.py, init_roles.py
│ └── workers/ # Celery задачи (День 36-37)
├── scanner/ # тяжелый агент сканирования
│ ├── src/
│ │ ├── managed_scanner.py
│ │ ├── core/ # orchestrator, state_manager, metrics
│ │ ├── classifiers/ # PII, Credentials, Code (с OCR)
│ │ │ └── credentials_classifier.py # + FP-фильтры (День 34.5)
│ │ ├── connectors/
│ │ │ └── filesystem.py # + расширенные типы, буферизация (День 34.5)
│ │ └── handlers/
│ │ └── finding_collector.py # + текстовый лог-отчёт (День 34.5)
│ └── config/scanner_config.json # + strict_filter, min_entropy и др.
├── audit-agent-windows/ # Windows-агент (легкий)
│ ├── main.py, collector.py, buffer.py, sender.py
│ ├── service.py # Windows-служба
│ └── config.json
├── audit-agent-linux/ # Linux-агент (inotify)
│ ├── main.py, collector.py, buffer.py, sender.py, heartbeat.py
│ ├── service/ # systemd unit, install.sh, install_cron.sh
│ └── start.sh, stop.sh, status.sh
├── audit-agent-s3/ # S3/MinIO агент (v3.0.0)
│ ├── src/ # main, collector, buffer, sender, converters, heartbeat, state
│ ├── config/ # config.json
│ ├── scripts/ # start.sh, stop.sh, status.sh, restart.sh
│ └── tests/ # unit + integration
├── webui/ # каноничный UI :8001
│ ├── src/
│ │ ├── main.py # FastAPI приложение (Jinja2)
│ │ ├── api/ # routes.py (прокси в Manager)
│ │ └── static/ # CSS, JS, vendor
│ ├── templates/ # Jinja2 шаблоны (День 28, 33)
│ │ ├── base.html
│ │ ├── dashboard.html
│ │ ├── login.html
│ │ ├── users.html, roles.html, settings.html (RBAC, День 33)
│ │ └── ...
│ └── config/config.json
├── shared/
│ ├── event_schema.py # UnifiedEvent (Pydantic)
│ ├── cert_utils.py # утилиты для сертификатов (День 34)
│ └── security.py # константы безопасности (День 34)
├── scripts/
│ ├── generate_certs.py # генерация сертификатов (День 34)
│ ├── rotate_certs.py # ротация сертификатов (День 34)
│ ├── migrate_sqlite_to_postgres.py # миграция данных (День 36)
│ └── init_ad_test_data.py # тестовые AD данные (День 33)
├── tests/
│ ├── e2e/ # E2E тесты
│ ├── chaos/ # Chaos тесты (отказоустойчивость)
│ └── load/ # Нагрузочное тестирование
├── docs/
│ ├── security_checklist.md # чеклист безопасности (День 34)
│ └── deployment.md # инструкции по развертыванию
├── docker-compose.yml # полный стек (День 36-38)
├── docker-compose.ad.yml # AD тестовый стенд (День 33)
├── SECURITY.md # политика безопасности (День 34)
├── AGENTS.md # инструкции для LLM
├── README.md # описание проекта
├── project_plan.md # план развития
└── project_context.md # этот файл

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
Архивные таблицы (День 35)
Таблица	Назначение
audit_logs_archive	Архив аудит-событий (TTL 90 дней)
findings_archive	Архив находок (TTL 180 дней)
audit_logs_archive очищается через 365 дней	
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
Архивация (retention/router.py)
Метод	Эндпоинт	Назначение
GET	/api/retention/policies	Получение политик хранения
POST	/api/retention/run	Ручной запуск архивации
GET	/api/retention/status	Статус последней архивации
POST	/api/retention/export	Экспорт архивных данных
📋 СТАТУС ВЫПОЛНЕНИЯ (ОБНОВЛЕННЫЙ)
Блок	Задач	Выполнено	Прогресс
Базовый функционал	8	8	██████████ 100%
Управление доступом	7	7	██████████ 100%
Аудит Windows	6	6	██████████ 100%
Аудит Linux	5	5	██████████ 100%
Enterprise Ready	6	6	██████████ 100%
S3/MinIO	2	2	██████████ 100%
AD интеграция + RBAC	1	1	██████████ 100%
Безопасность	1	1	██████████ 100%
Архивация	1	1	██████████ 100%
Secret Scanner	1	1	██████████ 100%
Масштабирование	2	0	░░░░░░░░░░ 0%
Деплой + Мониторинг	2	0	░░░░░░░░░░ 0%
Тестирование	2	0	░░░░░░░░░░ 0%
GitHub + Релиз	2	0	░░░░░░░░░░ 0%
Итого	49	42	86%
⚠️ ОГРАНИЧЕНИЯ И ИЗВЕСТНЫЕ ПРОБЛЕМЫ
Текущие ограничения
Ограничение	Описание	План
Active Directory	ad.py — заглушка, полная реализация в День 33	✅ Выполнено
Аудит Windows	wevtutil, требует прав администратора	✅ Работает
Аудит Linux	watchdog (inotify), работает без root	✅ Работает
SQLite	Используется для разработки	⚠️ Замена на PostgreSQL — День 36
Celery	Отсутствует	⚠️ Добавление — День 36-37
Агентская аутентификация	mTLS реализован, JWT для машин — TODO	📋 День 36-37
Снятые ограничения (v3.0.0)
Ограничение	Статус	Решение
Нет аутентификации	✅	JWT + AD + RBAC
Нет mTLS	✅	Полная реализация
Нет архивации	✅	Автоматическая очистка
Нет S3/MinIO агента	✅	Полноценный агент
Нет AD интеграции	✅	LDAP, SID → имя
Нет FP-фильтров в сканере	✅	Secret Scanner интеграция
🗓️ ПЛАН ПО ВЕРСИЯМ
Версия	Статус	Описание
v1.0.0	✅	Базовая DCAP (обнаружение + классификация + каталог)
v2.0.0	✅	Управление доступом + Аудит Windows (ядро)
v2.0.1	✅	Windows-стек полностью готов
v2.1.0	✅	Linux-агент + унифицированный формат + WebUI фильтр
v3.0.0	🔄	S3/MinIO, Enterprise Ready, Secret Scanner, масштабирование, контейнеризация, мониторинг, GitHub, релиз
v3.1.0	📋	DLP/ICAP, SMB-сканер, Webhook, облака, распределенная система
📝 КЛЮЧЕВЫЕ РЕШЕНИЯ
Архитектурные
Решение	Обоснование
Гибридная аутентификация	Поддержка local + AD, плавный переход в enterprise
mTLS relaxed/strict	Обратная совместимость с dev-средой
Secret Scanner интеграция	FP-фильтры, расширенные типы, производительность
Архивация без Celery	Celery отсутствует, фоновый поток
Rust → Python IPC	Производительность + сохранение Python-стекa
Технические
Решение	Обоснование
PostgreSQL + Redis в Docker	Production-готовность, масштабируемость
Docker Secrets	Безопасное хранение секретов
Единый формат событий	Унификация всех источников
Текстовый лог-отчёт	Безопасный для выкладки
Актуально на: 09.09.2026
Версия: v3.3.0
Следующий шаг: День 36-37 — Масштабирование (PostgreSQL, Redis, Celery)