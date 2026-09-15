# 🏗️ ARCHITECTURE.md — Архитектура DCAP

> **Обновляется архитектором при изменениях архитектуры.**
> Текущее состояние — в `STATE.md`. План и бэклог — в `ROADMAP.md`.

**Обновлено:** 12.09.2026
**Версия архитектуры:** v3.11.0 (в процессе — WebUI Findings)

---

## 🏗️ СТРУКТУРА ПРОЕКТА

```
dcap-system/
├── manager/                      # FastAPI :8000 (control-plane)
│   └── src/
│       ├── main.py               # точка входа
│       ├── api/                  # resources, tasks, findings, catalog, scanner,
│       │                         # permissions, audit, auth, retention, webui
│       ├── auth/                 # JWT, AD, RBAC
│       ├── core/                 # security (mTLS), secrets, rate_limit,
│       │                         # encryption.py (Findings AES-256-GCM)
│       ├── retention/            # архивация и очистка данных
│       ├── connectors/
│       │   ├── permissions/      # local/ad/mixed
│       │   └── audit/            # windows_audit
│       ├── services/             # access_service, access_config
│       ├── db/                   # models.py, session.py, init_roles.py
│       │   └── migrations/       # Alembic (001, 002, 003)
│       ├── cache/                # redis_client.py (кэш/rate-limit, fail-open)
│       ├── workers/              # Celery app/tasks/beat
│       └── metrics.py            # Prometheus
│
├── scanner/                      # Python-сканер (тяжёлый, на хосте)
│   └── src/
│       ├── managed_scanner.py
│       ├── heartbeat.py          # HeartbeatThread
│       ├── metrics.py            # Prometheus :9101
│       ├── finding.py            # 🆕 dataclass Finding (строка/фрагмент)
│       ├── encryption.py         # 🆕 AES-256-GCM + HMAC + маскирование
│       ├── core/                 # orchestrator, state_manager, metrics
│       ├── classifiers/          # PII, Credentials, Code
│       │                         # 🆕 scan_line(line, num) → list[Finding]
│       ├── connectors/           # filesystem.py (🆕 построчное чтение + контекст)
│       └── handlers/             # finding_collector.py
│
├── scanner-rust/                 # 🆕 v3.1.0: Rust-ядро (BACKLOG-036)
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       ├── walker.rs             # обход ФС (local + CIFS + NFS)
│       ├── prefilter.rs          # regex-префильтр
│       ├── entropy.rs            # entropy-анализ
│       ├── bridge/ipc.rs         # JSON-RPC к Python sidecar
│       ├── cifs.rs               # pavao + libsmbclient
│       ├── nfs.rs                # nfs-rs (авто-монтирование)
│       ├── heartbeat.rs
│       ├── metrics.rs
│       └── reporter.rs
│
├── scanner-python/               # 🆕 v3.1.0: Python sidecar (BACKLOG-036)
│   ├── src/
│   │   ├── sidecar.py            # IPC-сервер (JSON-RPC)
│   │   ├── ocr.py                # Tesseract wrapper
│   │   ├── pii.py                # Presidio wrapper
│   │   └── credentials.py
│   └── requirements.txt
│
├── audit-agent-windows/          # Windows-агент (лёгкий)
│   ├── main.py, collector.py, buffer.py, sender.py
│   ├── service.py                # Windows-служба
│   └── config.json
│
├── audit-agent-linux/            # Linux-агент (inotify)
│   ├── main.py, collector.py, buffer.py, sender.py, heartbeat.py
│   ├── metrics.py                # Prometheus :9102
│   ├── service/                  # systemd unit
│   └── start.sh, stop.sh, status.sh
│
├── audit-agent-s3/               # S3/MinIO агент
│   ├── src/                      # main, collector, buffer, sender,
│   │                             # converters, heartbeat, state, metrics
│   ├── config/
│   ├── scripts/
│   └── tests/
│
├── webui/                        # каноничный UI :8001
│   ├── src/
│   │   ├── main.py               # FastAPI приложение (Jinja2)
│   │   ├── api/                  # routes.py (прокси в Manager)
│   │   └── static/               # CSS, JS, vendor
│   ├── templates/                # Jinja2 шаблоны
│   │                             # 🆕 findings.html, finding_detail.html,
│   │                             #    catalog.html, false_positives.html
│   └── config/config.json
│
├── shared/
│   ├── event_schema.py           # UnifiedEvent (Pydantic)
│   ├── cert_utils.py
│   └── security.py
│
├── scripts/
│   ├── generate_certs.py, rotate_certs.py
│   ├── generate_findings_keys.py # 🆕 ключи шифрования находок
│   ├── migrate_sqlite_to_postgres.py
│   ├── deploy.sh, stop.sh, logs.sh, status.sh, healthcheck.sh
│   ├── monitoring-status.sh
│   ├── test-up.sh, test-down.sh, run-tests.sh
│   └── init_ad_test_data.py
│
├── monitoring/                   # Prometheus/Grafana/Alertmanager
│   ├── prometheus/{prometheus,alerts}.yml
│   ├── alertmanager/alertmanager.yml
│   └── grafana/provisioning/
│
├── tests/
│   ├── unit/                     # 🆕 unit-тесты
│   ├── e2e/                      # E2E тесты
│   ├── chaos/                    # Chaos тесты
│   ├── load/                     # Нагрузочные
│   └── fixtures/                 # Общие фикстуры
│
├── docs/
│   ├── admin-guide/              # 🆕 руководство администратора (42.1-42.4)
│   │   ├── README.md
│   │   ├── 01-architecture.md
│   │   ├── 02-installation.md
│   │   ├── 03-configuration.md
│   │   ├── 04-authentication.md
│   │   ├── 05-security.md
│   │   ├── 06-scanner.md
│   │   ├── 07-agents.md
│   │   ├── 08-monitoring.md
│   │   ├── 09-retention.md
│   │   ├── 10-troubleshooting.md
│   │   └── 11-faq.md
│   ├── deployment.md
│   ├── monitoring.md
│   ├── testing.md
│   ├── security_checklist.md
│   └── architecture.png          # 🆕 схема архитектуры (Mermaid + иллюстрация)
│
├── .github/
│   └── workflows/                # 🆕 CI/CD
│       ├── ci.yml
│       └── release.yml
│
├── alembic.ini
├── docker-compose.yml
├── docker-compose.prod.yml
├── docker-compose.test.yml       # 🆕 изолированный стек для тестов
├── docker-compose.ad.yml
├── SECURITY.md
├── STATE.md                      # текущее состояние (обновляет кодер)
├── ROADMAP.md                    # план + бэклог
├── ARCHITECTURE.md               # этот файл
├── AGENTS.md                     # инструкции для LLM
├── README.md                     # описание проекта
├── CHANGELOG.md                  # 🆕 история версий
├── CONTRIBUTING.md               # 🆕 как контрибьютить
├── LICENSE                       # 🆕 лицензия
└── requirements-dev.txt          # 🆕 dev-зависимости
```

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
| **Ключ** | Docker Secrets (`/run/secrets/findings_encryption_key`) |
| **HMAC-ключ** | Docker Secrets (`/run/secrets/findings_hmac_key`) |
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

