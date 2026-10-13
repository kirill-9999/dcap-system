# 🏗️ ARCHITECTURE.md — Архитектура DCAP

> **Обновляется архитектором при изменениях архитектуры.**
> Текущее состояние — в `STATE.md`. План и бэклог — в `ROADMAP.md`.

**Обновлено:** 13.10.2026
**Версия архитектуры:** v3.13.41 (Блок 5, 7, 9 закрыты; S3-коннектор сканера — части 1–4 + fix-bucket + BUG-149 (bucket-фолбэк из path); WebUI-редизайн — этап 1/5 (53.4a) + фиксы (53.4a-доп, 53.4a-доп3 backend-critical, 53.4a-доп4 шрифты, 53.4a-доп5 hotfix-backend); BUG-150 (CASCADE миграция 007); BACKLOG-121 (white .btn-primary); BACKLOG-119 (badge режима на /login))

---

## 🏗️ СТРУКТУРА ПРОЕКТА

```text
dcap-system/
├── manager/ # FastAPI :8000 (control-plane)
│ └── src/
│ ├── main.py # точка входа
│ ├── config.py # загрузка конфига (config.json + env)
│ ├── metrics.py # Prometheus /metrics
│ ├── api/ # resources, tasks, findings (+schemas_findings),
│ │ # catalog, scanner, permissions, audit (+audit_helper,
│ │ # +schemas_audit, v3.13.39), retention, webui
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
│ ├── retention/ # archiver, cleaner, exporter, policies, runtime, state
│ ├── connectors/
│ │ ├── permissions/ # base, local, remote, ad, factory, cache
│ │ └── audit/ # windows_audit
│ ├── services/ # access_service, access_config
│ ├── db/ # models.py, session.py, init_roles.py
│ │ └── migrations/ # Alembic 001…007 (007_add_cascade_deletes) + run_migration.py
│ ├── cache/ # redis_client.py (кэш/rate-limit, fail-open)
│ └── workers/ # Celery app/tasks/beat_schedule
│
├── scanner/ # Python-сканер (тяжёлый, на хосте)
│ ├── src/
│ │ ├── managed_scanner.py # main loop, submit_results_status,
│ │ │ # _fail_task_safely, _parent_of_path (S3)
│ │ ├── heartbeat.py # HeartbeatThread (backoff 5→10→30→60→120)
│ │ ├── metrics.py # Prometheus :9101
│ │ ├── config_loader.py # конфиг + env-override; S3ConnectorConfig
│ │ ├── finding.py # dataclass Finding (строка/фрагмент)
│ │ ├── encryption.py # AES-256-GCM + HMAC + маскирование
│ │ │ # _CONTEXT_PATTERNS (22 паттерна, BUG-086)
│ │ ├── modes/ # base, hybrid, managed, standalone
│ │ └── offline/ # queue, storage (оффлайн-батчи)
│ ├── connectors/ # коннекторы источников (BACKLOG-097)
│ │ ├── base.py # ISourceConnector / BaseConnector
│ │ ├── filesystem.py # FS-коннектор, построчное чтение (53.1b)
│ │ ├── s3_connector.py # старый ISourceConnector (list_files/get_content),
│ │ │ # сканером не используется
│ │ ├── s3_line_connector.py # построчный S3/MinIO (53.2, 53.3-fix,
│ │ │ # 53.3-fix-s3-bucket, v3.13.41 BUG-149: bucket-фолбэк из path)
│ │ ├── _text_scanner.py # общий построчный пайплайн (53.1b)
│ │ └── factory.py # реестр source_type → коннектор (53.1b)
│ ├── core/ # orchestrator, state_manager, metrics, base,
│ │ # catalog_manager, adaptive_cache_manager, memory_manager, logger
│ ├── classifiers/ # PII, Credentials, Code, OCR (ocr_worker)
│ │ # scan_line(line, num) → list[Finding]
│ ├── handlers/ # finding_collector.py
│ ├── utils/ # document_extractor, file_hasher, ocr_engine,
│ │ # performance_monitor
│ └── config/scanner_config.json
│
├── audit-agent-windows/ # Windows-агент (лёгкий)
│ ├── main.py, collector.py, buffer.py, sender.py
│ ├── service.py # Windows-служба
│ └── config.json
│
├── audit-agent-linux/ # Linux-агент (inotify/watchdog)
│ ├── main.py, collector.py, buffer.py, sender.py
│ ├── metrics.py # Prometheus :9102
│ ├── service/ # dcap-audit-agent.service + install/uninstall(.cron).sh
│ └── start.sh, stop.sh, status.sh
│
├── audit-agent-s3/ # S3/MinIO агент аудита
│ ├── src/ # main, collector, buffer, sender, config_loader,
│ │ # converters, heartbeat, state, metrics
│ ├── config/
│ ├── scripts/
│ └── tests/
│
├── webui/ # каноничный UI :8001 (прокси в Manager)
│ ├── main.py # FastAPI (Jinja2)
│ ├── config.py # загрузка конфига
│ ├── api/ # routes.py (прокси, forwarded_headers), schemas.py
│ ├── static/
│ │ ├── css/
│ │ │ ├── tokens.css # 🆕 v3.13.37 — Dovetail tokens (dark-only)
│ │ │ ├── base.css # 🆕 v3.13.37 — глобальные стили + шрифты
│ │ │ ├── components.css # 🆕 v3.13.37 — override Bootstrap
│ │ │ ├── grid-wireframe.css # 🆕 v3.13.37 — blueprint-сетка
│ │ │ ├── main.css # .app/.main-content/.page-content + медиа
│ │ │ ├── findings.css # страничная специфика (подхват. токены)
│ │ │ └── components/ # sidebar, header, cards, tables, forms, modals, badges
│ │ ├── js/ # api.js, auth.js, dashboard.js, findings.js, ... (theme.js — удалён v3.13.37)
│ │ └── vendor/
│ │ ├── css/ # Bootstrap, Font Awesome (локально)
│ │ ├── js/ # Chart.js (локально)
│ │ └── fonts/ # 🆕 v3.13.37 — inter.woff2 + inter.css,
│ │ # jetbrains-mono.woff2 + jetbrains-mono.css
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
│ ├── seed_minio.sh, minio-seed/access-logs/* # seed-логи для MinIO
│ └── init_ad_test_data.py, create_test_share.ps1
│
├── monitoring/ # Prometheus/Grafana/Alertmanager
│ ├── prometheus/{prometheus,alerts}.yml
│ ├── alertmanager/alertmanager.yml
│ └── grafana/provisioning/
│
├── tests/
│ ├── unit/ # unit-тесты (460 passed на v3.13.41; NEW v3.13.41: test_delete_resource_v31341.py (BUG-150), 3 теста S3 bucket-фолбэк (BUG-149); v3.13.39: *_v31339.py — audit rollback, change-password, RBAC /api/audit, roles CRUD)
│ ├── e2e/ # E2E-тесты (53 passed / 7 skipped, эталон :18000/:18001; NEW v3.13.41: test_s3_scan_v31341.py — S3-скан MinIO >0 files, ≥9 находок)
│ ├── chaos/ # Chaos-тесты
│ ├── load/ # Нагрузочные
│ └── fixtures/ # Общие фикстуры (auth, db, manager, scanner, test_files)
│
├── manager/tests/ # pytest-модули Manager (test_security,
│ # test_retention, test_auth_ad, test_ad_permissions)
│
├── docs/
│ ├── DESIGN.md # ⚠️ пока НЕ существует — план 53.4e (BACKLOG-093);
│ │ # сейчас DESIGN.md в корне репо (v3.13.37, перенесён из «не закоммичен»)
│ ├── ui-screenshots/ # ⚠️ НЕ существует — план 53.4e (BACKLOG-093)
│ ├── admin-guide/ # 04-authentication, 05-security,
│ │ # 06-scanner (+§8 S3/MinIO), 10-troubleshooting
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
├── init_db.py, init_db_data.py, fix_db.py, scan_folder.py
├── start_scanner.bat, generate_test_tree.py
├── test_models.py, test_parse.py, test_access_management.py
├── alembic.ini
├── docker-compose.yml, docker-compose.prod.yml
├── docker-compose.test.yml, docker-compose.s3.yml, docker-compose.minio.yml
├── docker-compose.ad.yml.example
├── SECURITY.md, NOTICE.md
├── STATE.md, ROADMAP.md
├── ARCHITECTURE.md # этот файл
├── AGENTS.md, README.md, CHANGELOG.md
├── DESIGN.md # 🆕 v3.13.37 — референс стиля Dovetail (временно в корне)
├── pyproject.toml, requirements.txt, requirements-dev.txt
├── Diagram-ru.png, Diagram-ru-1.png, Diagram-ru-2.png, Diagram-en.png
└── LICENSE # ⚠️ отсутствует (NO LICENSE в репозитории)
🔐 АУТЕНТИФИКАЦИЯ И БЕЗОПАСНОСТЬ
Режимы аутентификации
AuthMode (manager/src/auth/modes.py), дефолт в коде — local, в config.json — ${AUTH_MODE:-hybrid}.

Режим	Описание
local	JWT + Bcrypt, встроенные пользователи (разработка)
hybrid	SPNEGO → fallback JWT (тестирование)
windows_integrated	Только SPNEGO (production AD)
⚠️ ad.py (коннектор прав AD) — заглушка; локальный сбор прав идёт через icacls / net localgroup.

WebUI: хранение токена (v3.13.40/41)
JWT хранится в `localStorage['dcap_access_token']` (префикс `dcap_`). Дополнительно `localStorage['dcap-sidebar']` — состояние sidebar.

`webui/static/js/auth.js`:
- `setToken(null)` → `removeItem` (не пишет `null`).
- `getToken()` → `null` (если нет ключа).
- `authHeaders()` → `'Bearer ${token}'`.
- `login` → `setToken(data.access_token)`.
- `logout` → POST `/api/auth/logout` + `setToken(null)` + redirect.
- `me()` → при 401 → `setToken(null)` (авто-logout).
- `check()` → при 401 → redirect `/login`.

⚠️ BACKLOG-119 (v3.13.41): badge режима на /login показывается только для `windows_integrated` («Windows Authentication»); для `local`/`hybrid` — скрыт. Сам режим `hybrid` остаётся в коде до v3.1.0 (B.1), поле «Домен» — v3.1.0.

Ролевая модель
Роли создаются db/init_roles.py при старте. Проверки — в auth/dependencies.py.

Роль	Роли в require_*	Описание	AD группа
admin	require_admin, require_viewer	Полный доступ	DCAP_Admins
auditor	require_auditor, require_viewer	Аудит + расшифровка находок	DCAP_Auditors
scanner	require_viewer, require_scanner	Запуск сканирования	DCAP_Scanners
viewer	require_viewer	Только чтение (маскированное)	(все остальные)
⚠️ require_viewer перечисляет все 4 роли, поэтому на практике эквивалентен require_auth. В api/findings.py импортируется, но не применяется ни на одном маршруте — там стоит require_auth.
⚠️ Роль admin создаётся с паролем admin/admin123 — сменить при первом запуске.
⚠️ Системные роли (admin / auditor / scanner / viewer) иммутабельны (BUG-168, v3.13.39): rename и смена AD-группы → 400; редактируется только `description`. Кастомные роли — редактируются полностью.
⚠️ Все операции с ролями аудитируются (BUG-181, v3.13.39): `role_created` / `role_updated` / `role_deleted` (event_type в audit_logs).

mTLS
relaxed (по умолчанию) — если сертификаты не найдены, работает на plain HTTP; run_manager.py передаёт в uvicorn контекст из CertificateManager.get_server_ssl_context() (ssl_cert_reqs=ssl.CERT_OPTIONAL).

strict — Manager не стартует без PKI (CertificateManager.is_available → raise), ssl_cert_reqs=ssl.CERT_REQUIRED.

CRL для отзыва сертификатов. v3.13.28: проверяется на двух уровнях — ssl.VERIFY_CRL_CHECK_LEAF в TLS-контексте и is_revoked(DER) в AuthMiddleware._check_mtls; отозванный клиент получает 401.

Клиентский CN извлекается в AuthMiddleware._check_mtls → request.state.client_cert_cn.

Контейнер Manager монтирует ./certs:/app/certs:ro — BUG-105 (v3.13.28); прежний ./manager/certs не совпадал с каталогом, куда пишет scripts/generate_certs.py.

⚠️ BUG-106 (v3.13.28): machine-эндпоинты (AuthMiddleware.machine_prefixes) — /api/scanner/register, /api/scanner/heartbeat, /api/scanner/tasks*, /api/audit/agents/register, /api/audit/agents/heartbeat, /api/audit/events, /api/audit/permissions — не входят в public_paths (раньше входили, из-за чего mTLS-проверка для них пропускалась). JWT для них не требуется, но _check_mtls() вызывается явно: в strict без клиентского сертификата → 401.

Шифрование находок (Findings Refactor, v3.9.0-v3.10.0)
Модель: гибрид — маскированное + зашифрованное.

Аспект	Решение
Алгоритм	AES-256-GCM
Ключ	ENV (FINDINGS_ENCRYPTION_KEY) — Docker Secrets убраны (TASK-018)
HMAC-ключ	ENV (FINDINGS_HMAC_KEY)
Key ID	findings_key_id (для ротации)
По умолчанию	Маскированное
Расшифровка	Только Auditor, с аудитом
Fingerprint	HMAC-SHA256 (не SHA256 — защита от brute-force)
Legacy-режим	SHA-256 (не MD5 — BACKLOG-066, крипто-фикс)
Что маскируется (MASK_RULES):

Маски различаются между модулями: scanner/src/encryption.py — 19 категорий, manager/src/core/encryption.py — 11 (без credential-специфичных). Категории, которых нет в Manager, приходят маскированными от сканера.

Категория	Маска	Где	Шифрование
phone	+7***XXX-XX-XX	оба	✅
email	us***@ex***.com (BUG-044)	оба	✅
api_key / aws_key	AKIA*** (первые 4)	оба	✅
password	***	оба	✅
token	eyJh*** (первые 6)	оба	✅
jwt_token	eyJhbG*** (первые 10)	scanner	✅
ssh_key	***ssh-private-key***	scanner	✅
github_token	ghp_*** (первые 4)	scanner	✅
slack_token	xoxb*** (первые 5)	scanner	✅
discord_token	disco*** (первые 6)	scanner	✅
database_url	scheme://***@host	scanner	✅
basic_auth	Basic ***	scanner	✅
high_entropy	первые 6 симв.	scanner	✅
passport	12** ******	оба	✅
snils	***-***-*** **	оба	✅
inn	12**********	оба	✅
credit_card	**** **** **** 1234	оба	✅
person	не маскируется (по решению)	оба	❌
⚠️ phone маскируется только для RU-номеров вида +7 + 11 цифр (_mask_phone); US/интернациональные номера через MASK_RULES не проходят и закрываются _CONTEXT_PATTERNS.

Маскирование контекстов (BUG-086, v3.13.21)
Проблема: mask_context покрывал только 6 из 19 категорий MASK_RULES — в context_* утекали credentials (github_token, basic_auth) и US-phone.

Решение: конвейер _CONTEXT_PATTERNS — 22 паттерна (17 уникальных категорий из 19 в MASK_RULES; person и high_entropy исключены осознанно):

Порядок	Паттерн	Категория
1	ghp_*, github_pat_*	github_token
2	xox[baprs]-*	slack_token
3	AKIA*	aws_key
4	sk-*, sk_live_*	api_key
5	discord*	discord_token
6	eyJ*.*.*	jwt_token
7	-----BEGIN ... PRIVATE KEY-----	ssh_key
8	Basic <base64>	basic_auth
9	scheme://...	database_url
10	password= / api_key= (2 паттерна)	password, api_key
11	token=, secret=, access_key= (3 паттерна)	token
12	email (1)	email
13	phone: +7, +1, международные (3)	phone
14	passport, snils, inn, credit_card (4)	PII
Итого 22 паттерна: строки 1–9 дают по 1–2, строки 10–14 — по 2–4.

Ключевые решения:

Специфичные токены раньше generic — иначе token съедал бы ghp_-префиксы.

Generic KEY=VALUE маскирует только значение — сохраняет маркер категории (GITHUB_TOKEN=ghp_***, а не GITHUB_TOKEN=***).

person и high_entropy в контекст не попадают — исключены осознанно.

Аудит действий с findings (v3.13.24–26)
Все действия с findings логируются в audit_logs — compliance 152-ФЗ / GDPR / PCI DSS.

Действие	Эндпоинт	event_type	metadata
Раскрытие	POST /{id}/reveal	finding_reveal	action=finding_revealed, finding_id, category
Доступ к фрагменту	GET /{id}/fragment	fragment_accessed	finding_id, mode (embedded / full-image)
Доступ к hash	GET /{id}/fragment/hash	fragment_accessed	finding_id, mode=hash
Экспорт	GET /findings/export	findings_exported	format, count, reveal, фильтры
Подтверждение	PATCH /{id} (confirmed)	finding_confirmed	old_status, new_status, comment, via=patch
Ложное срабатывание	PATCH /{id} (false_positive)	finding_false_positive	то же
Архивирование	PATCH /{id} (archived)	finding_archived	то же
Сброс	PATCH /{id} (new)	finding_reset	то же
Массовое обновление	POST /bulk	finding_confirmed/_false_positive/_archived/_reset	via=bulk, по одной записи на finding
Удаление	DELETE /{id} (Admin)	finding_deleted	old_status, resource_id, via=delete
Поля записи:

event_source = "api"

user = current_user.username (реальный пользователь, не роль БД)

file_path = fragment_path finding'а

source_host = IP клиента

metadata_json = {action, finding_id, category, finding_type, old_status, new_status, comment, via}

Хелпер _log_finding_status_change (manager/src/api/findings.py):

Единая точка для PATCH и bulk.

Не делает commit — записи копятся, коммит вызывающего кода (избегает N коммитов на bulk).

Для DELETE — AuditLog создаётся до db.delete(finding), иначе после commit инстанс expire'ится.

Сброс review-полей при new (BUG-100): _apply_status — единая функция для PATCH и bulk; при new очищаются reviewed_by, reviewed_at, comment.

Аудит аутентификации (BUG-095, v3.13.24)
Событие	event_type	metadata
Успешный вход	auth_login	auth_source, auth_method, auth_mode, roles
Неудачный вход	auth_failed	reason (invalid_credentials/user_inactive/user_not_found), attempted_username
Выход	auth_logout	jti
Создание пользователя	user_created	target_user_id, target_username, auth_source, is_active, roles
Обновление	user_updated	changes, roles_added, roles_removed
Смена пароля	user_password_changed	by_admin, self_service
Роли	role_assigned / role_revoked	role, target_user_id
Роли (CRUD, v3.13.39)	role_created / role_updated / role_deleted	role_name, role_id, ad_group, changes (BUG-181)
Удаление	user_deleted	target_user_id, target_username, roles
auth_refresh НЕ логируется — 290 событий/сутки на пользователя без ценности для расследований.

Безопасность metadata: _sanitize рекурсивно вырезает password, *_token, *_secret, *_hash, *_salt, *_credential; PII (email, full_name) → "changed".

Fail-open: ошибка логирования не ломает эндпоинт (try/except + rollback).

HTTP-ответ при неудачном входе всегда 401 Invalid credentials — нельзя перебрать существующие учётки; различие только в аудите.

Единый `with_audit` (BUG-202, v3.13.39)
До v3.13.39 аудит писался до `db.commit()`: при откате транзакции запись в audit_logs оставалась, а бизнес-изменение — нет (и наоборот, middleware ломал коммит). Введён контекст-менеджер:

`manager/src/api/audit_helper.py`:

- `_log_audit(db, event_type, **kwargs)` — создаёт AuditLog БЕЗ commit (шарит транзакцию вызывающего).
- `with_audit(db, event_type, request=, user=, file_path=, metadata=)` — `yield` → `_log_audit` → `db.commit()`; при исключении → `db.rollback()` + `raise`.

Переведены на with_audit: `api/resources.py` (created/updated/deleted), `api/findings.py` (PATCH update_finding), `auth/router.py` (role_created/updated/deleted, change_password). `POST /api/findings/bulk` остаётся на `_log_finding_status_change` (N записей → один commit).

Смена пароля (BUG-201, v3.13.39)
`POST /api/auth/change-password` возвращал 200, но не менял пароль: `request.state.user` создаётся в сессии AuthMiddleware и мутируется «в чужой сессии» — `db.commit()` хендлера был пустым. Фикс: пользователь пере-запрашивается в сессии хендлера (`db.query(User).filter(User.id == current_user.id).first()`), пароль (`set_password`) → commit → refresh → аудит `user_password_changed` после commit. `ChangePasswordRequest.confirm_password` (опционально) — защита от опечаток.

Аудит-API (BUG-214/223/142, v3.13.39)
- `GET /api/audit` и `GET /api/audit/stats` — только Auditor+ (`require_auditor`); viewer/scanner → 403.
- `GET /api/audit/{log_id}` — деталь события с `metadata_json` (`AuditLogDetail`, `api/schemas_audit.py`); отсутствующая запись → 404.
- `/api/audit/stats` дополнительно возвращает `total_resources` = count(Resource.id) — Dashboard KPI «Ресурсов».

📊 МОДЕЛЬ ДАННЫХ: FINDINGS
Иерархия
text
Resource (корневая директория задачи)
└── Finding (находка = строка/фрагмент)
    ├── line_number
    ├── match_text_masked / match_text_encrypted
    ├── line_text_masked / line_text_encrypted
    ├── context_before_masked / context_after_masked
    ├── fragment_data (OCR PNG, BACKLOG-086)
    ├── fingerprint (HMAC-SHA256)
    └── status (new/confirmed/false_positive/archived)
Модель Finding
python
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
⚠️ 5 колонок fragment_* добавлены миграцией 005_add_fragment_columns.py, а не 003_findings_refactor.py.

Модель ScanTask — source_type (v3.13.29, миграция 006)
День 53.1a (BACKLOG-097): задание несёт явный тип источника — сканер выбирает коннектор по source_type, а не угадывает по префиксу source_path (s3://…).

Поле	Тип	Значение
source_type	String(20), default "filesystem", index	filesystem / s3 / minio (lowercase — как Resource.type)
progress	JSON, nullable	Прогресс из heartbeat (миграция 002)
POST /api/resources/{id}/scan проставляет source_type = (resource.type or "filesystem").lower(). Миграция 006_add_source_type идемпотентна (inspect-guard).

Для S3 source_path = s3://bucket/prefix, а fragment_path находки = s3://bucket/key (53.2) — стабильно между сканами, если ключ не меняется, поэтому дедупликация по fingerprint работает.

Дедупликация
manager/src/core/encryption.py:

python
msg = f"{file_path}|{line}|{match}|{category}".encode("utf-8")
hmac.new(hmac_key, msg, hashlib.sha256).hexdigest()
Разделитель — |. 4-й параметр сигнатуры называется category, но оба вызывающих передают finding_type (api/scanner.py, scanner/src/managed_scanner.py).

Legacy-режим: SHA-256 без HMAC (_legacy_fingerprint в сканере) — не MD5 (BACKLOG-066).

⚠️ Два нюанса:

Сканер считает legacy_fingerprint и кладёт в payload, но Manager его не читает — при отсутствии fingerprint Manager сам считает HMAC. То есть legacy-ветка на дедупликацию не влияет.

Миграция 003 для переноса legacy-строк использует md5(random()::text || resource_id::text) как fingerprint. MD5 в проекте остался только здесь (путь миграции, только PostgreSQL).

При повторном скане (api/scanner.py):

Статус в БД	Действие
false_positive	не создавать (skipped_false_positives)
confirmed / new / archived	обновить last_seen_at + masked/encrypted-поля
не найден	создать new
⚠️ Ветка обновления покрывает все три статуса, а не только confirmed. И на практике из сканера она почти не достигается: FP-фильтр сканера (skip = false_positives | confirmed) не отправляет в Manager и подтверждённые находки, поэтому обновление возможно только при прямом POST без HMAC-ключей.

Сканер проверяет FP батчем: POST /api/findings/check-fingerprints.

Типы фрагментов
Тип	Для чего	Что показывать
text_line	Текстовые файлы	Строка с совпадением
text_context	Текстовые файлы	Строка + N строк контекста
image_region	Изображения, PDF-сканы	Вырезанный фрагмент (PNG) + bounding box
byte_range	Бинарные	Hex-дамп вокруг offset
⚠️ Валидации значений нет: FragmentType Literal объявлен в api/schemas_findings.py, но нигде не применяется.

Встроенные фрагменты (BACKLOG-086, v3.13.19)
Проблема: Manager в Docker не видит хостовые пути сканера → /fragment для OCR возвращал 404. + Файл может быть удалён после сканирования.

Решение: сканер встраивает весь PNG (OCR-фрагмент) в payload (base64 + SHA-256) → Manager хранит fragment_data в БД → «файл удалили — доказательство осталось».

Ограничения:

Только image_region (OCR). text_line — данные уже в line_text_encrypted.

Максимум MAX_FRAGMENT_EMBED_SIZE (ENV, default 2 МБ).

Батчинг POST по MAX_BATCH_SIZE_BYTES (ENV, default 20 МБ).

Дедупликация фрагментов — BACKLOG-087 (v3.1.0).

Шифрование fragment_data — BACKLOG-088 (v3.1.0).

Архивная таблица findings_old
Миграция 003_findings_refactor.py переименовывает старую findings (файл-уровень) в findings_old. Таблица не удаляется ни одной миграцией.

⚠️ findings_old появляется только если до миграции была старая схема без fingerprint. Если БД создана через create_all с новой схемой, upgrade() выходит сразу и таблицы не будет.
⚠️ Данные переносятся только на PostgreSQL. На SQLite (dev) старые строки остаются в findings_old без переноса.
⚠️ Удаление — BACKLOG-065 (вместе с findings_archive).

Партиционирование audit_logs
audit_logs — партиционированная таблица (RANGE по created_at), только PostgreSQL.

PK: (created_at, id) — из-за этого ORDER BY id DESC не использует индекс.

⚠️ В SQL user обязательно в кавычках — иначе PostgreSQL вернёт CURRENT_USER (BUG-094).

🗂️ S3-КОННЕКТОР СКАНЕРА (BACKLOG-097, v3.13.29–35)
Общая картина
Сканер получил второй тип источника — S3/MinIO. Задание теперь содержит явный source_type, а не «угадывание» по префиксу пути.

text
Manager:
  POST /api/resources?type=s3&path=s3://bucket/prefix[&endpoint=...]
    → Resource(type='s3', path='s3://bucket/prefix',
               scan_config.connector.s3={endpoint,bucket,prefix,secure,use_path_style,region})
  POST /api/resources/{id}/scan
    → ScanTask(resource_id, source_path='s3://bucket/prefix',
               source_type='s3')
  GET /api/scanner/tasks/pending
    → {task: {id, path, source_type, scan_config}}

Scanner (managed_scanner.py):
  _execute_task(task)
    self._current_source_type = task.get("source_type") or "filesystem"
    self._current_scan_config = task.get("scan_config") or {}
    self._connector = None  # пересоздаём на каждой задаче
  _init_line_pipeline()
    connector_cfg = local defaults + scan_config.connector.s3 (merge)
    self._connector = factory.create_line_connector(self._current_source_type, connector_cfg)
  _execute_task_linewise → _scan_line_by_line → self._connector.scan_path(...)
Модули
Файл	Роль	Версия
scanner/connectors/_text_scanner.py	Общий построчный пайплайн (5 функций): is_supported_file, decode_text_bytes, file_pass_prefilter, scan_text, extract_document_text	53.1b
scanner/connectors/factory.py	Реестр source_type → фабрика, create_line_connector(source_type, config); зарегистрированы filesystem, s3, minio	53.1b + 53.2
scanner/connectors/filesystem.py	FS-коннектор FilesystemConnector (scan_path / scan_file), рефакторинг на _text_scanner	53.1b
scanner/connectors/s3_line_connector.py	Построчный S3/MinIO-коннектор S3LineConnector, интерфейс как у FilesystemConnector. Streaming через Body.iter_chunks, документы/OCR — через временный файл + DocumentExtractor	53.2 + 53.3-fix
scanner/connectors/s3_connector.py	Старый S3Connector(BaseConnector) — list_files / get_content для Orchestrator. Сканером не используется; в нём же configure() с fallback на config-секреты	—
scanner/connectors/base.py	ISourceConnector / BaseConnector (ABC)	—
Секреты S3
Только ENV на хосте сканера: S3_ACCESS_KEY, S3_SECRET_KEY (политика TASK-018).

S3LineConnector.__init__ — приоритет ENV над config.access_key/secret_key; если в config секреты есть, пишется WARNING; если нет ни ENV, ни config — ValueError;

fallback на config сохранён (чтобы не сломать существующие конфиги) — вынос в BACKLOG-103 (v3.1.0);

Manager никогда не передаёт секреты в payload задачи — только endpoint/bucket/prefix/secure/use_path_style/region.

⚠️ BUG-148 (v3.13.39): чтение ENV из .env на сканере — `run_scanner.py` вызывает `load_dotenv()` (корень репо), `start_scanner.bat` парсит `.env` построчно (загрузка S3_ACCESS_KEY/S3_SECRET_KEY и др. до запуска). Без этого S3-коннектор падал с «задайте S3_ACCESS_KEY/S3_SECRET_KEY в ENV».

Endpoint
Вариант B (v3.13.32), на стороне Manager: endpoint (query) → S3_DEFAULT_ENDPOINT (ENV на хосте Manager) → 400. Хардкод host.docker.internal:9000 в manager/src/api/resources.py удалён.

⚠️ На стороне сканера дефолт ещё есть: S3LineConnector при пустом config["endpoint"] подставляет host.docker.internal:9000 (последний рубеж) — см. BACKLOG-103.

⚠️ Legacy WebUI (v3.13.41, BUG-149): /api/tasks/create и /api/resources/create для s3/minio строят connector.s3 с endpoint из ENV S3_DEFAULT_ENDPOINT или fallback host.docker.internal:9000 (в WebUI-форме нет поля endpoint). POST /api/resources (каноничный) — endpoint обязателен (query/ENV), как в строке выше.

Рекурсия
Всегда — без опции отключения. list_objects_v2(Prefix=…) без Delimiter возвращает всё поддерево (S3 — плоское хранилище). Опция recursive=false намеренно не поддерживается — чтобы не пропустить вложенные объекты при ошибке конфигурации.

Bucket (v3.13.35)
Bucket — из scan_config.connector.s3.bucket (payload задачи от Manager). path (s3://bucket/prefix) используется как суффикс префикса; bucket в path игнорируется, если задан в config (53.3-fix-s3-bucket).

path в задании	Префикс для list_objects_v2
s3://other-bucket/logs/	logs
s3://other-bucket/	пусто → fallback на config.prefix (_discover_keys: prefix or self._prefix)
"" / None	config.prefix
не s3:// / minio://	весь path без ведущего / трактуется как префикс
Инвариант: bucket фиксируется при создании ресурса — смена bucket в path задания ничего не меняет, если bucket задан в config (тест test_bucket_in_path_is_ignored_and_config_wins).

BUG-149 (v3.13.41) — S3-скан возвращал 0 files
Причина: ресурсы s3/minio, созданные через legacy-эндпоинты WebUI (/api/tasks/create, /api/resources/create), НЕ получали `scan_config.connector.s3` → S3LineConnector падал с «bucket обязателен» (`_init_line_pipeline` → ValueError) → fallback на filesystem-оркестратор → «s3://…» открывался как папка → 0 files.

Фикс (3 части):
- WebUI-эндпоинты: для s3/minio собирают `connector.s3` из path (endpoint из ENV `S3_DEFAULT_ENDPOINT` или `host.docker.internal:9000`, bucket/prefix из path) — аналог POST /api/resources (v3.13.32);
- S3LineConnector: bucket может отсутствовать в config — берётся из path в `scan_path()` (fallback, config всё равно приоритетнее); добавляется в `self._bucket`, чтобы чтение (`scan_file`/`_read_text`) шло из того же bucket;
- диагностика: DEBUG-логи `list_objects_v2` (bucket/prefix/кол-во ключей на страницу и итого); таймаут соединения теперь поднимает исключение (раньше молча превращался в 0 ключей → «No files found»).

Тесты: tests/unit/test_s3_line_connector_v31331.py (3 новых: bucket из path, ошибка без bucket нигде, конструктор допускает отсутствие bucket) + tests/e2e/test_s3_scan_v31341.py (S3-скан MinIO на детерминированном датасете → > 0 files, ≥ 9 находок).

BUG-136 (v3.13.31)
decode_text_bytes теперь выполняет strict-декод: utf-8 → cp1251 → fallback utf-8 с errors="ignore". Раньше первая итерация использовала errors="ignore", из-за чего UnicodeDecodeError не поднимался и ветка cp1251 была недостижима. Cp1251-файлы декодируются корректно (подтверждено на живых данных MinIO: 9 находок; тест tests/unit/test_decode_text_cp1251_v31331.py).

Ограничения S3
Ограничение	Описание	План
s3://* (все bucket'ы одной задачей)	Не поддерживается — на каждый bucket создаётся отдельный Resource	—
recursive=false	Не поддерживается (рекурсия всегда)	—
Параллелизм S3 (max_parallel_files > 1)	scan_path последовательный	BACKLOG-100 (v3.1.0)
skip_prefixes (аналог skip_dirs)	Не реализован	BACKLOG-099 (v3.1.0)
Fallback на config-секреты	S3LineConnector.__init__ берёт config.access_key/secret_key, если нет ENV	BACKLOG-103 (v3.1.0)
Fallback endpoint в коннекторе	host.docker.internal:9000 при пустом endpoint	BACKLOG-103 (v3.1.0)
secure=false = verify=False	При HTTP-эндпоинте сертификат не проверяется	TEST-NOTE-6.11 → v3.1.0
Разные credentials на разные S3	Нужны отдельные инстансы сканера (ENV per host)	v3.1.0
📐 СКАНЕР: ИНСТАНСЫ И ПАРАЛЛЕЛИЗМ
Модель выполнения
1 инстанс сканера (ManagedScanner.run_loop) = 1 процесс = 1 задача за раз.

1 задача (ScanTask) = 1 Resource = 1 bucket (S3) или 1 папка (FS).

Много bucket'ов / папок — один инстанс обрабатывает их последовательно (FIFO по created_at), задачи забираются из GET /api/scanner/tasks/pending.

Параллелизм
N инстансов сканера (N процессов на одном/разных хостах), у каждого свой scanner_id и свои state_dir / порт метрик.

Manager распределяет задачи: первый, кто дёрнул /tasks/pending, забирает задачу (перевод в assigned).

⚠️ Ограничение: N инстансов должны иметь уникальные scanner_id (иначе heartbeat перезапишет чужой) и уникальные state_dir (иначе гонка за state.json).

Endpoint / credentials
Endpoint — per-task (payload scan_config.connector.s3), поэтому один сканер может работать с разными endpoint (MinIO, AWS S3, Wasabi).

Секреты — per-host ENV. Разные credentials → разные инстансы сканера (или общий credential-set).

Что НЕ поддерживается (v3.0.0)
Resource.path = s3://* (все bucket'ы одной задачей) — на каждый bucket создаётся отдельный Resource.

Per-task credentials (чтение из ENV-файла, привязанного к задаче) — v3.1.0+.

📌 Раздел «Масштабирование: сколько инстансов» в docs/admin-guide/06-scanner.md — отдельный день (после 53.4e).

🌐 WEBUI-РЕДИЗАЙН (BACKLOG-093, v3.13.37, этап 1/5)
Общая картина
Цель: перевести WebUI на тёмную тему Dovetail (DESIGN.md) — command-center, single accent #6798ff, 8px радиусы, zero-shadow, grid-wireframe. Dark-only (переключатель темы удалён).

5 под-дней:

53.4a (✅ v3.13.37) — токены + base + компоненты + grid-wireframe + локальные шрифты.

53.4b — login, dashboard, resources, findings.

53.4c — finding_detail, catalog, audit, scanners, access.

53.4d — roles, users, settings, footer, графики (Chart.js palette).

53.4e — полировка + docs/ui-screenshots/ + docs/DESIGN.md.

Файлы CSS (после 53.4a)
Файл	Роль	Legacy-аналоги
tokens.css	CSS-переменные Dovetail (dark-only) + legacy-алиасы (--color-bg, --color-text, --color-surface, --color-primary и т.д.)	заменяет variables.css + theme-dark.css
base.css	html/body, заголовки, ссылки, code/pre, скроллбар, override select/input/textarea, ::selection	—
components.css	Override Bootstrap 5 (.btn, .card, формы, modal, badge, table, alert, dropdown, pagination, progress, utilities)	—
grid-wireframe.css	1px #1e1e1e blueprint-сетка на body::before (opacity: 0.6)	—
main.css	.app, .main-content, .page-content, .text-center, .text-muted, @media	бывш. базовые правила
findings.css	Страничная специфика findings (карточки, фрагменты, hex)	—
components/*.css	sidebar, header, cards, tables, forms, modals, badges	—
Ключевая идея: legacy-имена переменных сохранены в tokens.css (--color-bg = var(--color-page-ink) = #0a0a0a, --color-text = var(--color-snow) = #ffffff, --color-primary = var(--color-blue-cornflower) = #6798ff и т.д.), поэтому components/*.css и findings.css подхватили новые значения без правок.

Шрифты (локально, CDN запрещён) — ✅ кириллица (BUG-212, v3.13.40)
webui/static/vendor/fonts/:

Файл	Размер	Источник
inter.woff2	352 KB	Inter Variable (rsms/inter), кириллица есть
jetbrains-mono.woff2	113 KB	JetBrains Mono v2.304 variable (wght 100–800), кириллица 92/96 базовых
inter.css	—	@font-face woff2-variations, unicode-range + кириллица
jetbrains-mono.css	—	@font-face woff2-variations, unicode-range + кириллица
OFL.txt	—	NEW v3.13.40 — SIL OFL 1.1 (JetBrains Mono)
✅ 53.4a-доп4 (v3.13.40): `unicode-range` обоих @font-face расширен кириллицей — Cyrillic base (U+0400-045F, U+0490-0491, U+04B0-04B1, U+0301, U+2116), Cyrillic Extended (U+0460-052F, U+1C80-1C88, U+20B4, U+2DE0-2DFF, U+A640-A69F), Latin Extended Additional (U+1E00-1EFF) — русский UI и `<code>/<pre>` отрисовываются без fallback (проверено: глифы П/р/и/в/е/т/Ж/У/К/я в cmap обоих woff2).
⚠️ Причина BUG-212 была двойной: (1) `unicode-range` без кириллицы; (2) прежний `jetbrains-mono.woff2` был Fontsource latin-подмножество (229 глифов, кириллицы 0). Заменён на официальный JetBrains Mono v2.304 variable (файл пересобран из `JetBrainsMono[wght].ttf` через fontTools, `flavor='woff2'`).
Принцип подключения: `main.css → @import base.css → @import '/static/vendor/fonts/inter.css' + '/static/vendor/fonts/jetbrains-mono.css'`; `tokens.css`: `--font-inter: 'Inter', ui-sans-serif, …`, `--font-jetbrains-mono: 'JetBrains Mono', ui-monospace, …`, `--font-mono: var(--font-jetbrains-mono)`; `base.css` вешает их на `body` и `code/pre`.

Что удалено (53.4a)
Файл	Почему
webui/static/css/variables.css	Перенесено в tokens.css
webui/static/css/theme-dark.css	Dark-only, отдельный файл не нужен
webui/static/js/theme.js	Переключателя темы больше нет
Отличия от DESIGN.md (осознанные)
Аспект	DESIGN.md	Реализация DCAP	Причина
.btn-primary background	White filled #ffffff	White filled #ffffff (var(--color-snow), текст var(--color-page-ink)); hover — var(--color-ash); disabled — var(--color-fog)	✅ Соответствует DESIGN.md. Отклонение 53.4a (dark carbon #1e1e1e) отменено BACKLOG-121 (v3.13.41)
Семантические цвета (--color-danger/success/warning)	«Do not introduce a second chromatic color»	Введены приглушённые #d67272/#4ea87a/#b8974a — только для бейджей статусов (confirmed/false_positive/archived)	Иначе confirmed/false_positive не различить
Ссылки .btn-link	—	#6798ff underline on hover	Как в Bootstrap-совместимости
Тени --shadow-*	Запрещены	none (заглушки для совместимости)	Legacy-код ссылается на --shadow-sm
Grid-wireframe
Тонкая сетка 1px #1e1e1e на фоне #0a0a0a — blueprint-мотив. Рисуется через body::before (position: fixed; inset: 0; z-index: 0; opacity: 0.6), контент поверх (z-index: 1 у .app/.main-content/.sidebar).

⚠️ Тонкий (~3 % контраста). При полировке 53.4e возможна корректировка до #161616 или увеличение opacity.

Открытые задачи в рамках BACKLOG-093
Задача	День
Разметка страниц (login, dashboard, resources, findings)	53.4b
finding_detail, catalog, audit, scanners, access	53.4c
roles, users, settings, footer, Chart.js палитра	53.4d
Полировка, скриншоты в docs/ui-screenshots/, git mv DESIGN.md docs/DESIGN.md	53.4e
unicode-range кириллицы в обоих @font-face	✅ 53.4a-доп4 (v3.13.40)
Stroke-SVG иконки (замена Font Awesome)	BACKLOG-101 (v3.1.0)
Light-тема	BACKLOG-102 (v3.1.0)
🔌 API ЭНДПОИНТЫ
Ресурсы (v3.13.32)
Метод	Эндпоинт	Роль	Назначение
GET	/api/resources	require_auth	Список ресурсов
POST	/api/resources?path=…&type=…	Admin	Создание ресурса. Для type=s3/minio дополнительно: endpoint, secure, use_path_style, region. endpoint: query → S3_DEFAULT_ENDPOINT → 400
DELETE	/api/resources/{id}	Admin	Удалить → 204. ON DELETE CASCADE (миграция 007_add_cascade_deletes, BUG-150 v3.13.41): findings, scan_tasks, catalog_entries, access_entries, access_alerts, permission_changes, failed_files, schedules. audit_logs/findings_old/reviewed_by не затронуты; для SQLite (dev) удаление связанных записей вручную в delete_resource.
POST	/api/resources/{id}/scan	Scanner+	Создать ScanTask c source_type из Resource.type
GET/PUT	/api/resources/{id}/config	Auth/Admin	Конфиг сканирования
type допускает filesystem, s3, minio. Для s3/minio path должен иметь схему s3:///minio:// и непустой bucket; в scan_config.connector.s3 сохраняются endpoint, bucket, prefix, secure, use_path_style, region.

Находки (Findings Refactor, v3.9.0–v3.13.27)
Метод	Эндпоинт	Роль	Назначение
GET	/api/findings	require_auth	Список (маскированное, фильтры)
GET	/api/findings/{id}	require_auth	Детали (маскированное)
POST	/api/findings/{id}/reveal	Auditor+	Расшифровка (с аудитом)
PATCH	/api/findings/{id}	Auditor+	Статус (confirmed/false_positive/archived/new)
POST	/api/findings/bulk	Auditor+	Массовое обновление (до 1000)
GET	/api/findings/stats	require_auth	Статистика
GET	/api/findings/false-positives	Auditor+	Список FP
GET	/api/findings/{id}/fragment	Auditor+	Фрагмент (embedded / full-image / bbox)
GET	/api/findings/{id}/fragment/hash	Auditor+	Метаданные фрагмента
GET	/api/findings/export	Auditor+	Экспорт (CSV/JSON)
DELETE	/api/findings/{id}	Admin	Удалить (с аудитом)
POST	/api/findings/check-fingerprints	публичный	Проверка FP (machine-API)
GET	/api/findings/count	require_auth	Legacy-счётчик (WebUI)
Фильтры GET /api/findings
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
FastAPI 0.137 gotcha: BeforeValidator в Annotated теряется, если Query(...) указан в default → Query() объявлен внутри Annotated, дефолт через =; числовые le/ge несовместимы с Optional[int] → _clamp_int().

Формат ответа списка — плоский массив, не {items, total}:

X-Total-Count — заголовок (BACKLOG-067).

Поля: id, resource_id, task_id, finding_type, category, severity, fragment_type, line_number, match_text (masked), line_text (masked), context_before / context_after (masked), has_fragment, bounding_box, byte_offset, byte_length, file_path, value, status, reviewed_by, reviewed_at, comment, confidence, detector, first_seen_at, last_seen_at, has_encrypted, can_reveal, encryption_key_id.

fingerprint — не отдаётся наружу (только через check-fingerprints).

match_text_encrypted / line_text_encrypted — не отдаются.

Сканер
Метод	Эндпоинт	Назначение
POST	/api/scanner/register	Регистрация
POST	/api/scanner/heartbeat	Heartbeat (scanner_id, task_id, progress)
POST	/api/scanner/tasks/{id}/results	Результаты (findings + fragment_base64)
GET	/api/scanner	Список всех сканеров (WebUI-совместимый)
GET	/api/scanner/{id}	Статус одного сканера
DELETE	/api/scanner/{id}	Удалить регистрацию сканера
GET	/api/scanner/tasks/assigned?scanner_id=N	Назначенные сканеру задачи
GET	/api/scanner/tasks/pending?scanner_id=N	Задачи для сканера
POST	/api/scanner/tasks/{id}/fail	Пометить задачу failed
POST	/api/scanner/tasks/{id}/cancel	Отменить задачу
POST	/api/scanner/tasks/{id}/release	Вернуть задачу в пул
Payload GET /api/scanner/tasks/pending (v3.13.29)
json
{
  "task": {
    "id": 191,
    "resource_id": 135,
    "path": "s3://dcap-audit-logs/",
    "source_type": "s3",
    "scan_config": {
      "classifiers": {},
      "scan": {},
      "connector": {
        "s3": {
          "endpoint": "host.docker.internal:9000",
          "bucket": "dcap-audit-logs",
          "prefix": "",
          "secure": false,
          "use_path_style": true,
          "region": "us-east-1"
        }
      }
    }
  }
}
Если задач нет — {"task": null}. Эндпоинт также освобождает «зависшие» задачи: status='assigned' с assigned_at старше TASK_TIMEOUT_MINUTES → снова pending.

⚠️ task_id в heartbeat — это id текущей (assigned/running) задачи, а не current_task_id: POST /api/scanner/heartbeat ищет активную задачу через task_id/current_task_id, оба допустимы. Пустое значение = idle.
⚠️ Все /api/scanner/* — machine-эндпоинты, публичные в terms of JWT (машина аутентифицируется опциональным mTLS; в strict без клиентского сертификата → 401).

Аутентификация
Метод	Эндпоинт	Назначение
POST	/api/auth/login	Логин (auth_login / auth_failed)
POST	/api/auth/refresh	Обновление токена
POST	/api/auth/logout	Выход (auth_logout)
GET	/api/auth/me	Информация о пользователе
GET	/api/auth/mode	Режим аутентификации
GET	/api/auth/check	Проверка прав роли (WebUI-совместимый)
GET/POST/PUT/DELETE	/api/auth/users	CRUD пользователей (Admin, user_created/user_updated/user_deleted)
PUT	/api/auth/users/{id}/roles	role_assigned / role_revoked
POST	/api/auth/change-password	user_password_changed (self); BUG-201 — пароль реально меняется (пере-запрос user в сессии хендлера)
GET/POST	/api/auth/roles	Список/создание ролей (Admin) — role_created
PUT/DELETE	/api/auth/roles/{id}	Изменить/удалить роль (Admin) — role_updated / role_deleted (BUG-181, v3.13.39)

Каталог
Метод	Эндпоинт	Назначение
GET	/api/catalog/resources	Ресурсы (директории)
GET	/api/catalog/resources/{id}/findings	Строки файла с находками
GET	/api/catalog/tree	Дерево с находками на уровне строк
Аудит
Метод	Эндпоинт	Роль	Назначение
POST	/api/audit/agents/register	—	machine: регистрация агента → agent_id
POST	/api/audit/agents/heartbeat	—	machine: heartbeat агентов
POST	/api/audit/events	—	machine: приём событий (батч)
GET	/api/audit	Auditor+	Список событий (event_source, event_type, user, пагинация) — BUG-214
GET	/api/audit/stats	Auditor+	Агрегаты (by_source, by_type) + total_resources (BUG-142)
GET	/api/audit/{log_id}	Auditor+	Деталь события (AuditLogDetail, metadata_json); 404 при отсутствии (BUG-223)
POST	/api/audit/permissions	—	machine: приём событий прав (WebUI access)
Архивация
Метод	Эндпоинт	Назначение
GET	/api/retention/policies	Политики хранения
POST	/api/retention/run	Ручной запуск
GET	/api/retention/status	Статус
POST	/api/retention/export	Экспорт (JSON/CSV)
Метрики
Метод	Эндпоинт	Назначение
GET	/metrics	Prometheus-метрики Manager (публичный, вне /api/*)
GET	/api/health	Healthcheck (исключён из rate-limit)
Порядок middleware (BUG-103, v3.13.28): Metrics → RateLimit → Auth → CORS.
MetricsMiddleware регистрируется последним, поэтому в uvicorn он outermost
и видит ответы AuthMiddleware, включая 401.

Метка endpoint: берётся шаблон маршрута (/api/findings/{id}), а не сырой
путь. Если шаблон недоступен — regex-fallback _ID_RE подставляет {id} / {uuid} / {hash}.

📈 МОНИТОРИНГ
Метрики
Компонент	Порт	Ключевые метрики
Manager	:8000/metrics	dcap_http_*, dcap_tasks_total, dcap_findings_total, dcap_scanner_*, dcap_celery_queue_size
Scanner	:9101	dcap_scanner_files_scanned_total, dcap_scanner_findings_total, dcap_scanner_errors_total, dcap_scanner_current_task
Linux-агент	:9102	dcap_linux_*
S3-агент	:9103	dcap_s3_*
Celery	:9808	(celery-exporter)
PostgreSQL	:9187	(postgres-exporter)
Redis	:9121	(redis-exporter)
Heartbeat-thread (v3.7.0, backoff v3.13.20)
scanner/src/heartbeat.py — daemon, interval 30 с, fail-open.

text
POST /api/scanner/heartbeat с {scanner_id, status, current_task_id, progress}
⚠️ _mark_stale_scanners переводит задачи в failed у сканеров без heartbeat. Активной задачей защищается только сам сканер (status='assigned'), не задача.

Backoff (BUG-080, v3.13.20): BACKOFF_STEPS = [5, 10, 30, 60, 120]; фейлы — DEBUG, WARNING на 1-м и каждые 5; _stop.wait() вместо time.sleep().

Prometheus targets (6/6 up)
text
http://celery_exporter:9808/metrics       up
http://manager:8000/metrics               up
http://postgres_exporter:9187/metrics     up
http://redis_exporter:9121/metrics        up
http://s3_agent:9103/metrics              up
http://host.docker.internal:9101/metrics  up  (scanner, на хосте)
Алерты
Алерт	Условие	Severity
ScannerInactive	dcap_scanner_heartbeat_age_seconds > 120	warning
TaskFailed	increase(dcap_tasks_total{status="failed"}[5m]) > 0	critical
HighErrorRate	rate(dcap_http_requests_total{status=~"5.."}[5m]) > 0.05	critical
CeleryQueueBacklog	dcap_celery_queue_size > 100	warning
🗄️ RETENTION (v3.13.27)
API
Метод	Эндпоинт	Роль	Назначение
GET	/api/retention/policies	Admin	Политики хранения
GET	/api/retention/status	Admin	Текущий статус (last_run, running)
POST	/api/retention/run	Admin	Ручной запуск (sync в Manager), ?dry_run=true
POST	/api/retention/start	Admin	Запуск через Celery (run_retention.delay)
POST	/api/retention/export	Admin	Экспорт архива в файл
Все 5 эндпоинтов — require_admin.

run vs start:

run — синхронно в процессе Manager (для dry-run и отладки).

start — асинхронно через Celery (штатный путь, очередь retention).

⚠️ Тест, вызывающий только run, не покрывает Celery-путь: в процессе Manager auth.models импортирован, и BUG-102 там не воспроизводился.

Политики (default, manager/config/config.json → retention)
Категория	TTL	Архив	Примечание
audit_events	90 дней	✅ → audit_logs_archive	Гейт archive_enabled: true; архив живёт ещё 365 дней
findings	180 дней	✅ → findings_archive	Без гейта — архивируется всегда (TEST-NOTE-7.3)
tasks	30 дней	❌	scan_tasks, только завершённые
logs	rotate 30 дней / 100 МБ	—	Файловые логи
Global: enabled: true, interval_hours: 24.

Порядок шагов (retention/runtime.py): archive_audit → archive_findings → clean_archive → clean_tasks → export → rotate_logs.

Перемещение, а не копирование
_move_to_archive() делает add(archive) + delete(source) — запись из основной таблицы удаляется.

Партиционирование audit_logs
RANGE по created_at, 13 месяцев + default.

PK: (created_at, id).

Миграция 001_initial_postgres создаёт только 4 партиции; остальные добирает ensure_audit_log_partitions(months_ahead=12) при старте.

⚠️ DROP PARTITION в retention не используется — bulk DELETE WHERE created_at < cutoff.

Архивные таблицы
audit_logs_archive — копия схемы audit_logs + archived_at.

findings_archive — legacy-схема (до Findings Refactor v3.9.0). Маппинг lossy: subcategory всегда NULL, fingerprint/fragment_*/шифрование теряются. Удаление — BACKLOG-065.

BUG-102 (v3.13.27)
Проблема: Celery-воркер падал на Mapper[Finding] ... 'User' failed to locate a name.

Фикс: импорт User из auth.models в 6 модулях + configure_mappers() в celery_app.py.

Состояние retention
last_run / last_result — в памяти процесса (TEST-NOTE-7.2).

Персистятся в manager/data/retention_state.json, но у celery_worker в compose нет томов.

📤 SIEM-ИНТЕГРАЦИЯ (план, v3.1.0+)
⚠️ Статус: НЕ РЕАЛИЗОВАНО. Каталога manager/src/siem/ в репозитории нет, метрик dcap_siem_* тоже нет.

Назначение
Передача событий ИБ из DCAP в SIEM для централизованного мониторинга, корреляции, compliance (152-ФЗ, GDPR, PCI DSS), алертинга.

Форматы
Формат	Протокол	SIEM
Syslog (RFC 5424)	UDP / TCP / TLS	ArcSight, QRadar, MaxPatrol, Wazuh, rsyslog
JSON	HTTP/HTTPS (webhook)	Splunk HEC, Elastic, Kibana, кастомные SIEM
Планируемые события ИБ
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
⚠️ scanner_inactive и retention_run как event_type в audit_logs сейчас не пишутся.

Архитектура (план)
text
Manager (события) → EventGenerator → SIEMConnector
                                       ├── SyslogSender (UDP/TCP/TLS)
                                       └── JSONSender (HTTP/HTTPS)
                                              ├─→ Dead-letter queue (Redis) при ошибке
                                              └─→ Retry с backoff
Планируемые модули
text
manager/src/siem/              # ⚠️ не существует
├── generator.py               # генерация событий из findings/audit
├── config.py                  # конфигурация (Syslog/JSON)
├── senders/
│   ├── syslog_sender.py       # RFC 5424 (UDP/TCP/TLS)
│   └── json_sender.py         # HTTP/HTTPS webhook
└── queue.py                   # dead-letter + retry
Ключевые свойства (план)
Асинхронная отправка через Celery.

Retry с экспоненциальным backoff.

Dead-letter queue (Redis) при недоступности SIEM.

Метрики: dcap_siem_events_sent_total, dcap_siem_events_failed_total.

Безопасность (план)
Только маскированные match_text — без reveal.
match_text_encrypted не отправляется.

WebUI (BACKLOG-072)
⚠️ Страницы /settings/siem в webui/templates/ нет — бэклог.

v4.0.0+
Kafka / Kinesis — потоковая передача.

CEF / LEEF — если потребуется.

⚡ ОПТИМИЗАЦИЯ ПРОИЗВОДИТЕЛЬНОСТИ (план, v3.1.0+)
⚠️ Статус: НЕ РЕАЛИЗОВАНО. В репозитории нет ни Cargo.toml/*.rs, ни *.pyx/*.so, ни scanner-rust/, ни scanner-python/. Приведённые ниже цифры — оценки из BACKLOG, а не замеры.

Стратегия: Cython + Rust (гибрид)
Компонент	Технология	Прирост (оценка)	Приоритет
Regex-фильтры (_filter_url_over_email, _filter_spacy_noise)	Cython + cre/re2	3–10×	BACKLOG-090
Маскирование (mask_context, _CONTEXT_PATTERNS)	Cython	3–5×	BACKLOG-089
Entropy-анализ	Cython	5–10×	BACKLOG-089
Prefilter	Cython	3–5×	BACKLOG-089
Обход ФС (CIFS/NFS)	Rust (pavao, nfs-rs)	нативно	BACKLOG-036
Параллелизм	Rust (rayon)	N×CPU	BACKLOG-036
OCR (Tesseract)	Python (CLI)	—	—
Presidio/spaCy	Python (уже Cython внутри)	—	—
Ожидаемый эффект (оценка)
30–50% общего ускорения сканирования от Cython.

Дополнительно от параллелизма (Rust) на многоядерных CPU.

Без переписывания Presidio/spaCy.

TruffleHog (BACKLOG-091, v3.1.0+)
Идея: верификация credentials через API провайдера (AWS, GitHub, Slack, Stripe).
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
Cython + Rust (гибрид, план)	Cython — для горячих точек Python, Rust — для сетей/параллелизма
SIEM-модуль manager/src/siem/ (план)	Только CIFS/NFS + параллелизм (BACKLOG-036); классификаторы/PII — Python
Retention: чистка по created_at	DROP PARTITION не используется — archive-таблицы + bulk DELETE
ScanTask.source_type (явный, v3.13.29)	Сканер выбирает коннектор по source_type, не угадывая по префиксу source_path
_text_scanner.py + factory.py (v3.13.30)	Общий построчный пайплайн — S3LineConnector не копипастит логику FS
S3LineConnector — отдельный класс от S3Connector (v3.13.31)	SRP: ISourceConnector для Orchestrator vs построчный коннектор
Секреты S3 — ENV-only (TASK-018)	Manager не хранит и не передаёт секреты; fallback на config — временно (BACKLOG-103)
endpoint — вариант B (v3.13.32)	На стороне Manager нет хардкода: query → S3_DEFAULT_ENDPOINT → 400
Рекурсия S3 — всегда	Защита от пропуска вложенных объектов при ошибке конфигурации
Bucket S3 — только из scan_config (v3.13.35)	s3://bucket/prefix — суффикс префикса; bucket фиксируется при создании ресурса
BUG-136: strict-декод utf-8 → cp1251 → ignore	Ветка cp1251 была недостижимой из-за errors="ignore" в первой итерации
WebUI — редизайн Dovetail-style (v3.13.37, этап 1/5)	Dark-only, Inter + JetBrains Mono, #6798ff, 8px радиусы, zero-shadow, grid-wireframe. 53.4a ✅; 53.4a-доп3/4 ✅ (v3.13.39/40); 53.4b–53.4e 📋
.btn-primary = #1e1e1e (dark-carbon)	Отступление от DESIGN.md (white-filled) — dark-carbon ближе к «инструменту», не перегружает консоль
Семантические цвета (danger/success/warning) — приглушённые, только для бейджей	Иначе confirmed/false_positive не различить; DESIGN.md single-accent сохраняется в кнопках/фонах
Legacy-имена в tokens.css	--color-bg / --color-text / --color-surface / --color-primary и т.д. — чтобы components/*.css и findings.css подхватили без правок
Шрифты — локально (CDN запрещён), кириллица ✅ 	Inter Variable (352 KB, кириллица) + JetBrains Mono Variable (113 KB, v2.304, wght 100–800, кириллица) + unicode-range с Cyrillic (BUG-212, v3.13.40) + OFL.txt
Chart.js — монохром + акцент (план)	Single-chromatic accent — системное решение из DESIGN.md, этап 53.4d
Grid-wireframe — везде (план)	Blueprint-мотив на тёмной поверхности, body::before, этап 53.4a ✅
Технические
Решение	Обоснование
PostgreSQL + Redis в Docker	Production-готовность
ENV-ключи (не Docker Secrets)	Упрощение ротации, единый источник (TASK-018); SecretsManager (core/secrets.py) написан, но вызовов в коде нет
Единый формат событий (UnifiedEvent)	Унификация источников
Prometheus + Grafana + Alertmanager	Стандартный стек
spaCy-модели sm	Жёстко зашито в pii_classifier
spnego убран из requirements	Нет на PyPI, реальный — pyspnego
AES-256-GCM для находок	Стандарт для шифрования данных
Pytest + docker-compose.test.yml	Изолированные тесты
_clamp_int + OptInt	Валидация числовых query-параметров (BUG-084, 099)
forwarded_headers	WebUI-прокси: X-Total-Count, X-Fragment-*, Content-Disposition (BUG-087)
fetch + Blob + Bearer	Бинарные данные (fragment, export) — не <img>/window.location (BUG-088, 093)
SubmitStatus (OK/RETRY/LOST)	Оффлайн-буфер: 404/410 → LOST (BUG-097)
_CONTEXT_PATTERNS	mask_context: 22 паттерна, специфичные раньше generic (BUG-086)
_log_finding_status_change	Единая точка аудита PATCH/bulk; без commit — batch (BUG-101)
_apply_status	Единая функция PATCH/bulk; сброс review при new (BUG-100)
with_audit (v3.13.39)	Единая транзакция «бизнес-изменение + аудит»; исключение → rollback + raise (BUG-202); `api/resources.py`, PATCH findings, roles, change_password
change_password в сессии хендлера (v3.13.39)	НЕ мутировать request.state.user из middleware — commit пустой (BUG-201); пере-запрос user + commit/refresh + аудит после commit
Системные роли иммутабельны (v3.13.39)	admin/auditor/scanner/viewer: rename и cмена AD-группы → 400, description редактируется (BUG-168)
Аудит-API — Auditor+ (v3.13.39)	GET /api/audit, /api/audit/stats, GET /api/audit/{log_id} → 403 для viewer/scanner (BUG-214); деталь с metadata_json, 404 (BUG-223)
BUG-102: импорт User в 6 модулях	SQLAlchemy mapper init в Celery-контексте (Finding.reviewer)
run (sync) ≠ start (Celery)	Dry-run через API без очереди; Celery-путь — отдельно
_parent_of_path (в managed_scanner.py) для S3	Path('s3://bucket/key').parent сломан (даёт s3:/bucket) → urlparse + posixpath
create_line_connector(source_type, config)	Единая точка создания коннектора
S3LineConnector.scan_path — последовательный	Параллелизм S3 — v3.1.0 (BACKLOG-100)
decode_text_bytes — strict → cp1251 → ignore	BUG-136
endpoint = query или S3_DEFAULT_ENDPOINT или 400 (Manager)	Вариант B
CSS — 4 новых файла в 53.4a	tokens.css, base.css, components.css, grid-wireframe.css; main.css — только .app/.main-content/.page-content/.text-* + @media
ON DELETE CASCADE (BUG-150)	DELETE /api/resources/{id} → 204; миграция 007_add_cascade_deletes, 11 FK; findings_archive — отдельная foreign таблица без FK; для SQLite — ручное удаление в delete_resource
Bucket-фолбэк из path (BUG-149)	S3LineConnector.scan_path: config.bucket приоритетнее, иначе path.s3://bucket; единая точка self._bucket (list+read); таймайты re-raise
Legacy WebUI → connector.s3 (BUG-149)	/api/tasks/create и /api/resources/create для s3/minio строят connector.s3 (endpoint: S3_DEFAULT_ENDPOINT → host.docker.internal:9000)
.btn-primary white filled (BACKLOG-121, v3.13.41)	Отклонение 53.4a отменено: белый фон (#ffffff) + текст #0a0a0a; hover #a7a7a7; disabled #7c7c7c
Badge режима /login (BACKLOG-119, v3.13.41)	Показывается только для windows_integrated; для local/hybrid скрыт (login.html)
⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ
Ограничение	Описание	План
⚠️ BUG-150 (v3.13.41)	DELETE /api/resources/{id} → 500 (FK с NO ACTION)	✅ Исправлено миграцией 007_add_cascade_deletes (ON DELETE CASCADE) + 204. Тесты unit (3) + PG-верификация
⚠️ BUG-149 (v3.13.41)	S3-скан возвращал 0 files (WebUI-ресурсы без connector.s3)	✅ Исправлено: bucket-фолбэк из path, legacy-эндпоинты WebUI строят connector.s3, DEBUG-логи list_objects_v2. E2E test_s3_scan_v31341
/metrics публичный	Нет JWT/basic_auth	BACKLOG-044
Прогресс сканера	Не виден в WebUI	BACKLOG-043 (🔄)
NOT NULL поля	Возможны скрытые баги	BACKLOG-039
Параллельный батч	Форк один (OCRWorker)	BACKLOG-040 (v3.1.0)
NFS на Windows	Ограниченный клиент	Решено в nfs-rs (v3.1.0, плана нет в коде)
Presidio	Медленный на 100k+ строк	BACKLOG-063 (v3.1.0)
findings_old	Legacy-таблица в БД (только PG-миграция)	BACKLOG-065
WebUI legacy Findings	Деградация до 40.3	BACKLOG-061 (🔄)
order_by=severity	Лексикографический порядок (не семантический)	BUG-083 (v3.1.0)
/fragment для text_line	400 (не 404 + пояснение)	BUG-085 (v3.1.0)
OCR bbox	None до v3.1.0 (Tesseract без tsv)	BACKLOG-085
Сканер не перезапускается	После рестарта Docker/хоста	TEST-NOTE-5.8 (v3.1.0)
findings_archive	Архив findings (маппинг lossy)	BACKLOG-065
Retention state	Не виден Manager'у	TEST-NOTE-7.2
Findings без гейта archive_enabled	Архивируются всегда	TEST-NOTE-7.3
SIEM не реализован	Каталога manager/src/siem/ нет	BACKLOG (план)
Rust/Cython не реализованы	Нет .rs/.pyx/Cargo.toml	BACKLOG-036, 089, 090
Нет LICENSE	Файл отсутствует в репозитории	—
s3://* (все bucket'ы)	Не поддерживается — на каждый bucket свой Resource	—
recursive=false для S3	Не поддерживается (рекурсия всегда)	—
Параллелизм S3	scan_path последовательный	BACKLOG-100 (v3.1.0)
skip_prefixes для S3	Нет аналога skip_dirs	BACKLOG-099 (v3.1.0)
Fallback на config-секреты	S3LineConnector.__init__ берёт config.access_key/secret_key	BACKLOG-103 (v3.1.0)
Fallback endpoint в коннекторе	host.docker.internal:9000 при пустом endpoint	BACKLOG-103 (v3.1.0)
secure=false = verify=False	HTTP-endpoint — сертификат не проверяется	TEST-NOTE-6.11 → v3.1.0
Разные credentials на разные S3	Нужны отдельные инстансы сканера	v3.1.0
Chart.js палитра — не под Dovetail	Дефолтные цвета Chart.js на тёмной теме «выпадают»	53.4d
Grid-wireframe тонкий (~3 %)	Если визуально не видно — усилить до #161616	53.4e
docs/DESIGN.md нет	DESIGN.md временно в корне; перенос в docs/ — git mv	53.4e
Font Awesome (не stroke-SVG)	Остаётся в 53.4a–53.4e	BACKLOG-101 (v3.1.0)
WebUI light-тема	Не поддерживается (dark-only)	BACKLOG-102 (v3.1.0)
Теги docker-образов	Все — ${VERSION:-3.13.41}	✅ v3.13.41
📘 АДМИН-РУКОВОДСТВО (Дни 42.1–42.4)
Принцип: документация = проверенный факт.

⚠️ Фактически в docs/admin-guide/ лежат только 4 файла: 04-authentication.md, 05-security.md, 06-scanner.md, 10-troubleshooting.md. Остальное — план.

Структура docs/admin-guide/ (план)
Файл	Описание	Статус
README.md	Оглавление + быстрый старт	❌ нет
01-architecture.md	Обзор компонентов	❌ нет
02-installation.md	Установка (Docker + локально)	❌ нет
03-configuration.md	Все конфиги, env-переменные	❌ нет
04-authentication.md	local/AD/hybrid, RBAC	✅ есть
05-security.md	mTLS, ключи, секреты, аудит findings/auth, маскирование контекстов	✅ есть
06-scanner.md	Настройка, задания, FP, §8 S3/MinIO (53.2–53.3)	✅ есть
07-agents.md	Windows/Linux/S3	❌ нет
08-monitoring.md	Метрики, алерты	❌ нет
09-retention.md	Архивация	❌ нет
10-troubleshooting.md	Решение проблем	✅ есть
11-faq.md	Частые вопросы	❌ нет
Актуально на: 13.10.2026
Версия архитектуры: v3.13.41 (WebUI-редизайн — этап 1/5 (53.4a) закрыт; 53.4a-доп (v3.13.38), 53.4a-доп3 backend-critical (v3.13.39), 53.4a-доп4 шрифты кириллицы (v3.13.40), 53.4a-доп5 hotfix-backend (v3.13.41: BUG-150, BUG-149, BACKLOG-121, BACKLOG-119) закрыты; S3-коннектор — части 1–4 + fix-bucket + BUG-149; Блок 5, 7, 9 закрыты)