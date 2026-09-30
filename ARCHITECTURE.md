# 🏗️ ARCHITECTURE.md — Архитектура DCAP

> **Обновляется архитектором при изменениях архитектуры.**
> Текущее состояние — в `STATE.md`. План и бэклог — в `ROADMAP.md`.

**Обновлено:** 30.09.2026
**Версия архитектуры:** v3.13.26 (в процессе — Блок 5 WebUI)

---

## 🏗️ СТРУКТУРА ПРОЕКТА
dcap-system/
├── manager/ # FastAPI :8000 (control-plane)
│ └── src/
│ ├── main.py # точка входа
│ ├── api/ # resources, tasks, findings, catalog, scanner,
│ │ # permissions, audit, auth, retention, webui
│ ├── auth/ # JWT, AD, RBAC
│ │ ├── models.py # User (user_roles, M:N)
│ │ ├── router.py # login/logout/refresh, CRUD users
│ │ ├── audit.py # 🆕 аудит аутентификации (BUG-095)
│ │ └── dependencies.py # require_auth, require_role
│ ├── core/ # security (mTLS), secrets, rate_limit,
│ │ # encryption.py (Findings AES-256-GCM)
│ ├── retention/ # архивация и очистка данных
│ ├── connectors/
│ │ ├── permissions/ # local/ad/mixed
│ │ └── audit/ # windows_audit
│ ├── services/ # access_service, access_config
│ ├── db/ # models.py, session.py, init_roles.py
│ │ └── migrations/ # Alembic (001…005)
│ ├── cache/ # redis_client.py (кэш/rate-limit, fail-open)
│ ├── workers/ # Celery app/tasks/beat
│ └── metrics.py # Prometheus
│
├── scanner/ # Python-сканер (тяжёлый, на хосте)
│ └── src/
│ ├── managed_scanner.py # main loop, submit_results_status, _fail_task_safely
│ ├── heartbeat.py # HeartbeatThread (backoff 5→10→30→60→120)
│ ├── metrics.py # Prometheus :9101
│ ├── finding.py # dataclass Finding (строка/фрагмент)
│ ├── encryption.py # AES-256-GCM + HMAC + маскирование
│ │ # _CONTEXT_PATTERNS (21 паттерн, BUG-086)
│ ├── core/ # orchestrator, state_manager, metrics
│ ├── classifiers/ # PII, Credentials, Code, OCR
│ │ # scan_line(line, num) → list[Finding]
│ ├── connectors/ # filesystem.py (построчное чтение + контекст)
│ └── handlers/ # finding_collector.py
│
├── scanner-rust/ # 🆕 v3.1.0: Rust-ядро (BACKLOG-036)
│ ├── Cargo.toml # ТОЛЬКО CIFS/NFS + параллелизм
│ └── src/
│ ├── main.rs
│ ├── walker.rs # обход ФС (CIFS + NFS)
│ ├── cifs.rs # pavao + libsmbclient
│ ├── nfs.rs # nfs-rs (авто-монтирование)
│ ├── bridge/ipc.rs # JSON-RPC к Python sidecar
│ ├── heartbeat.rs
│ ├── metrics.rs
│ └── reporter.rs
│
├── scanner-python/ # 🆕 v3.1.0: Python sidecar (BACKLOG-036)
│ ├── src/
│ │ ├── sidecar.py # IPC-сервер (JSON-RPC)
│ │ ├── ocr.py # Tesseract wrapper
│ │ ├── pii.py # Presidio wrapper
│ │ └── credentials.py
│ └── requirements.txt
│
├── audit-agent-windows/ # Windows-агент (лёгкий)
│ ├── main.py, collector.py, buffer.py, sender.py
│ ├── service.py # Windows-служба
│ └── config.json
│
├── audit-agent-linux/ # Linux-агент (inotify)
│ ├── main.py, collector.py, buffer.py, sender.py, heartbeat.py
│ ├── metrics.py # Prometheus :9102
│ ├── service/ # systemd unit
│ └── start.sh, stop.sh, status.sh
│
├── audit-agent-s3/ # S3/MinIO агент
│ ├── src/ # main, collector, buffer, sender,
│ │ # converters, heartbeat, state, metrics
│ ├── config/
│ ├── scripts/
│ └── tests/
│
├── webui/ # каноничный UI :8001
│ ├── src/
│ │ ├── main.py # FastAPI приложение (Jinja2)
│ │ ├── api/routes.py # прокси в Manager, forwarded_headers
│ │ └── static/ # CSS, JS, vendor
│ ├── templates/ # Jinja2 шаблоны
│ │ # findings.html, finding_detail.html,
│ │ # catalog.html, false_positives.html, audit.html
│ └── config/config.json
│
├── shared/
│ ├── event_schema.py # UnifiedEvent (Pydantic)
│ ├── cert_utils.py
│ └── security.py
│
├── scripts/
│ ├── generate_certs.py, rotate_certs.py
│ ├── generate_findings_keys.py
│ ├── migrate_sqlite_to_postgres.py
│ ├── deploy.sh, stop.sh, logs.sh, status.sh, healthcheck.sh
│ ├── monitoring-status.sh
│ ├── test-up.sh, test-down.sh, run-tests.sh
│ └── init_ad_test_data.py
│
├── monitoring/ # Prometheus/Grafana/Alertmanager
│ ├── prometheus/{prometheus,alerts}.yml
│ ├── alertmanager/alertmanager.yml
│ └── grafana/provisioning/
│
├── tests/
│ ├── unit/ # unit-тесты (301 passed на v3.13.26)
│ ├── e2e/ # E2E тесты
│ ├── chaos/ # Chaos тесты
│ ├── load/ # Нагрузочные
│ └── fixtures/ # Общие фикстуры
│
├── docs/
│ ├── admin-guide/ # руководство администратора (42.1-42.4)
│ │ ├── README.md
│ │ ├── 01-architecture.md
│ │ ├── 02-installation.md
│ │ ├── 03-configuration.md
│ │ ├── 04-authentication.md
│ │ ├── 05-security.md
│ │ ├── 06-scanner.md
│ │ ├── 07-agents.md
│ │ ├── 08-monitoring.md
│ │ ├── 09-retention.md
│ │ ├── 10-troubleshooting.md
│ │ └── 11-faq.md
│ ├── deployment.md
│ ├── monitoring.md
│ ├── testing.md
│ ├── security_checklist.md
│ └── architecture.png # схема архитектуры (Mermaid + иллюстрация)
│
├── .github/
│ └── workflows/ # CI/CD
│ ├── ci.yml
│ └── release.yml
│
├── alembic.ini
├── docker-compose.yml
├── docker-compose.prod.yml
├── docker-compose.test.yml
├── docker-compose.ad.yml.example
├── SECURITY.md
├── STATE.md
├── ROADMAP.md
├── ARCHITECTURE.md # этот файл
├── AGENTS.md
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
└── requirements-dev.txt