**Аудит расшифровок:**
- Каждый `POST /api/findings/{id}/reveal` → запись в `audit_logs`
- Поля: `action="finding_revealed"`, `finding_id`, `user`, `timestamp`

---

## 📊 МОДЕЛЬ ДАННЫХ: FINDINGS

### Иерархия

```
Resource (файл)
  └── Finding (находка = строка/фрагмент)
        ├── line_number
        ├── match_text (masked + encrypted)
        ├── line_text (masked + encrypted)
        ├── context_before/after
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

    # Дедупликация
    fingerprint = Column(String(64), nullable=False, index=True)   # HMAC-SHA256
    encryption_key_id = Column(String(50), nullable=False)

    # Время
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    # Статус
    status = Column(String(20), default="new", index=True)
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
```

### Дедупликация

- `fingerprint = HMAC-SHA256(file_path + line + match_text + finding_type)` *(реально в коде — `finding_type`, не `category`)*
- Legacy-режим: SHA-256 (не MD5 — BACKLOG-066)
- При повторном скане:
  - `false_positive` → **не создавать**
  - `confirmed` → обновить `last_seen_at`
  - новый → создать `new`
- Сканер проверяет FP батчем: `POST /api/findings/check-fingerprints`

### Типы фрагментов

| Тип | Для чего | Что показывать |
|-----|----------|----------------|
| `text_line` | Текстовые файлы | Строка с совпадением |
| `text_context` | Текстовые файлы | Строка + N строк контекста |
| `image_region` | Изображения, PDF-сканы | Вырезанный фрагмент (PNG) + bounding box |
| `byte_range` | Бинарные | Hex-дамп вокруг offset |

### Архивная таблица

