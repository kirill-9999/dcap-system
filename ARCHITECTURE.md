# 🏗️ ARCHITECTURE.md — Архитектура DCAP

> **Обновляется архитектором при изменениях архитектуры.**
> Текущее состояние — в `STATE.md`. План и бэклог — в `ROADMAP.md`.

**Обновлено:** 01.10.2026
**Версия архитектуры:** v3.13.27 (в процессе — Блок 5, 7 закрыты)

---

## 🏗️ СТРУКТУРА ПРОЕКТА

```text
dcap-system/
├── manager/ # FastAPI :8000 (control-plane)
│ └── src/
│ ├── main.py # точка входа
│ ├── config.py # загрузка конфига (config.json + env)
│ ├── api/ # resources, tasks, findings (+schemas_findings),
│ │ # catalog, scanner, permissions, audit, retention, webui
│ ├── auth/ # JWT, AD, RBAC
│ │ ├── models.py # User (user_roles, M:N)
│ │ ├── router.py # login/logout/refresh, CRUD users/roles
│ │ ├── audit.py # аудит аутентификации (BUG-095)
│ │ ├── dependencies.py # require_auth/require_admin/require_auditor
│ │ ├── manager.py, modes.py, middleware.py
│ │ ├── jwt.py, local_auth.py, ad_auth.py, windows_auth.py
│ │ └── schemas.py, rate_limit.py
│ ├── core/ # security (mTLS), secrets, rate_limit, encryption,
│ │ # csv_utils, hex_dump, image_fragment
│ ├── retention/ # архивация и очистка данных
│ ├── connectors/
│ │ ├── permissions/ # local, remote, ad (Mixed — внутри ad.py), factory, cache
│ │ └── audit/ # windows_audit
│ ├── services/ # access_service, access_config
│ ├── db/ # models.py, session.py, init_roles.py
│ │ └── migrations/ # Alembic (001…005)
│ ├── cache/ # redis_client.py (кэш/rate-limit, fail-open)
│ ├── workers/ # Celery app/tasks/beat_schedule
│ └── metrics.py # Prometheus
│
├── scanner/ # Python-сканер (тяжёлый, на хосте)
│ └── src/
│ ├── managed_scanner.py # main loop, submit_results_status, _fail_task_safely
│ ├── heartbeat.py # HeartbeatThread (backoff 5→10→30→60→120)
│ ├── metrics.py # Prometheus :9101
│ ├── config_loader.py # конфиг + env-override
│ ├── finding.py # dataclass Finding (строка/фрагмент)
│ ├── encryption.py # AES-256-GCM + HMAC + маскирование
│ │ # _CONTEXT_PATTERNS (22 паттерна, BUG-086)
│ ├── modes/ # base, hybrid, managed, standalone
│ ├── offline/ # queue, storage (оффлайн-батчи)
│ ├── core/ # orchestrator, state_manager, metrics
│ ├── classifiers/ # PII, Credentials, Code, OCR
│ │ # scan_line(line, num) → list[Finding]
│ ├── connectors/ # filesystem.py (построчное чтение + контекст)
│ └── handlers/ # finding_collector.py
│ ├── utils/ # document_extractor, file_hasher, ocr_engine,
│ │ # performance_monitor
│ └── config/scanner_config.json
│
├── audit-agent-windows/ # Windows-агент (лёгкий)
│ ├── main.py, collector.py, buffer.py, sender.py
│ ├── service.py # Windows-служба
│ └── config.json
│
├── audit-agent-linux/ # Linux-агент (inotify)
│ ├── main.py, collector.py, buffer.py, sender.py
│ ├── metrics.py # Prometheus :9102
│ ├── service/ # systemd unit + install/uninstall
│ └── start.sh, stop.sh, status.sh
│
├── audit-agent-s3/ # S3/MinIO агент
│ ├── src/ # main, collector, buffer, sender,
│ │ # converters, heartbeat, state, metrics
│ ├── config/
│ ├── scripts/
│ └── tests/
│
├── webui/ # каноничный UI :8001 (прокси в Manager)
│ ├── main.py # FastAPI (Jinja2)
│ ├── config.py # загрузка конфига
│ ├── api/ # routes.py (прокси, forwarded_headers), schemas.py
│ ├── static/ # CSS, JS, vendor
│ ├── templates/ # Jinja2: base, login, dashboard, resources,
│ │ # findings, finding_detail, catalog, false_positives,
│ │ # audit, scanners, access, roles, users, settings
│ └── config/config.json
│
├── shared/
│ ├── event_schema.py # UnifiedEvent (Pydantic)
│ ├── cert_utils.py
│ └── security.py
│
├── scripts/
│ ├── generate_certs.py, rotate_certs.py
│ ├── generate_findings_keys.py, reencrypt_findings.py
│ ├── migrate_sqlite_to_postgres.py
│ ├── deploy.sh, stop.sh, logs.sh, status.sh, healthcheck.sh
│ ├── monitoring-status.sh
│ ├── test-up.sh, test-down.sh, run-tests.sh
│ └── init_ad_test_data.py, create_test_share.ps1
│
├── monitoring/ # Prometheus/Grafana/Alertmanager
│ ├── prometheus/{prometheus,alerts}.yml
│ ├── alertmanager/alertmanager.yml
│ └── grafana/provisioning/
│
├── tests/
│ ├── unit/ # unit-тесты (317 passed на v3.13.27)
│ ├── e2e/ # E2E тесты (47 passed / 6 skipped)
│ ├── chaos/ # Chaos тесты
│ ├── load/ # Нагрузочные
│ └── fixtures/ # Общие фикстуры
│
├── manager/tests/ # pytest-модули Manager (test_security,
│ # test_retention, test_auth_ad, test_ad_permissions)
│
├── docs/
│ ├── admin-guide/ # 04-authentication, 05-security,
│ │ # 06-scanner, 10-troubleshooting
│ │ # (01,02,03,07,08,09,11 — ещё не написаны)
│ ├── deployment.md
│ ├── monitoring.md
│ ├── testing.md
│ ├── security_checklist.md
│ ├── architecture.mermaid # схема архитектуры
│ ├── architecture_webui_manager_merge.md
│ └── launch_guide.md
│
├── run_all.py, run_manager.py, run_webui.py
├── run_scanner.py, run_audit_agent.py, run_audit_agent_linux.py
├── init_db.py, fix_db.py, scan_folder.py
├── alembic.ini
├── docker-compose.yml, docker-compose.prod.yml
├── docker-compose.test.yml, docker-compose.s3.yml
├── docker-compose.ad.yml.example
├── SECURITY.md, NOTICE.md
├── STATE.md, ROADMAP.md
├── ARCHITECTURE.md # этот файл
├── AGENTS.md, README.md, CHANGELOG.md
├── pyproject.toml, requirements.txt, requirements-dev.txt
├── Diagram-ru.png, Diagram-en.png # схемы в корне
└── LICENSE # ⚠️ отсутствует (NO LICENSE в репозитории)

```