text

---

## 🔐 АУТЕНТИФИКАЦИЯ И БЕЗОПАСНОСТЬ

### Режимы аутентификации

| Режим | Описание |
|-------|----------|
| **local** | JWT + Bcrypt, встроенные пользователи (разработка) |
| **hybrid** | SPNEGO → fallback JWT (тестирование) |
| **windows_integrated** | Только SPNEGO (production AD) |

### Ролевая модель

| Роль | Описание | AD группа |
|------|----------|-----------|
| **Admin** | Полный доступ | DCAP_Admins |
| **Auditor** | Аудит, мониторинг, **расшифровка находок** | DCAP_Auditors |
| **Scanner** | Запуск сканирования | DCAP_Scanners |
| **Viewer** | Только чтение (маскированное) | (все остальные) |

### mTLS

- **relaxed** — если сертификаты не найдены, работает на plain HTTP
- **strict** — Manager не стартует без PKI
- Поддерживается во всех компонентах
- CRL для отзыва сертификатов

### Шифрование находок (Findings Refactor, v3.9.0-v3.10.0)

**Модель:** гибрид — маскированное + зашифрованное.

| Аспект | Решение |
|--------|---------|
| **Алгоритм** | AES-256-GCM |
| **Ключ** | ENV (`FINDINGS_ENCRYPTION_KEY`) — Docker Secrets убраны (TASK-018) |
| **HMAC-ключ** | ENV (`FINDINGS_HMAC_KEY`) |
| **Key ID** | `findings_key_id` (для ротации) |
| **По умолчанию** | Маскированное |
| **Расшифровка** | Только Auditor, с аудитом |
| **Fingerprint** | HMAC-SHA256 (не SHA256 — защита от brute-force) |
| **Legacy-режим** | SHA-256 (не MD5 — BACKLOG-066, крипто-фикс) |

**Что маскируется:**

| Категория | Маска | Шифрование |
|-----------|-------|-----------|
| phone | `+7***123-45-67` | ✅ |
| email | `iv***@example.com` | ✅ |
| api_key / aws_key | `AKIA***` | ✅ |
| password | `***` | ✅ |
| token / jwt_token | `eyJ***` | ✅ |
| ssh_key / github_token / slack_token | `***` | ✅ |
| database_url / basic_auth | `***` | ✅ |
| passport | `12** ******` | ✅ |
| snils / inn | `***` | ✅ |
| credit_card | `**** **** **** 1234` | ✅ |
| person | **не маскируется** | ❌ |

### Маскирование контекстов (BUG-086, v3.13.21)

**Проблема:** `mask_context` покрывал только 6 из 19 категорий `MASK_RULES` — в `context_*` утекали credentials (github_token, basic_auth) и US-phone.

**Решение:** конвейер `_CONTEXT_PATTERNS` (21 паттерн):