- `findings_old` — старая таблица (файл-уровень), сохраняется для отката (миграция 003)
- Удалить после проверки: BACKLOG-062

---

## 🔌 API ЭНДПОИНТЫ

### Находки (Findings Refactor, v3.9.0)

| Метод | Эндпоинт | Роль | Назначение |
|-------|----------|------|------------|
| GET | `/api/findings` | Viewer+ | Список (маскированное, фильтры) |
| GET | `/api/findings/{id}` | Viewer+ | Детали (маскированное) |
| POST | `/api/findings/{id}/reveal` | **Auditor+** | Расшифровка (с аудитом) |
| PATCH | `/api/findings/{id}` | Auditor+ | Статус (confirmed/false_positive) |
| POST | `/api/findings/bulk` | Auditor+ | Массовое обновление |
| GET | `/api/findings/stats` | Viewer+ | Статистика |
| GET | `/api/findings/false-positives` | Auditor+ | Список FP |
| GET | `/api/findings/{id}/fragment` | Viewer+ | Фрагмент (изображение/hex) |
| GET | `/api/findings/export` | Auditor+ | Экспорт (CSV/JSON) |
| DELETE | `/api/findings/{id}` | Admin | Удалить |
| POST | `/api/findings/check-fingerprints` | **публичный** | Проверка FP перед отправкой (machine) |
| GET | `/api/findings/count` | Viewer+ | Legacy-счётчик (WebUI) |

### Сканер

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| POST | `/api/scanner/heartbeat` | Heartbeat (scanner_id, task_id, progress) |
| POST | `/api/scanner/tasks/{id}/results` | Результаты (новый формат findings) |
| GET | `/api/scanner/{id}` | Статус сканера |

### Каталог

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| GET | `/api/catalog/resources` | Ресурсы (файлы) |
| GET | `/api/catalog/resources/{id}/findings` | Строки файла с находками |
| GET | `/api/catalog/tree` | Дерево с находками на уровне строк |

### Аутентификация

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| POST | `/api/auth/login` | Логин |
| POST | `/api/auth/refresh` | Обновление токена |
| POST | `/api/auth/logout` | Выход |
| GET | `/api/auth/me` | Информация о пользователе |
| GET | `/api/auth/mode` | Режим аутентификации |
| GET/POST/PUT/DELETE | `/api/auth/users` | CRUD пользователей (Admin) |
| GET/POST | `/api/auth/roles` | CRUD ролей (Admin) |

### Архивация

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| GET | `/api/retention/policies` | Политики хранения |
| POST | `/api/retention/run` | Ручной запуск |
| GET | `/api/retention/status` | Статус |
| POST | `/api/retention/export` | Экспорт |

### Метрики

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| GET | `/metrics` | Prometheus-метрики Manager |
| GET | `/api/health` | Healthcheck |

---

## 📈 МОНИТОРИНГ

### Метрики

| Компонент | Порт | Ключевые метрики |
|-----------|------|------------------|
| Manager | :8000/metrics | `dcap_http_*`, `dcap_tasks_total`, `dcap_findings_total`, `dcap_scanner_*`, `dcap_celery_queue_size` |
| Scanner | :9101 | `dcap_scanner_files_scanned_total`, `dcap_scanner_findings_total`, `dcap_scanner_errors_total` |
| Linux-агент | :9102 | `dcap_linux_*` |
| S3-агент | :9103 | `dcap_s3_*` |
| Celery | :9808 | (celery-exporter) |
| PostgreSQL | :9187 | (postgres-exporter) |
| Redis | :9121 | (redis-exporter) |

### Heartbeat-thread (v3.7.0)

- `scanner/src/heartbeat.py` — daemon, interval 30 c, fail-open
- `POST /api/scanner/heartbeat` с `{scanner_id, status, current_task_id, progress}`
- Manager `_mark_stale_scanners` не трогает сканеры с активным заданием

### Алерты

| Алерт | Условие | Severity |
|-------|---------|----------|
| `ScannerInactive` | `dcap_scanner_heartbeat_age_seconds > 120` | warning |
| `TaskFailed` | `increase(dcap_tasks_total{status="failed"}[5m]) > 0` | critical |
| `HighErrorRate` | `rate(dcap_http_requests_total{status=~"5.."}[5m]) > 0.05` | critical |
| `CeleryQueueBacklog` | `dcap_celery_queue_size > 100` | warning |

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
| **Findings = строка/фрагмент** | Нельзя обработать результаты, если находка = файл |
| **Гибридное хранение (masked + encrypted)** | Безопасность + удобство анализа |
| **Расшифровка — только Auditor, с аудитом** | Минимизация доступа + compliance |
| **HMAC-fingerprint** | Защита от brute-force по fingerprint |
| **MD5 → SHA-256 в legacy** | MD5 криптографически сломан (BACKLOG-066) |
| Rust Scanner (v3.1.0) | IPC (JSON-RPC), CIFS `pavao`, NFS `nfs-rs` |