---

## 🔐 АУТЕНТИФИКАЦИЯ И БЕЗОПАСНОСТЬ

### Режимы аутентификации

`AuthMode` (`manager/src/auth/modes.py`), дефолт в коде — `local`, в `config.json` — `${AUTH_MODE:-hybrid}`.

| Режим | Описание |
|-------|----------|
| **local** | JWT + Bcrypt, встроенные пользователи (разработка) |
| **hybrid** | SPNEGO → fallback JWT (тестирование) |
| **windows_integrated** | Только SPNEGO (production AD) |

> ⚠️ `ad.py` (коннектор прав AD) — **заглушка**; локальный сбор прав идёт через `icacls` / `net localgroup`.

### Ролевая модель

Роли создаются `db/init_roles.py` при старте. Проверки — в `auth/dependencies.py`.

| Роль | Роли в `require_*` | Описание | AD группа |
|------|-------------------|----------|-----------|
| **admin** | `require_admin`, `require_viewer` | Полный доступ | DCAP_Admins |
| **auditor** | `require_auditor`, `require_viewer` | Аудит + **расшифровка находок** | DCAP_Auditors |
| **scanner** | `require_viewer`, `require_scanner` | Запуск сканирования | DCAP_Scanners |
| **viewer** | `require_viewer` | Только чтение (маскированное) | (все остальные) |

> ⚠️ `require_viewer` перечисляет все 4 роли, поэтому на практике эквивалентен `require_auth`. В `api/findings.py` импортируется, но не применяется ни на одном маршруте — там стоит `require_auth`.
> ⚠️ Роль `admin` создаётся с паролем `admin/admin123` — **сменить при первом запуске**.

### mTLS

- **relaxed** (по умолчанию) — если сертификаты не найдены, работает на plain HTTP; `run_manager.py` передаёт в uvicorn `ssl_cert_reqs=ssl.CERT_OPTIONAL`.
- **strict** — Manager не стартует без PKI (`CertificateManager.is_available` → raise).
- CRL для отзыва сертификатов (`CertificateManager.is_revoked`).
- Клиентский CN извлекается в `AuthMiddleware._check_mtls` → `request.state.client_cert_cn`.

> ⚠️ Machine-эндпоинты в `auth/middleware.py` (`public_paths`): `/api/scanner/register`, `/api/scanner/heartbeat`, `/api/scanner/tasks*`, `/api/audit/agents/register`, `/api/audit/agents/heartbeat`, `/api/audit/events`, `/api/audit/permissions`. Остальные `/api/scanner/*` — в `machine_prefixes`: JWT не требуется, но в `strict` без клиентского сертификата → 401.

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

**Что маскируется (`MASK_RULES`):**

Маски **различаются между модулями**: `scanner/src/encryption.py` — 19 категорий, `manager/src/core/encryption.py` — 11 (без credential-специфичных). Категории, которых нет в Manager, приходят маскированными от сканера.

| Категория | Маска | Где | Шифрование |
|-----------|-------|-----|-----------|
| phone | `+7***XXX-XX-XX` | оба | ✅ |
| email | `us***@ex***.com` (BUG-044) | оба | ✅ |
| api_key / aws_key | `AKIA***` (первые 4) | оба | ✅ |
| password | `***` | оба | ✅ |
| token | `eyJh***` (первые 6) | оба | ✅ |
| jwt_token | `eyJhbG***` (первые 10) | scanner | ✅ |
| ssh_key | `***ssh-private-key***` | scanner | ✅ |
| github_token | `ghp_***` (первые 4) | scanner | ✅ |
| slack_token | `xoxb***` (первые 5) | scanner | ✅ |
| discord_token | `disco***` (первые 6) | scanner | ✅ |
| database_url | `scheme://***@host` | scanner | ✅ |
| basic_auth | `Basic ***` | scanner | ✅ |
| high_entropy | первые 6 симв. | scanner | ✅ |
| passport | `12** ******` | оба | ✅ |
| snils | `***-***-*** **` | оба | ✅ |
| inn | `12**********` | оба | ✅ |
| credit_card | `**** **** **** 1234` | оба | ✅ |
| person | **не маскируется** (по решению) | оба | ❌ |

> ⚠️ `phone` маскируется только для RU-номеров вида `+7` + 11 цифр (`_mask_phone`); US/интернациональные номера через `MASK_RULES` не проходят и закрываются `_CONTEXT_PATTERNS`.

### Маскирование контекстов (BUG-086, v3.13.21)

**Проблема:** `mask_context` покрывал только 6 из 19 категорий `MASK_RULES` — в `context_*` утекали credentials (github_token, basic_auth) и US-phone.

**Решение:** конвейер `_CONTEXT_PATTERNS` — **22 паттерна** (17 уникальных категорий из 19 в `MASK_RULES`; `person` и `high_entropy` исключены осознанно):

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
| 10 | `password=` / `api_key=` (2 паттерна) | `password`, `api_key` |
| 11 | `token=`, `secret=`, `access_key=` (3 паттерна) | `token` |
| 12 | email (1) | `email` |
| 13 | phone: `+7`, `+1`, международные (3) | `phone` |
| 14 | passport, snils, inn, credit_card (4) | PII |

Итого 22 паттерна: строки 1–9 дают по 1–2, строки 10–14 — по 2–4.

**Ключевые решения:**
- **Специфичные токены раньше generic** — иначе `token` съедал бы `ghp_`-префиксы.
- **Generic `KEY=VALUE`** маскирует **только значение** — сохраняет маркер категории (`GITHUB_TOKEN=ghp_***`, а не `GITHUB_TOKEN=***`).
- **`person` и `high_entropy` в контекст не попадают** — исключены осознанно (`high_entropy` маскируется в самом finding, но не в `context_*`).

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