| Порядок | Паттерн | Категория |
|---------|---------|-----------|
| 1 | `ghp_*`, `github_pat_*` | `github_token` |
| 2 | `xox[baprs]-*` | `slack_token` |
| 3 | `AKIA*` | `aws_key` |
| 4 | `sk-*`, `sk_live_*` | `api_key` |
| 5 | `discord*` | `discord_token` |
| 6 | `eyJ*.*.*` | `jwt_token` |
| 7 | `-----BEGIN ... PRIVATE KEY-----` | `ssh_key` |
| 8 | `Basic <base64>` | `basic_auth` |
| 9 | `scheme://...` | `database_url` |
| 10 | `password=...`, `api_key=...`, `token=...` | generic (маскируется только значение — 2 capture-группы) |
| 11 | email | `email` |
| 12 | `+7`, `+1`, международные | `phone` |
| 13 | passport, snils, inn, credit_card | PII |

**Ключевые решения:**
- **Специфичные токены раньше generic** — иначе `token` съедал бы `ghp_`-префиксы.
- **Generic `KEY=VALUE`** маскирует **только значение** — сохраняет маркер категории (`GITHUB_TOKEN=ghp_***`, а не `GITHUB_TOKEN=***`).
- **`person` / `high_entropy` не маскируются** в контексте (`high_entropy` — до v3.1.0).

### Аудит действий с findings (v3.13.24–26)

**Все действия с findings логируются в `audit_logs`** — compliance 152-ФЗ / GDPR / PCI DSS.

| Действие | Эндпоинт | `event_type` | `metadata` |
|----------|----------|--------------|------------|
| Раскрытие | `POST /{id}/reveal` | `finding_reveal` | `action=finding_revealed`, `finding_id`, `category` |
| Доступ к фрагменту | `GET /{id}/fragment` | `fragment_accessed` | `finding_id`, `mode` (embedded / full-image) |
| Доступ к hash | `GET /{id}/fragment/hash` | `fragment_accessed` | `finding_id`, `mode=hash` |
| Экспорт | `GET /findings/export` | `findings_exported` | `format`, `count`, `reveal`, фильтры |
| Подтверждение | `PATCH /{id}` (confirmed) | `finding_confirmed` | `old_status`, `new_status`, `comment`, `via=patch` |
| Ложное срабатывание | `PATCH /{id}` (false_positive) | `finding_false_positive` | то же |
| Архивирование | `PATCH /{id}` (archived) | `finding_archived` | то же |
| Сброс | `PATCH /{id}` (new) | `finding_reset` | то же |
| Массовое обновление | `POST /bulk` | `finding_confirmed`/`_false_positive`/`_archived`/`_reset` | `via=bulk`, по одной записи на finding |
| Удаление | `DELETE /{id}` (Admin) | `finding_deleted` | `old_status`, `resource_id`, `via=delete` |

**Поля записи:**
- `event_source = "api"`
- `user` = `current_user.username` (реальный пользователь, не роль БД)
- `file_path` = `fragment_path` finding'а
- `source_host` = IP клиента
- `metadata_json` = `{action, finding_id, category, finding_type, old_status, new_status, comment, via}`

**Хелпер `_log_finding_status_change`** (`manager/src/api/findings.py`):
- Единая точка для PATCH и bulk.
- **Не делает `commit`** — записи копятся, коммит вызывающего кода (избегает N коммитов на bulk).
- Для DELETE — `AuditLog` создаётся **до** `db.delete(finding)`, иначе после commit инстанс expire'ится.

**Сброс review-полей при `new` (BUG-100):** `_apply_status` — единая функция для PATCH и bulk; при `new` очищаются `reviewed_by`, `reviewed_at`, `comment`.

### Аудит аутентификации (BUG-095, v3.13.24)

| Событие | `event_type` | `metadata` |
|---------|--------------|------------|
| Успешный вход | `auth_login` | `auth_source`, `auth_method`, `auth_mode`, `roles` |
| Неудачный вход | `auth_failed` | `reason` (`invalid_credentials`/`user_inactive`/`user_not_found`), `attempted_username` |
| Выход | `auth_logout` | `jti` |
| Создание пользователя | `user_created` | `target_user_id`, `target_username`, `auth_source`, `is_active`, `roles` |
| Обновление | `user_updated` | `changes`, `roles_added`, `roles_removed` |
| Смена пароля | `user_password_changed` | `by_admin`, `self_service` |
| Роли | `role_assigned` / `role_revoked` | `role`, `target_user_id` |
| Удаление | `user_deleted` | `target_user_id`, `target_username`, `roles` |

**`auth_refresh` НЕ логируется** — 290 событий/сутки на пользователя без ценности для расследований.

**Безопасность `metadata`:** `_sanitize` рекурсивно вырезает `password`, `*_token`, `*_secret`, `*_hash`, `*_salt`, `*_credential`; PII (`email`, `full_name`) → `"changed"`.

**Fail-open:** ошибка логирования не ломает эндпоинт (`try/except + rollback`).