### Технические

| Решение | Обоснование |
|---------|-------------|
| PostgreSQL + Redis в Docker | Production-готовность |
| Docker Secrets | Безопасное хранение ключей и секретов |
| Единый формат событий (UnifiedEvent) | Унификация источников |
| Текстовый лог-отчёт | Безопасный для выкладки |
| Prometheus + Grafana + Alertmanager | Стандартный стек |
| spaCy-модели `sm` | Жёстко зашито в `pii_classifier` |
| `spnego` убран из requirements | Нет на PyPI, реальный — `pyspnego` |
| AES-256-GCM для находок | Стандарт для шифрования данных |
| Pytest + docker-compose.test.yml | Изолированные тесты |

---

## ⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ

| Ограничение | Описание | План |
|-------------|----------|------|
| `/metrics` публичный | Нет JWT/basic_auth | BACKLOG-044 |
| Прогресс сканера | Не виден в WebUI | BACKLOG-043 (🔄 40.3) |
| NOT NULL поля | Возможны скрытые баги | BACKLOG-039 |
| Параллельный батч | Форк один (OCRWorker) | BACKLOG-040 (v3.1.0) |
| NFS на Windows | Ограниченный клиент | Решено в `nfs-rs` (v3.1.0) |
| Presidio | Медленный на 100k+ строк | BACKLOG-063 (v3.1.0) |
| `findings_old` | Legacy-таблица в БД | BACKLOG-062 |
| WebUI legacy Findings | Деградация до 40.3 | BACKLOG-061 (🔄 40.3) |

---

## 📘 АДМИН-РУКОВОДСТВО (Дни 42.1-42.4)

**Принцип:** документация = проверенный факт. Кодер валидирует каждый раздел по реальному коду.

**Структура `docs/admin-guide/`:**
- `README.md` — оглавление + быстрый старт
- `01-architecture.md` — обзор компонентов
- `02-installation.md` — установка (Docker + локально)
- `03-configuration.md` — все конфиги, env-переменные
- `04-authentication.md` — local/AD/hybrid, RBAC
- `05-security.md` — mTLS, ключи, секреты
- `06-scanner.md` — настройка, задания, FP
- `07-agents.md` — Windows/Linux/S3
- `08-monitoring.md` — метрики, алерты
- `09-retention.md` — архивация
- `10-troubleshooting.md` — решение проблем
- `11-faq.md` — частые вопросы

**Разбивка:**
- 42.1 — установка + конфигурация
- 42.2 — аутентификация + безопасность
- 42.3 — сканер + агенты
- 42.4 — мониторинг + retention + troubleshooting + FAQ

---

**Актуально на:** 12.09.2026
**Версия архитектуры:** v3.11.0 (в процессе — WebUI Findings)
📌 Что изменилось
ROADMAP.md
#	Изменение
1	День 40.1 → ✅
2	День 40.2 → ✅
3	BACKLOG-050…055 → ✅
4	Добавлены BACKLOG-061…066
5	Добавлены Дни 42.1-42.4 (админ-руководство)
6	BACKLOG-021 убран из v3.1.0 (дубль)
7	Статистика: v3.0.0 = 35 задач (22 ✅), ИТОГО 83 (49 ✅, 59%)
8	Дедупликация: + finding_type (не category)
9	FP-фильтр: /api/findings/check-fingerprints (не /api/scanner/...)
ARCHITECTURE.md
#	Изменение
1	Версия → v3.11.0
2	Убран scanner/fingerprint.py (в encryption.py)
3	Дедупликация: + finding_type
4	check-fingerprints → /api/findings/...
5	Добавлены: finding.py, encryption.py, admin-guide/, tests/unit/
6	Добавлен findings_old (BACKLOG-062)
7	Добавлен BACKLOG-066 (MD5→SHA-256)
8	Расширены категории маскирования (jwt, ssh, github, slack, database_url)
9	Обновлены «Известные ограничения»
10	Добавлен раздел «Админ-руководство»