```text
Resource (корневая директория задачи)
└── Finding (находка = строка/фрагмент)
    ├── line_number
    ├── match_text_masked / match_text_encrypted
    ├── line_text_masked / line_text_encrypted
    ├── context_before_masked / context_after_masked
    ├── fragment_data (OCR PNG, BACKLOG-086)
    ├── fingerprint (HMAC-SHA256)
    └── status (new/confirmed/false_positive/archived)
```

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
    fragment_mime = Column(String(50), nullable=True)       # image/png, image/jpeg
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

    resource = relationship("Resource", back_populates="findings")
    task = relationship("ScanTask", back_populates="findings")
    # ⚠️ BUG-102: строка "User" требует, чтобы manager.src.auth.models был
    # импортирован в любом процессе, трогающем Finding (Celery worker, retention)
    reviewer = relationship("User", foreign_keys=[reviewed_by])
```

> ⚠️ 5 колонок `fragment_*` добавлены миграцией `005_add_fragment_columns.py`, а не `003_findings_refactor.py`.

### Дедупликация

`manager/src/core/encryption.py`:

```python
msg = f"{file_path}|{line}|{match}|{category}".encode("utf-8")
hmac.new(hmac_key, msg, hashlib.sha256).hexdigest()
```

Разделитель — `|`. 4-й параметр сигнатуры называется `category`, но **оба вызывающих передают `finding_type`** (`api/scanner.py`, `scanner/src/managed_scanner.py`).

**Legacy-режим:** SHA-256 без HMAC (`_legacy_fingerprint` в сканере) — не MD5 (BACKLOG-066).

> ⚠️ Два нюанса:
> - Сканер считает `legacy_fingerprint` и кладёт в payload, но **Manager его не читает** — при отсутствии `fingerprint` Manager сам считает HMAC. То есть legacy-ветка на дедупликацию не влияет.
> - Миграция `003` для переноса legacy-строк использует `md5(random()::text || resource_id::text)` как fingerprint. MD5 в проекте остался только здесь (путь миграции, только PostgreSQL).

**При повторном скане** (`api/scanner.py`):

| Статус в БД | Действие |
|-------------|----------|
| `false_positive` | не создавать (`skipped_false_positives`) |
| `confirmed` / `new` / `archived` | обновить `last_seen_at` + masked/encrypted-поля |
| не найден | создать `new` |

> ⚠️ Ветка обновления покрывает **все три** статуса, а не только `confirmed`. И на практике из сканера она почти не достигается: FP-фильтр сканера (`skip = false_positives | confirmed`) не отправляет в Manager и подтверждённые находки, поэтому обновление возможно только при прямом POST без HMAC-ключей.

**Сканер** проверяет FP батчем: `POST /api/findings/check-fingerprints`.

### Типы фрагментов

| Тип | Для чего | Что показывать |
|-----|----------|----------------|
| `text_line` | Текстовые файлы | Строка с совпадением |
| `text_context` | Текстовые файлы | Строка + N строк контекста |
| `image_region` | Изображения, PDF-сканы | Вырезанный фрагмент (PNG) + bounding box |
| `byte_range` | Бинарные | Hex-дамп вокруг offset |

> ⚠️ Валидации значений **нет**: `FragmentType` Literal объявлен в `api/schemas_findings.py`, но нигде не применяется. На записи значение берётся из payload (`default="text_line"`), на фильтре — точный `==` без pattern, CHECK-constraint в БД отсутствует.

### Встроенные фрагменты (BACKLOG-086, v3.13.19)

**Проблема:** Manager в Docker не видит хостовые пути сканера → `/fragment` для OCR возвращал 404. + Файл может быть удалён после сканирования.

**Решение:** сканер встраивает весь PNG (OCR-фрагмент) в payload (base64 + SHA-256) → Manager хранит `fragment_data` в БД → «файл удалили — доказательство осталось».

**Ограничения:**

- Только `image_region` (OCR). `text_line` — данные уже в `line_text_encrypted`.
- Максимум `MAX_FRAGMENT_EMBED_SIZE` (ENV, default 2 МБ).
- Батчинг POST по `MAX_BATCH_SIZE_BYTES` (ENV, default 20 МБ).
- Дедупликация фрагментов — BACKLOG-087 (v3.1.0).
- Шифрование `fragment_data` — BACKLOG-088 (v3.1.0).

### Архивная таблица findings_old

Миграция `003_findings_refactor.py` переименовывает старую `findings` (файл-уровень) в `findings_old`. Таблица **не удаляется** ни одной миграцией.

> ⚠️ Уточнения:
> - `findings_old` появляется **только** если до миграции была старая схема без `fingerprint`. Если БД создана через `create_all` с новой схемой, `upgrade()` выходит сразу и таблицы не будет.
> - Данные переносятся **только на PostgreSQL**. На SQLite (dev) старые строки остаются в `findings_old` без переноса.
> - Удаление — **BACKLOG-065** (вместе с `findings_archive`).

### Партиционирование audit_logs

`audit_logs` — партиционированная таблица (RANGE по `created_at`), только PostgreSQL. Подробности — в секции [Retention](#-retention-v31327).

**PK:** `(created_at, id)` — из-за этого `ORDER BY id DESC` не использует индекс.

> ⚠️ В SQL `user` обязательно в кавычках — иначе PostgreSQL вернёт `CURRENT_USER` (BUG-094).

---

## 🔌 API ЭНДПОИНТЫ

### Находки (Findings Refactor, v3.9.0–v3.13.27)

| Метод | Эндпоинт | Роль | Назначение |
|-------|----------|------|------------|
| GET | `/api/findings` | `require_auth` | Список (маскированное, фильтры) |
| GET | `/api/findings/{id}` | `require_auth` | Детали (маскированное) |
| POST | `/api/findings/{id}/reveal` | Auditor+ | Расшифровка (с аудитом) |
| PATCH | `/api/findings/{id}` | Auditor+ | Статус (confirmed/false_positive/archived/new) |
| POST | `/api/findings/bulk` | Auditor+ | Массовое обновление (до 1000) |
| GET | `/api/findings/stats` | `require_auth` | Статистика |
| GET | `/api/findings/false-positives` | Auditor+ | Список FP |
| GET | `/api/findings/{id}/fragment` | Auditor+ | Фрагмент (embedded / full-image / bbox) |
| GET | `/api/findings/{id}/fragment/hash` | Auditor+ | Метаданные фрагмента |
| GET | `/api/findings/export` | Auditor+ | Экспорт (CSV/JSON) |
| DELETE | `/api/findings/{id}` | Admin | Удалить (с аудитом) |
| POST | `/api/findings/check-fingerprints` | публичный | Проверка FP (machine-API) |
| GET | `/api/findings/count` | `require_auth` | Legacy-счётчик (WebUI) |

### Фильтры `GET /api/findings`

| Параметр | Тип | Pattern / Ограничение |
|----------|-----|-----------------------|
| `resource_id` | int | — |
| `task_id` | int | — |
| `status` | str | `new` / `confirmed` / `false_positive` / `archived` |
| `finding_type` | str | `pii` / `credentials` / `code` |
| `category` | str | CSV: `phone`, `email`; legacy: `pii`, `credentials`, `code` → `finding_type` |
| `severity` | str | — |
| `detector` | str | 🆕 BUG-090 (v3.13.22) |
| `fragment_type` | str | 🆕 BUG-090 (v3.13.22) |
| `search` | str | 🆕 ILIKE по `fragment_path` / `match_text_masked` / `line_text_masked` |
| `limit` | int | `_clamp_int` (1..1000), default 100 |
| `offset` | int | `_clamp_int` (0..10M), default 0 |
| `order_by` | str | `^(first_seen_at\|last_seen_at\|severity\|line_number\|id)$` |
| `order` | str | `^(asc\|desc)$`, default `desc` |

**FastAPI 0.137 gotcha:** `BeforeValidator` в `Annotated` теряется, если `Query(...)` указан в `default` (`create_model_field` берёт annotation из `field_info`) → `Query()` объявлен **внутри** `Annotated`, дефолт через `=`; числовые `le`/`ge` несовместимы с `Optional[int]` (TypeError на None) → `_clamp_int()`.

**Формат ответа списка** — плоский массив, не `{items, total}`:

- `X-Total-Count` — заголовок (BACKLOG-067).

Поля: `id`, `resource_id`, `task_id`, `finding_type`, `category`, `severity`, `fragment_type`, `line_number`, `match_text` (masked), `line_text` (masked), `context_before` / `context_after` (masked), `has_fragment`, `bounding_box`, `byte_offset`, `byte_length`, `file_path`, `value`, `status`, `reviewed_by`, `reviewed_at`, `comment`, `confidence`, `detector`, `first_seen_at`, `last_seen_at`, `has_encrypted`, `can_reveal`, `encryption_key_id`.

- `fingerprint` — **не отдаётся наружу** (только через `check-fingerprints`).
- `match_text_encrypted` / `line_text_encrypted` — **не отдаются**.

### Сканер

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| POST | `/api/scanner/register` | Регистрация |
| POST | `/api/scanner/heartbeat` | Heartbeat (`scanner_id`, `task_id`, `progress`) |
| POST | `/api/scanner/tasks/{id}/results` | Результаты (`findings` + `fragment_base64`) |
| GET | `/api/scanner` | Список всех сканеров (WebUI-совместимый) |
| GET | `/api/scanner/{id}` | Статус одного сканера |
| DELETE | `/api/scanner/{id}` | Удалить регистрацию сканера |
| GET | `/api/scanner/tasks/assigned?scanner_id=N` | Назначенные сканеру задачи |
| GET | `/api/scanner/tasks/pending?scanner_id=N` | Задачи для сканера |
| POST | `/api/scanner/tasks/{id}/fail` | Пометить задачу failed |
| POST | `/api/scanner/tasks/{id}/cancel` | Отменить задачу |
| POST | `/api/scanner/tasks/{id}/release` | Вернуть задачу в пул |

> ⚠️ `task_id` в heartbeat — это **id текущей (assigned/running) задачи**, а не `current_task_id`: `POST /api/scanner/heartbeat` ищет активную задачу через `task_id`/`current_task_id`, оба допустимы. Пустое значение = idle.
> ⚠️ Все `/api/scanner/*` — **machine-эндпоинты**, публичные в terms of JWT (машина аутентифицируется опциональным mTLS; в `strict` без клиентского сертификата → 401).

### Аутентификация

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| POST | `/api/auth/login` | Логин (`auth_login` / `auth_failed`) |
| POST | `/api/auth/refresh` | Обновление токена |
| POST | `/api/auth/logout` | Выход (`auth_logout`) |
| GET | `/api/auth/me` | Информация о пользователе |
| GET | `/api/auth/mode` | Режим аутентификации |
| GET | `/api/auth/check` | Проверка прав роли (WebUI-совместимый) |
| GET/POST/PUT/DELETE | `/api/auth/users` | CRUD пользователей (Admin, `user_created`/`user_updated`/`user_deleted`) |
| PUT | `/api/auth/users/{id}/roles` | `role_assigned` / `role_revoked` |
| POST | `/api/auth/change-password` | `user_password_changed` (self) |
| GET/POST | `/api/auth/roles` | Список/создание ролей (Admin) |

> ⚠️ `PUT/DELETE /api/auth/roles/{id}` в коде **нет** — только `GET /api/auth/roles` и `POST /api/auth/roles`. Удаление/изменение ролей не поддержано.

### Каталог

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| GET | `/api/catalog/resources` | Ресурсы (директории) |
| GET | `/api/catalog/resources/{id}/findings` | Строки файла с находками |
| GET | `/api/catalog/tree` | Дерево с находками на уровне строк |

### Аудит

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| POST | `/api/audit/agents/register` | Регистрация агента → `agent_id` |
| POST | `/api/audit/agents/heartbeat` | Heartbeat агентов |
| POST | `/api/audit/events` | Приём событий (батч) |
| GET | `/api/audit` | Список событий (`event_source`, `event_type`, user) |
| GET | `/api/audit/stats` | Агрегаты (`by_source`, `by_type`) |

### Архивация

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| GET | `/api/retention/policies` | Политики хранения |
| POST | `/api/retention/run` | Ручной запуск |
| GET | `/api/retention/status` | Статус |
| POST | `/api/retention/export` | Экспорт (JSON/CSV) |

### Метрики

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| GET | `/metrics` | Prometheus-метрики Manager (публичный, вне `/api/*`) |
| GET | `/api/health` | Healthcheck (исключён из rate-limit) |

---

## 📈 МОНИТОРИНГ

### Метрики

| Компонент | Порт | Ключевые метрики |
|-----------|------|------------------|
| Manager | `:8000/metrics` | `dcap_http_*`, `dcap_tasks_total`, `dcap_findings_total`, `dcap_scanner_*`, `dcap_celery_queue_size` |
| Scanner | `:9101` | `dcap_scanner_files_scanned_total`, `dcap_scanner_findings_total`, `dcap_scanner_errors_total`, `dcap_scanner_current_task` |
| Linux-агент | `:9102` | `dcap_linux_*` |
| S3-агент | `:9103` | `dcap_s3_*` |
| Celery | `:9808` | (celery-exporter) |
| PostgreSQL | `:9187` | (postgres-exporter) |
| Redis | `:9121` | (redis-exporter) |

### Heartbeat-thread (v3.7.0, backoff v3.13.20)

`scanner/src/heartbeat.py` — daemon, interval 30 с, fail-open.

```
POST /api/scanner/heartbeat с {scanner_id, status, current_task_id, progress}
```

> ⚠️ **Важное уточнение:** `_mark_stale_scanners` **переводит задачи в `failed`** у сканеров без heartbeat. Активной (`assigned`/`running`) задачей защищается только **сам сканер** (`status='assigned'`), не задача — поэтому «сканер не станет inactive при длинной задаче» верно, а «задание не будет провалено» — нет.

**Backoff (BUG-080, v3.13.20):** `BACKOFF_STEPS = [5, 10, 30, 60, 120]`; фейлы — DEBUG, WARNING на 1-м и каждые 5; `_stop.wait()` вместо `time.sleep()`; INFO «Heartbeat restored after N failure(s)».

### Prometheus targets (6/6 up)

```text
http://celery_exporter:9808/metrics       up
http://manager:8000/metrics               up
http://postgres_exporter:9187/metrics     up
http://redis_exporter:9121/metrics        up
http://s3_agent:9103/metrics              up
http://host.docker.internal:9101/metrics  up  (scanner, на хосте)
```

### Алерты

| Алерт | Условие | Severity |
|-------|---------|----------|
| `ScannerInactive` | `dcap_scanner_heartbeat_age_seconds > 120` | warning |
| `TaskFailed` | `increase(dcap_tasks_total{status="failed"}[5m]) > 0` | critical |
| `HighErrorRate` | `rate(dcap_http_requests_total{status=~"5.."}[5m]) > 0.05` | critical |
| `CeleryQueueBacklog` | `dcap_celery_queue_size > 100` | warning |

### Аудит: аудит-логи партиционированы

> ⚠️ Диагностические запросы: `ORDER BY created_at DESC, id DESC` (а не `ORDER BY id DESC`) — из-за партиционирования.

---

## 🗄️ RETENTION (v3.13.27)

### API

| Метод | Эндпоинт | Роль | Назначение |
|---|---|---|---|
| GET | `/api/retention/policies` | Admin | Политики хранения |
| GET | `/api/retention/status` | Admin | Текущий статус (`last_run`, `running`) |
| POST | `/api/retention/run` | Admin | Ручной запуск (**sync** в Manager), `?dry_run=true` |
| POST | `/api/retention/start` | Admin | Запуск через **Celery** (`run_retention.delay`) |
| POST | `/api/retention/export` | Admin | Экспорт архива в файл |

Все 5 эндпоинтов — `require_admin`.

**`run` vs `start`:**
- `run` — **синхронно** в процессе Manager (для dry-run и отладки).
- `start` — **асинхронно** через Celery (штатный путь, очередь `retention`).

> ⚠️ Тест, вызывающий только `run`, **не покрывает** Celery-путь: в процессе Manager `auth.models` импортирован, и BUG-102 там не воспроизводился.

### Политики (default, `manager/config/config.json` → `retention`)

| Категория | TTL | Архив | Примечание |
|---|---|---|---|
| `audit_events` | 90 дней | ✅ → `audit_logs_archive` | Гейт `archive_enabled: true`; архив живёт ещё 365 дней |
| `findings` | 180 дней | ✅ → `findings_archive` | **Без гейта** — архивируется всегда (TEST-NOTE-7.3) |
| `tasks` | 30 дней | ❌ | `scan_tasks`, только завершённые |
| `logs` | rotate 30 дней / 100 МБ | — | Файловые логи |

**Global:** `enabled: true`, `interval_hours: 24`.

Порядок шагов (`retention/runtime.py`): `archive_audit → archive_findings → clean_archive → clean_tasks → export → rotate_logs`.

### Перемещение, а не копирование

`_move_to_archive()` делает `add(archive)` + `delete(source)` — запись из основной таблицы **удаляется**, а не остаётся. Отсюда фактический срок жизни данных:

- `audit_events`: 90 дней в `audit_logs` → далее `audit_logs_archive` → удаление по `archive_ttl_days` (365).
- `findings`: 180 дней в `findings` → далее `findings_archive` → удаление по тем же 365 дням.
- Основная `audit_logs` массовым DELETE **не чистится** — только перемещением строк.

### Партиционирование `audit_logs`

- RANGE по `created_at`, **13 месяцев + default**.
- PK: `(created_at, id)`. Из-за этого `ORDER BY id DESC` не использует индекс — для больших выборок `ORDER BY created_at DESC, id DESC`.
- Миграция `001_initial_postgres` создаёт только 4 партиции (`AUDIT_PARTITIONS_HEAD = 3` + текущая); остальные добирает `ensure_audit_log_partitions(months_ahead=12)` при старте.
- ⚠️ **`DROP PARTITION` в retention не используется** — в коде его нет вообще; удаление партиций есть только в `downgrade` миграции `001`. Архивная очистка — bulk `DELETE WHERE created_at < cutoff`.

### Архивные таблицы

- `audit_logs_archive` — копия схемы `audit_logs` + `archived_at`; экспортируется в JSON/CSV.
- `findings_archive` — **legacy-схема** (до Findings Refactor v3.9.0: `file_path`, `subcategory`, `value`, `context`). Активно используется как цель архивации, очистки и экспорта; маппинг **lossy**: `subcategory` всегда `NULL`, в `context` попадает лишь `context_before_masked`, поля `fingerprint`/`fragment_*`/шифрование теряются. Удаление — **BACKLOG-065** (вместе с `findings_old`).

### BUG-102 (v3.13.27)

**Проблема:** Celery-воркер падал на `Mapper[Finding] ... 'User' failed to locate a name`.

**Причина:** `Finding.reviewer = relationship("User", ...)` — `User` в `manager.src.auth.models`, но в Celery-контексте не импортирован (та же проблема, что BUG-096).

**Фикс:** импорт `User` из `auth.models` в **6 модулях**:
- `workers/tasks.py` — основная точка гарантии
- `workers/celery_app.py` (+ `configure_mappers()` — fail-fast на старте)
- `retention/archiver.py`
- `retention/cleaner.py`
- `retention/exporter.py`
- `services/access_service.py` — «проверить заодно»

**Каскадность:** после первого сбоя `Mapper[Finding]` все последующие mapper-инициализации падают. `run_retention` не поднимает исключение — каждый шаг в `try/except` возвращает `{"error": "..."}`. Итог: `status: completed`, но работы нет.

### Состояние retention

- `last_run` / `last_result` — **в памяти процесса** (TEST-NOTE-7.2).
- Персистятся в `manager/data/retention_state.json`, но у `celery_worker` в compose **нет томов** — файл остаётся в эфемерном слое контейнера. `manager` монтирует `manager_data:/app/data`, поэтому состояние воркера Manager **не видит**, и оно теряется при пересоздании контейнера.

### ⚠️ Заметки

- **TEST-NOTE-7.1:** `findings_archive` — legacy-схема, маппинг lossy.
- **TEST-NOTE-7.2:** Manager не видит состояние воркера.
- **TEST-NOTE-7.3:** `findings.ttl_days=180` — архивируются **без** гейта `archive_enabled` (в отличие от audit); «архивации не видно» на свежих данных, а не из-за выключенного фича.
- **TEST-NOTE-7.4:** `run` (sync) ≠ `start` (Celery).
- **TEST-NOTE-7.5:** Flower не видит worker'ов (dev-инструмент).

---

## 📤 SIEM-ИНТЕГРАЦИЯ (план, v3.1.0+)

> ⚠️ **Статус: НЕ РЕАЛИЗОВАНО.** Каталога `manager/src/siem/` в репозитории **нет**, метрик `dcap_siem_*` тоже нет. Раздел описывает план (BACKLOG), а не текущее состояние. События ИБ сейчас хранятся только в `audit_logs` в БД Manager.

### Назначение

Передача событий ИБ из DCAP в SIEM для централизованного мониторинга, корреляции, compliance (152-ФЗ, GDPR, PCI DSS), алертинга.

### Форматы

| Формат | Протокол | SIEM |
|--------|----------|------|
| Syslog (RFC 5424) | UDP / TCP / TLS | ArcSight, QRadar, MaxPatrol, Wazuh, rsyslog |
| JSON | HTTP/HTTPS (webhook) | Splunk HEC, Elastic, Kibana, кастомные SIEM |

### Планируемые события ИБ

| Источник | Событие | Severity |
|----------|---------|----------|
| Findings | `finding_detected` | по severity |
| Findings | `finding_revealed` | high |
| Findings | `finding_confirmed` | medium |
| Findings | `finding_false_positive` | low |
| Findings | `finding_archived` | low |
| Findings | `finding_deleted` | medium |
| Scanner | `scan_started` / `scan_completed` | info |
| Scanner | `scan_failed` / `scanner_inactive` | high / warning |
| Audit | `auth_login` / `auth_failed` | info / medium |
| Audit | `user_created` / `role_changed` | medium |
| Audit | `fragment_accessed` | medium |
| Retention | `retention_run` | info |

> ⚠️ `scanner_inactive` и `retention_run` как `event_type` в `audit_logs` сейчас **не пишутся** — `_mark_stale_scanners` и retention только логируются в logger/stdout.

### Архитектура (план)

```text
Manager (события) → EventGenerator → SIEMConnector
                                       ├── SyslogSender (UDP/TCP/TLS)
                                       └── JSONSender (HTTP/HTTPS)
                                              ├─→ Dead-letter queue (Redis) при ошибке
                                              └─→ Retry с backoff
```

### Планируемые модули

```text
manager/src/siem/              # ⚠️ не существует
├── generator.py               # генерация событий из findings/audit
├── config.py                  # конфигурация (Syslog/JSON)
├── senders/
│   ├── syslog_sender.py       # RFC 5424 (UDP/TCP/TLS)
│   └── json_sender.py         # HTTP/HTTPS webhook
└── queue.py                   # dead-letter + retry
```

### Ключевые свойства (план)

- Асинхронная отправка через Celery.
- Retry с экспоненциальным backoff.
- Dead-letter queue (Redis) при недоступности SIEM.
- Метрики: `dcap_siem_events_sent_total`, `dcap_siem_events_failed_total`.

### Безопасность (план)

Только маскированные `match_text` — без reveal.

`match_text_encrypted` не отправляется.

### WebUI (BACKLOG-072)

> ⚠️ Страницы `/settings/siem` в `webui/templates/` **нет** — бэклог.

Страница `/settings/siem`:

- Формы: Syslog (host, port, protocol, TLS), JSON (URL, token).
- Выбор событий (чекбоксы).
- Кнопка «Test» — тестовое событие.
- Метрики — отправлено/ошибок за 24ч.

### v4.0.0+

- Kafka / Kinesis — потоковая передача.
- CEF / LEEF — если потребуется.

---

## ⚡ ОПТИМИЗАЦИЯ ПРОИЗВОДИТЕЛЬНОСТИ (план, v3.1.0+)

> ⚠️ **Статус: НЕ РЕАЛИЗОВАНО.** В репозитории **нет** ни `Cargo.toml`/`*.rs`, ни `*.pyx`/`*.so`, ни `scanner-rust/`, ни `scanner-python/`. Приведённые ниже цифры — оценки из BACKLOG, а не замеры.

### Проблема

Python-сканер — узкое место на 100k+ строках. Профилирование: ~60% в Presidio/spaCy, ~40% — в собственных regex-фильтрах и маскировании.

### Стратегия: Cython + Rust (гибрид)

| Компонент | Технология | Прирост (оценка) | Приоритет |
|-----------|------------|------------------|-----------|
| Regex-фильтры (`_filter_url_over_email`, `_filter_spacy_noise`) | Cython + cre/re2 | 3–10× | BACKLOG-090 |
| Маскирование (`mask_context`, `_CONTEXT_PATTERNS`) | Cython | 3–5× | BACKLOG-089 |
| Entropy-анализ | Cython | 5–10× | BACKLOG-089 |
| Prefilter | Cython | 3–5× | BACKLOG-089 |
| Обход ФС (CIFS/NFS) | Rust (pavao, nfs-rs) | нативно | BACKLOG-036 |
| Параллелизм | Rust (rayon) | N×CPU | BACKLOG-036 |
| OCR (Tesseract) | Python (CLI) | — | — |
| Presidio/spaCy | Python (уже Cython внутри) | — | — |

### Cython vs Rust

**Cython:**

- Низкий порог входа (Python + типы).
- Плавная интеграция в существующий код.
- 3–10× на своих функциях (потолок ~5×, редко 10×).
- Ограничен GIL (частично — `nogil`).
- Простой rollback (`.pyx` → `.py`).
- Для существующего Python-кода.

**Rust:**

- Высокий порог входа (ownership, borrow checker).
- Отдельный модуль + FFI/IPC.
- 10–50×, близко к C.
- Нативный параллелизм (rayon, tokio).
- Готовые крейты для сетевых ФС (pavao, nfs-rs).
- Для новых компонентов (сети, IPC).

### Быстрые regex-движки (BACKLOG-090)

| Библиотека | Технология | Особенность |
|-------------|------------|-------------|
| `cre` | Cython + GLib PCRE | Освобождает GIL → распараллеливание regex без Rust |
| `re2` | Google RE2 | Линейное время, устойчивость к ReDoS |
| `esmre` | Cython | Индекс обязательных подстрок — быстрый отсев несовпадающих регулярок |
| `simple-fast-regex` | Python + Rust | Можно обернуть через Cython |

> **Важно:** «цитонизировать» `re.py` напрямую не даст прироста — движок `re` уже на C (`_sre`). Нужно менять движок (`cre`, `re2`) или использовать Cython + библиотеки.

### Ожидаемый эффект (оценка)

- 30–50% общего ускорения сканирования от Cython.
- Дополнительно от параллелизма (Rust) на многоядерных CPU.
- Без переписывания Presidio/spaCy.

### TruffleHog (BACKLOG-091, v3.1.0+)

**Идея:** верификация credentials через API провайдера (AWS, GitHub, Slack, Stripe) — «рабочий» / «просроченный» / «unverified».

- **Плюс:** снижение FP на `high_entropy`, приоритизация подтверждённых.
- **Ограничения:** ресурсоёмкий (4+ CPU, 16 ГБ RAM), требует egress.
- **Не заменяет DCAP** — другая ниша (code secrets vs DLP).

---

## 📝 КЛЮЧЕВЫЕ РЕШЕНИЯ

### Архитектурные

| Решение | Обоснование |
|---------|-------------|
| Гибридная аутентификация | local + AD, плавный переход в enterprise |
| mTLS relaxed/strict | Обратная совместимость с dev |
| Secret Scanner интеграция | FP-фильтры, расширенные типы |
| Масштабирование (PG/Redis/Celery) | Celery Beat, партиционированные audit_logs |
| Scanner на хосте (не Docker) | Docker не может динамически монтировать пути |
| Heartbeat-thread | Отдельный поток — сканер не «inactive» |
| Findings = строка/фрагмент | Нельзя обработать результаты, если находка = файл |
| Гибридное хранение (masked + encrypted) | Безопасность + удобство анализа |
| Расшифровка — только Auditor, с аудитом | Минимизация доступа + compliance |
| HMAC-fingerprint | Защита от brute-force по fingerprint |
| MD5 → SHA-256 в legacy | MD5 криптографически сломан (BACKLOG-066) |
| Встроенные фрагменты в БД | «Файл удалили — доказательство осталось» (BACKLOG-086) |
| Аудит PATCH/bulk/DELETE findings | Compliance 152-ФЗ / GDPR / PCI DSS (BUG-101, 101b) |
| Cython + Rust (гибрид, **план**) | Cython — для горячих точек Python, Rust — для сетей/параллелизма |
| SIEM-модуль `manager/src/siem/` (**план**) | Только CIFS/NFS + параллелизм (BACKLOG-036); классификаторы/PII — Python |
| Retention: чистка по `created_at` | `DROP PARTITION` не используется — archive-таблицы + bulk DELETE |

### Технические

| Решение | Обоснование |
|---------|-------------|
| PostgreSQL + Redis в Docker | Production-готовность |
| ENV-ключи (не Docker Secrets) | Упрощение ротации, единый источник (TASK-018); `SecretsManager` (`core/secrets.py`) с приоритетом `/run/secrets/` → env → default написан, но **вызовов в коде нет** — фактически везде читается `os.getenv` |
| Единый формат событий (UnifiedEvent) | Унификация источников |
| Текстовый лог-отчёт | Безопасный для выкладки |
| Prometheus + Grafana + Alertmanager | Стандартный стек |
| spaCy-модели sm | Жёстко зашито в `pii_classifier` |
| spnego убран из requirements | Нет на PyPI, реальный — pyspnego |
| AES-256-GCM для находок | Стандарт для шифрования данных |
| Pytest + docker-compose.test.yml | Изолированные тесты |
| `_clamp_int` + OptInt | Валидация числовых query-параметров (BUG-084, 099) |
| `forwarded_headers` | WebUI-прокси: X-Total-Count, X-Fragment-*, Content-Disposition (BUG-087) |
| `fetch` + Blob + Bearer | Бинарные данные (fragment, export) — не `<img>`/`window.location` (BUG-088, 093) |
| `SubmitStatus` (OK/RETRY/LOST) | Оффлайн-буфер: 404/410 → LOST (пачка отбрасывается) (BUG-097) |
| `_CONTEXT_PATTERNS` | `mask_context`: 22 паттерна, специфичные раньше generic (BUG-086) |
| `_log_finding_status_change` | Единая точка аудита PATCH/bulk; без commit — batch (BUG-101) |
| `_apply_status` | Единая функция PATCH/bulk; сброс review при new (BUG-100) |
| BUG-102: импорт `User` в 6 модулях | SQLAlchemy mapper init в Celery-контексте (`Finding.reviewer`) |
| `run` (sync) ≠ `start` (Celery) | Dry-run через API без очереди; Celery-путь — отдельно |

---

## ⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ

| Ограничение | Описание | План |
|-------------|----------|------|
| `/metrics` публичный | Нет JWT/basic_auth | BACKLOG-044 |
| Прогресс сканера | Не виден в WebUI | BACKLOG-043 (🔄) |
| NOT NULL поля | Возможны скрытые баги | BACKLOG-039 |
| Параллельный батч | Форк один (OCRWorker) | BACKLOG-040 (v3.1.0) |
| NFS на Windows | Ограниченный клиент | Решено в nfs-rs (v3.1.0, **плана нет в коде**) |
| Presidio | Медленный на 100k+ строк | BACKLOG-063 (v3.1.0) |
| `findings_old` | Legacy-таблица в БД (только PG-миграция) | BACKLOG-065 |
| WebUI legacy Findings | Деградация до 40.3 | BACKLOG-061 (🔄) |
| `order_by=severity` | Лексикографический порядок (не семантический) | BUG-083 (v3.1.0) |
| `/fragment` для `text_line` | 400 (не 404 + пояснение) | BUG-085 (v3.1.0) |
| OCR bbox | `None` до v3.1.0 (Tesseract без tsv) | BACKLOG-085 |
| Сканер не перезапускается | После рестарта Docker/хоста | TEST-NOTE-5.8 (v3.1.0) |
| `findings_archive` | Архив findings (маппинг lossy, `decrypted_match_text` теряется) | BACKLOG-065 |
| Retention state | Не виден Manager'у (файл в эфемерном слое воркера) | TEST-NOTE-7.2 |
| Findings без гейта `archive_enabled` | Архивируются всегда; audit — только по флагу | TEST-NOTE-7.3 |
| SIEM не реализован | Каталога `manager/src/siem/` нет | BACKLOG (план) |
| Rust/Cython не реализованы | Нет `.rs`/`.pyx`/`Cargo.toml` | BACKLOG-036, 089, 090 |
| Нет `LICENSE` | Файл отсутствует в репозитории | — |

---

## 📘 АДМИН-РУКОВОДСТВО (Дни 42.1–42.4)

Принцип: **документация = проверенный факт**. Кодер валидирует каждый раздел по реальному коду.

> ⚠️ Фактически в `docs/admin-guide/` лежат **только 4 файла**: `04-authentication.md`, `05-security.md`, `06-scanner.md`, `10-troubleshooting.md`. Остальное — план (BACKLOG).

### Структура docs/admin-guide/ (план)

| Файл | Описание | Статус |
|------|----------|--------|
| `README.md` | Оглавление + быстрый старт | ❌ нет |
| `01-architecture.md` | Обзор компонентов | ❌ нет |
| `02-installation.md` | Установка (Docker + локально) | ❌ нет |
| `03-configuration.md` | Все конфиги, env-переменные | ❌ нет |
| `04-authentication.md` | local/AD/hybrid, RBAC | ✅ есть |
| `05-security.md` | mTLS, ключи, секреты, аудит findings/auth, маскирование контекстов | ✅ есть |
| `06-scanner.md` | Настройка, задания, FP | ✅ есть |
| `07-agents.md` | Windows/Linux/S3 | ❌ нет |
| `08-monitoring.md` | Метрики, алерты | ❌ нет |
| `09-retention.md` | Архивация | ❌ нет |
| `10-troubleshooting.md` | Решение проблем (в т.ч. `user` без кавычек, stale `__pycache__`, аудит auth) | ✅ есть |
| `11-faq.md` | Частые вопросы | ❌ нет |

### Разбивка (план)

| День | Разделы |
|------|---------|
| 42.1 | Установка + конфигурация |
| 42.2 | Аутентификация + безопасность |
| 42.3 | Сканер + агенты |
| 42.4 | Мониторинг + retention + troubleshooting + FAQ |

---

Актуально на: 01.10.2026
Версия архитектуры: v3.13.27 (в процессе — Блок 5, 7 закрыты)

---

## 📌 Что изменилось в ARCHITECTURE.md

| # | Раздел | Что добавлено |
|---|--------|---------------|
| 1 | Версия | v3.11.0 → **v3.13.26** |
| 2 | `manager/src/auth/` | Добавлен `audit.py` (BUG-095) |
| 3 | `manager/src/db/migrations/` | 001…**005** (было 003) |
| 4 | `scanner-rust/` | Уточнение: **ТОЛЬКО CIFS/NFS + параллелизм** (BACKLOG-036) |
| 5 | Секция «Шифрование находок» | Добавлена **«Маскирование контекстов»** (`_CONTEXT_PATTERNS`, 22 паттерна) |
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
| 21 | Версия | v3.13.26 → **v3.13.27** (Блок 7 закрыт) |
| 22 | Новая секция | **«Retention (v3.13.27)»** — API, политики, партиционирование, архивные таблицы, BUG-102 |
| 23 | Ревизия v3.13.27 | **Весь файл пересобран по коду**: восстановлен Markdown (заголовки, pipe-таблицы, fenced blocks), удалены tab-таблицы и литералы `text` |
| 24 | Дерево проекта | Убраны несуществующие `scanner-rust/`, `scanner-python/`, `.github/`, `webui/src/`, `CONTRIBUTING.md`, `LICENSE`, `docs/architecture.png`; добавлены реальные `modes/`, `offline/`, `utils/`, `pyproject.toml`, `Diagram-*.png`; тесты 301 → **317** |
| 25 | Маскирование | Таблица `MASK_RULES` приведена к коду: **19 категорий** в сканере / **11** в Manager, исправлены примеры масок |
| 26 | SIEM, Оптимизация | Помечены как **план** (нет `manager/src/siem/`, `.rs`/`.pyx`/`Cargo.toml`) |
| 27 | API | Добавлены отсутствующие scanner-эндпоинты (`/api/scanner`, `DELETE`, `tasks/assigned`, `fail`/`cancel`/`release`), audit-эндпоинты агентов; `PUT/DELETE /api/auth/roles/{id}` помечен как несуществующий |
| 28 | Модель `Finding` | Добавлены `resource`/`task`/`reviewer` relationship; фрагментные колонки отнесены к миграции **005**, не 003; уточнено, что `fragment_data` — base64-decoded bytes |
| 29 | Дедупликация | Формула приведена к коду: `file_path\|line\|match\|category`; отмечено, что `legacy_fingerprint` Manager не читает |
| 30 | `findings_old` | Уточнено: создаётся только при upgrade со старой схемы и **только на PostgreSQL** |
| 31 | Heartbeat | `_mark_stale_scanners` переводит `assigned`/`running` задачи в `failed` (защищён только сам сканер) |
| 32 | Секция mTLS | Перечислены реальные `public_paths`/`machine_prefixes`, `ssl_cert_reqs=CERT_OPTIONAL` |
| 33 | Ключевые решения | `SecretsManager` отмечен как **написанный, но не вызываемый** (везде `os.getenv`) |
| 34 | Админ-руководство | Таблица статусов: реально есть только 4 файла из 12 |