**HTTP-ответ при неудачном входе всегда `401 Invalid credentials`** — нельзя перебрать существующие учётки; различие только в аудите.

---

## 📊 МОДЕЛЬ ДАННЫХ: FINDINGS

### Иерархия
Resource (корневая директория задачи)
└── Finding (находка = строка/фрагмент)
├── line_number
├── match_text_masked / match_text_encrypted
├── line_text_masked / line_text_encrypted
├── context_before_masked / context_after_masked
├── fragment_data (OCR PNG, BACKLOG-086)
├── fingerprint (HMAC-SHA256)
└── status (new/confirmed/false_positive/archived)

text

### Модель `Finding`

```python
class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("scan_tasks.id"), nullable=True, index=True)

    # Классификация
    finding_type = Column(String(50), nullable=False, index=True)   # pii, credentials, code
    category = Column(String(100), nullable=False, index=True)      # phone, email, api_key
    severity = Column(String(20), default="medium")

    # Где найдено
    fragment_type = Column(String(20), nullable=False)
    # text_line | text_context | image_region | byte_range
    line_number = Column(Integer, nullable=True)
    line_text_masked = Column(Text, nullable=True)
    line_text_encrypted = Column(Text, nullable=True)
    match_text_masked = Column(Text, nullable=True)
    match_text_encrypted = Column(Text, nullable=True)
    context_before_masked = Column(Text, nullable=True)
    context_after_masked = Column(Text, nullable=True)

    # Не-текстовые
    fragment_path = Column(String(500), nullable=True)
    bounding_box = Column(JSON, nullable=True)
    byte_offset = Column(Integer, nullable=True)
    byte_length = Column(Integer, nullable=True)
    hex_preview = Column(Text, nullable=True)

    # 🆕 BACKLOG-086: встроенные фрагменты
    fragment_data = Column(LargeBinary, nullable=True)      # base64-decoded bytes
    fragment_mime = Column(String(50), nullable=True)       # image/png
    fragment_hash = Column(String(64), nullable=True)       # SHA-256
    fragment_size = Column(Integer, nullable=True)          # bytes
    fragment_embedded_at = Column(DateTime, nullable=True)

    # Дедупликация
    fingerprint = Column(String(64), nullable=False, index=True)   # HMAC-SHA256
    encryption_key_id = Column(String(50), nullable=False)

    # Время
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    # Статус
    status = Column(String(20), default="new", index=True)
    # new | confirmed | false_positive | archived
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    comment = Column(Text, nullable=True)

    # Метаданные
    confidence = Column(Float, nullable=True)
    detector = Column(String(50), nullable=True)  # presidio, regex, entropy, ocr, legacy

    __table_args__ = (
        Index("ix_findings_resource_status", "resource_id", "status"),
        Index("ix_findings_type_category", "finding_type", "category"),
        Index("ix_findings_status_first_seen", "status", "first_seen_at"),
    )
Дедупликация
fingerprint = HMAC-SHA256(file_path + line + match_text + finding_type)

Legacy-режим: SHA-256 (не MD5 — BACKLOG-066)

При повторном скане:

false_positive → не создавать

confirmed → обновить last_seen_at

новый → создать new

Сканер проверяет FP батчем: POST /api/findings/check-fingerprints

Типы фрагментов
Тип	Для чего	Что показывать
text_line	Текстовые файлы	Строка с совпадением
text_context	Текстовые файлы	Строка + N строк контекста
image_region	Изображения, PDF-сканы	Вырезанный фрагмент (PNG) + bounding box
byte_range	Бинарные	Hex-дамп вокруг offset
Встроенные фрагменты (BACKLOG-086, v3.13.19)
Проблема: Manager в Docker не видит хостовые пути сканера → /fragment для OCR возвращал 404. + Файл может быть удалён после сканирования.

Решение: сканер встраивает весь PNG (OCR-фрагмент) в payload (base64 + SHA-256) → Manager хранит fragment_data в БД → «файл удалили — доказательство осталось».

Ограничения:

Только image_region (OCR). text_line — данные уже в line_text_encrypted.

Максимум MAX_FRAGMENT_EMBED_SIZE (ENV, default 2 МБ).

Батчинг POST по MAX_BATCH_SIZE_BYTES (ENV, default 20 МБ).

Дедупликация фрагментов — BACKLOG-087 (v3.1.0).

Шифрование fragment_data — BACKLOG-088 (v3.1.0).

Архивная таблица
findings_old — старая таблица (файл-уровень), сохраняется для отката (миграция 003)

Удалить после проверки: BACKLOG-065

Партиционирование audit_logs
audit_logs — партиционированная таблица (RANGE по created_at)

PK: (created_at, id)

⚠️ В SQL user обязательно в кавычках — иначе PostgreSQL вернёт CURRENT_USER (BUG-094)

🔌 API ЭНДПОИНТЫ
Находки (Findings Refactor, v3.9.0–v3.13.26)
Метод	Эндпоинт	Роль	Назначение
GET	/api/findings	Viewer+	Список (маскированное, фильтры)
GET	/api/findings/{id}	Viewer+	Детали (маскированное)
POST	/api/findings/{id}/reveal	Auditor+	Расшифровка (с аудитом)
PATCH	/api/findings/{id}	Auditor+	Статус (confirmed/false_positive/archived/new)
POST	/api/findings/bulk	Auditor+	Массовое обновление (до 1000)
GET	/api/findings/stats	Viewer+	Статистика
GET	/api/findings/false-positives	Auditor+	Список FP
GET	/api/findings/{id}/fragment	Auditor+	Фрагмент (embedded / full-image / bbox)
GET	/api/findings/{id}/fragment/hash	Auditor+	Метаданные фрагмента
GET	/api/findings/export	Auditor+	Экспорт (CSV/JSON)
DELETE	/api/findings/{id}	Admin	Удалить (с аудитом)
POST	/api/findings/check-fingerprints	публичный	Проверка FP (machine-API)
GET	/api/findings/count	Viewer+	Legacy-счётчик (WebUI)
Фильтры GET /api/findings:

Параметр	Тип	Pattern / Ограничение
resource_id	int	—
task_id	int	—
status	str	new / confirmed / false_positive / archived
finding_type	str	pii / credentials / code
category	str	CSV: phone, email; legacy: pii, credentials, code → finding_type
severity	str	—
detector	str	🆕 BUG-090 (v3.13.22)
fragment_type	str	🆕 BUG-090 (v3.13.22)
search	str	🆕 ILIKE по fragment_path / match_text_masked / line_text_masked
limit	int	_clamp_int (1..1000), default 100
offset	int	_clamp_int (0..10M), default 0
order_by	str	^(first_seen_at|last_seen_at|severity|line_number|id)$
order	str	^(asc|desc)$, default desc
FastAPI 0.137 gotcha: BeforeValidator в Annotated теряется, если Query(...) указан в default (create_model_field берёт annotation из field_info) → Query() объявлен внутри Annotated, дефолт через =; числовые le/ge несовместимы с Optional[int] (TypeError на None) → _clamp_int().

Формат ответа списка — плоский массив, не {items, total}:

X-Total-Count — заголовок (BACKLOG-067)

Поля: id, resource_id, task_id, finding_type, category, severity, fragment_type, line_number, match_text (masked), line_text (masked), context_before / context_after (masked), has_fragment, bounding_box, byte_offset, byte_length, file_path, value, status, reviewed_by, reviewed_at, comment, confidence, detector, first_seen_at, last_seen_at, has_encrypted, can_reveal, encryption_key_id

fingerprint — не отдаётся наружу (только через check-fingerprints)

match_text_encrypted / line_text_encrypted — не отдаются

Сканер
Метод	Эндпоинт	Назначение
POST	/api/scanner/register	Регистрация
POST	/api/scanner/heartbeat	Heartbeat (scanner_id, task_id, progress)
POST	/api/scanner/tasks/{id}/results	Результаты (findings + fragment_base64)
GET	/api/scanner/{id}	Статус
GET	/api/scanner/tasks/pending?scanner_id=N	Задачи для сканера
Аутентификация
Метод	Эндпоинт	Назначение
POST	/api/auth/login	Логин (auth_login / auth_failed)
POST	/api/auth/refresh	Обновление токена
POST	/api/auth/logout	Выход (auth_logout)
GET	/api/auth/me	Информация о пользователе
GET	/api/auth/mode	Режим аутентификации
GET/POST/PUT/DELETE	/api/auth/users	CRUD пользователей (Admin, user_created/user_updated/user_deleted)
PUT	/api/auth/users/{id}/roles	role_assigned / role_revoked
POST	/api/auth/change-password	user_password_changed (self)
GET/POST	/api/auth/roles	CRUD ролей (Admin)
Каталог
Метод	Эндпоинт	Назначение
GET	/api/catalog/resources	Ресурсы (директории)
GET	/api/catalog/resources/{id}/findings	Строки файла с находками
GET	/api/catalog/tree	Дерево с находками на уровне строк
Аудит
Метод	Эндпоинт	Назначение
GET	/api/audit	Список событий (event_source, event_type, user)
GET	/api/audit/stats	Агрегаты (by_source, by_type)
POST	/api/audit/agents/heartbeat	Heartbeat агентов
Архивация
Метод	Эндпоинт	Назначение
GET	/api/retention/policies	Политики хранения
POST	/api/retention/run	Ручной запуск
GET	/api/retention/status	Статус
POST	/api/retention/export	Экспорт
Метрики
Метод	Эндпоинт	Назначение
GET	/metrics	Prometheus-метрики Manager
GET	/api/health	Healthcheck
📈 МОНИТОРИНГ
Метрики
Компонент	Порт	Ключевые метрики
Manager	:8000/metrics	dcap_http_*, dcap_tasks_total, dcap_findings_total, dcap_scanner_*, dcap_celery_queue_size
Scanner	:9101	dcap_scanner_files_scanned_total, dcap_scanner_findings_total, dcap_scanner_errors_total
Linux-агент	:9102	dcap_linux_*
S3-агент	:9103	dcap_s3_*
Celery	:9808	(celery-exporter)
PostgreSQL	:9187	(postgres-exporter)
Redis	:9121	(redis-exporter)
Heartbeat-thread (v3.7.0, backoff v3.13.20)
scanner/src/heartbeat.py — daemon, interval 30 c, fail-open

POST /api/scanner/heartbeat с {scanner_id, status, current_task_id, progress}

Manager _mark_stale_scanners не трогает сканеры с активным заданием

Backoff (BUG-080, v3.13.20): BACKOFF_STEPS = [5, 10, 30, 60, 120]; фейлы — DEBUG, WARNING на 1-м и каждые 5; _stop.wait() вместо time.sleep(); INFO «Heartbeat restored after N failure(s)»

Prometheus targets (6/6 up)
text
http://celery_exporter:9808/metrics      up
http://manager:8000/metrics              up
http://postgres_exporter:9187/metrics    up
http://redis_exporter:9121/metrics       up
http://s3_agent:9103/metrics             up
http://host.docker.internal:9101/metrics up  (scanner, на хосте)
Алерты
Алерт	Условие	Severity
ScannerInactive	dcap_scanner_heartbeat_age_seconds > 120	warning
TaskFailed	increase(dcap_tasks_total{status="failed"}[5m]) > 0	critical
HighErrorRate	rate(dcap_http_requests_total{status=~"5.."}[5m]) > 0.05	critical
CeleryQueueBacklog	dcap_celery_queue_size > 100	warning
Аудит: аудит-логи партиционированы
⚠️ Диагностические запросы: ORDER BY created_at DESC, id DESC (а не ORDER BY id DESC) — из-за партиционирования.

📤 SIEM-ИНТЕГРАЦИЯ (v3.1.0+)
Назначение
Передача событий ИБ из DCAP в SIEM для централизованного мониторинга, корреляции, compliance (152-ФЗ, GDPR, PCI DSS), алертинга.

Форматы
Формат	Протокол	SIEM
Syslog (RFC 5424)	UDP / TCP / TLS	ArcSight, QRadar, MaxPatrol, Wazuh, rsyslog
JSON	HTTP/HTTPS (webhook)	Splunk HEC, Elastic, Kibana, кастомные SIEM
События ИБ
Источник	Событие	Severity
Findings	finding_detected	по severity
Findings	finding_revealed	high
Findings	finding_confirmed	medium
Findings	finding_false_positive	low
Findings	finding_archived	low
Findings	finding_deleted	medium
Scanner	scan_started / scan_completed	info
Scanner	scan_failed / scanner_inactive	high / warning
Audit	auth_login / auth_failed	info / medium
Audit	user_created / role_changed	medium
Audit	fragment_accessed	medium
Retention	retention_run	info
Архитектура
text
Manager (события) → EventGenerator → SIEMConnector
                                       ├── SyslogSender (UDP/TCP/TLS)
                                       └── JSONSender (HTTP/HTTPS)
                                              ├─→ Dead-letter queue (Redis) при ошибке
                                              └─→ Retry с backoff
Модули (v3.1.0)
text
manager/src/siem/
├── generator.py         # генерация событий из findings/audit
├── config.py            # конфигурация (Syslog/JSON)
├── senders/
│   ├── syslog_sender.py # RFC 5424 (UDP/TCP/TLS)
│   └── json_sender.py   # HTTP/HTTPS webhook
└── queue.py             # dead-letter + retry
Ключевые свойства
Асинхронная отправка через Celery.

Retry с экспоненциальным backoff.

Dead-letter queue (Redis) при недоступности SIEM.

Метрики: dcap_siem_events_sent_total, dcap_siem_events_failed_total.

Только маскированные match_text — без reveal.

match_text_encrypted не отправляется.

WebUI (BACKLOG-072)
Страница /settings/siem:

Формы: Syslog (host, port, protocol, TLS), JSON (URL, token).

Выбор событий (чекбоксы).

Кнопка «Test» — тестовое событие.

Метрики — отправлено/ошибок за 24ч.

v4.0.0+
Kafka / Kinesis — потоковая передача.

CEF / LEEF — если потребуется.

⚡ ОПТИМИЗАЦИЯ ПРОИЗВОДИТЕЛЬНОСТИ (v3.1.0+)
Проблема
Python-сканер — узкое место на 100k+ строках. Профилирование: ~60% в Presidio/spaCy, ~40% — в собственных regex-фильтрах и маскировании.

Стратегия: Cython + Rust (гибрид)
Компонент	Технология	Прирост	Приоритет
Regex-фильтры (_filter_url_over_email, _filter_spacy_noise)	Cython + cre/re2	3–10×	BACKLOG-090
Маскирование (mask_context, _CONTEXT_PATTERNS)	Cython	3–5×	BACKLOG-089
Entropy-анализ	Cython	5–10×	BACKLOG-089
Prefilter	Cython	3–5×	BACKLOG-089
Обход ФС (CIFS/NFS)	Rust (pavao, nfs-rs)	нативно	BACKLOG-036
Параллелизм	Rust (rayon)	N×CPU	BACKLOG-036
OCR (Tesseract)	Python (CLI)	—	—
Presidio/spaCy	Python (уже Cython внутри)	—	—
Cython vs Rust
Cython:

Низкий порог входа (Python + типы).

Плавная интеграция в существующий код.

3–10× на своих функциях (потолок ~5×, редко 10×).

Ограничен GIL (частично — nogil).

Простой rollback (.pyx → .py).

Для существующего Python-кода.

Rust:

Высокий порог входа (ownership, borrow checker).

Отдельный модуль + FFI/IPC.

10–50×, близко к C.

Нативный параллелизм (rayon, tokio).

Готовые крейты для сетевых ФС (pavao, nfs-rs).

Для новых компонентов (сети, IPC).

Быстрые regex-движки (BACKLOG-090)
Библиотека	Технология	Особенность
cre	Cython + GLib PCRE	Освобождает GIL → распараллеливание regex без Rust
re2	Google RE2	Линейное время, устойчивость к ReDoS
esmre	Cython	Индекс обязательных подстрок — быстрый отсев несовпадающих регулярок
simple-fast-regex	Python + Rust	Можно обернуть через Cython
Важно: «цитонизировать» re.py напрямую не даст прироста — движок re уже на C (_sre). Нужно менять движок (cre, re2) или использовать Cython + библиотеки.

Ожидаемый эффект
30–50% общего ускорения сканирования от Cython.

дополнительно от параллелизма (Rust) на многоядерных CPU.

без переписывания Presidio/spaCy.

TruffleHog (BACKLOG-091, v3.1.0+)
Идея: верификация credentials через API провайдера (AWS, GitHub, Slack, Stripe) — «рабочий» / «просроченный» / «unverified».

Плюс: снижение FP на high_entropy, приоритизация подтверждённых.

Ограничения: ресурсоёмкий (4+ CPU, 16 ГБ RAM), требует egress.

Не заменяет DCAP — другая ниша (code secrets vs DLP).

📝 КЛЮЧЕВЫЕ РЕШЕНИЯ
Архитектурные
Решение	Обоснование
Гибридная аутентификация	local + AD, плавный переход в enterprise
mTLS relaxed/strict	Обратная совместимость с dev
Secret Scanner интеграция	FP-фильтры, расширенные типы
Масштабирование (PG/Redis/Celery)	Celery Beat, партиционированные audit_logs
Scanner на хосте (не Docker)	Docker не может динамически монтировать пути
Heartbeat-thread	Отдельный поток — сканер не «inactive»
Findings = строка/фрагмент	Нельзя обработать результаты, если находка = файл
Гибридное хранение (masked + encrypted)	Безопасность + удобство анализа
Расшифровка — только Auditor, с аудитом	Минимизация доступа + compliance
HMAC-fingerprint	Защита от brute-force по fingerprint
MD5 → SHA-256 в legacy	MD5 криптографически сломан (BACKLOG-066)
Встроенные фрагменты в БД	«Файл удалили — доказательство осталось» (BACKLOG-086)
Аудит PATCH/bulk/DELETE findings	Compliance 152-ФЗ / GDPR / PCI DSS (BUG-101, 101b)
Cython + Rust (гибрид)	Cython — для горячих точек Python, Rust — для сетей/параллелизма
Rust Scanner (v3.1.0)	Только CIFS/NFS + параллелизм (BACKLOG-036); классификаторы/PII — Python
Технические
Решение	Обоснование
PostgreSQL + Redis в Docker	Production-готовность
ENV-ключи (не Docker Secrets)	Упрощение ротации, единый источник (TASK-018)
Единый формат событий (UnifiedEvent)	Унификация источников
Текстовый лог-отчёт	Безопасный для выкладки
Prometheus + Grafana + Alertmanager	Стандартный стек
spaCy-модели sm	Жёстко зашито в pii_classifier
spnego убран из requirements	Нет на PyPI, реальный — pyspnego
AES-256-GCM для находок	Стандарт для шифрования данных
Pytest + docker-compose.test.yml	Изолированные тесты
_clamp_int + OptInt	Валидация числовых query-параметров (BUG-084, 099)
forwarded_headers	WebUI-прокси: X-Total-Count, X-Fragment-*, Content-Disposition (BUG-087)
fetch + Blob + Bearer	Бинарные данные (fragment, export) — не <img>/window.location (BUG-088, 093)
SubmitStatus (OK/RETRY/LOST)	Оффлайн-буфер: 404/410 → LOST (пачка отбрасывается) (BUG-097)
_CONTEXT_PATTERNS	mask_context: 21 паттерн, специфичные раньше generic (BUG-086)
_log_finding_status_change	Единая точка аудита PATCH/bulk; без commit — batch (BUG-101)
_apply_status	Единая функция PATCH/bulk; сброс review при new (BUG-100)
⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ
Ограничение	Описание	План
/metrics публичный	Нет JWT/basic_auth	BACKLOG-044
Прогресс сканера	Не виден в WebUI	BACKLOG-043 (🔄)
NOT NULL поля	Возможны скрытые баги	BACKLOG-039
Параллельный батч	Форк один (OCRWorker)	BACKLOG-040 (v3.1.0)
NFS на Windows	Ограниченный клиент	Решено в nfs-rs (v3.1.0)
Presidio	Медленный на 100k+ строк	BACKLOG-063 (v3.1.0)
findings_old	Legacy-таблица в БД	BACKLOG-065
WebUI legacy Findings	Деградация до 40.3	BACKLOG-061 (🔄)
order_by=severity	Лексикографический порядок (не семантический)	BUG-083 (v3.1.0)
/fragment для text_line	400 (не 404 + пояснение)	BUG-085 (v3.1.0)
OCR bbox	None до v3.1.0 (Tesseract без tsv)	BACKLOG-085
Сканер не перезапускается	После рестарта Docker/хоста	TEST-NOTE-5.8 (v3.1.0)
📘 АДМИН-РУКОВОДСТВО (Дни 42.1-42.4)
Принцип: документация = проверенный факт. Кодер валидирует каждый раздел по реальному коду.

Структура docs/admin-guide/:

README.md — оглавление + быстрый старт

01-architecture.md — обзор компонентов

02-installation.md — установка (Docker + локально)

03-configuration.md — все конфиги, env-переменные

04-authentication.md — local/AD/hybrid, RBAC

05-security.md — mTLS, ключи, секреты, аудит findings/auth, маскирование контекстов

06-scanner.md — настройка, задания, FP

07-agents.md — Windows/Linux/S3

08-monitoring.md — метрики, алерты

09-retention.md — архивация

10-troubleshooting.md — решение проблем (в т.ч. user без кавычек, stale __pycache__, аудит auth)

11-faq.md — частые вопросы

Разбивка:

42.1 — установка + конфигурация

42.2 — аутентификация + безопасность

42.3 — сканер + агенты

42.4 — мониторинг + retention + troubleshooting + FAQ

Актуально на: 30.09.2026
Версия архитектуры: v3.13.26 (в процессе — Блок 5 WebUI)

text

---

## 📌 Что изменилось в ARCHITECTURE.md

| # | Раздел | Что добавлено |
|---|--------|---------------|
| 1 | Версия | v3.11.0 → **v3.13.26** |
| 2 | `manager/src/auth/` | Добавлен `audit.py` (BUG-095) |
| 3 | `manager/src/db/migrations/` | 001…**005** (было 003) |
| 4 | `scanner-rust/` | Уточнение: **ТОЛЬКО CIFS/NFS + параллелизм** (BACKLOG-036) |
| 5 | Секция «Шифрование находок» | Добавлена **«Маскирование контекстов»** (`_CONTEXT_PATTERNS`, 21 паттерн) |
| 6 | Новая секция | **«Аудит действий с findings»** (PATCH/bulk/DELETE + reveal/fragment/export) |
| 7 | Новая секция | **«Аудит аутентификации»** (9 event_type, BUG-095) |
| 8 | Модель `Finding` | +5 колонок `fragment_*` (BACKLOG-086) |
| 9 | Новая секция | **«Встроенные фрагменты»** (BACKLOG-086) |
| 10 | Новая секция | **«Партиционирование audit_logs»** + кавычки для `user` |
| 11 | API Findings | +`detector`, `fragment_type`, `search`; `_clamp_int`; формат ответа; FastAPI 0.137 gotcha |
| 12 | API Scanner | +`register`, `tasks/pending` |
| 13 | API Auth | +`/users/{id}/roles`, `change-password` |
| 14 | API Audit | +`/api/audit/stats` |
| 15 | Мониторинг | +Backoff heartbeat (BUG-080); 6/6 targets; партиционирование |
| 16 | SIEM | +`finding_archived`, `finding_deleted`, `fragment_accessed` |
| 17 | Новая секция | **«Оптимизация производительности»** (Cython/Rust/`cre`/`re2`/TruffleHog) |
| 18 | Ключевые решения | +12 новых (BUG-086, 097, 100, 101, Cython, Rust-scope) |
| 19 | Известные ограничения | +`order_by=severity`, `/fragment text_line`, OCR bbox, сканер |
| 20 | Админ-руководство | +аудит findings/auth, маскирование контекстов, troubleshooting |