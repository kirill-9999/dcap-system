> **Обновляется архитектором.** План — редко, бэклог — по мере.
> Текущее состояние — в `STATE.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 12.10.2026
**Стратегия:** Windows First → Linux → S3/MinIO → Enterprise Ready → UI-редизайн → Rust + DLP + SIEM → ML

---

## 🚀 Вехи

| Версия | Статус | Ключевые фичи |
|--------|--------|---------------|
| v1.0.0-v2.1.0 | ✅ | Обнаружение, классификация, WebUI, Linux-агент |
| **v3.0.0** | **🔄 Финальный этап** | **Enterprise Ready + WebUI-редизайн (Dovetail, 53.4a ✅, 53.4a-доп ✅). Мастер-сессия v3.13.38 — найдено ~100 BUG + ~40 BACKLOG.** |
| v3.1.0 | 📋 | Rust Scanner (CIFS/NFS), DLP/ICAP, SMB, Webhook, облака, Per-scanner keys, SIEM, Cython, Formal Grammars, BOM fix (BUG-135), BUG-117/118/123/125/126/129/130 |
| v3.2.0 | 📋 | ML-классификаторы, embeddings, near-duplicate |
| v4.0.0 | 📋 | Zero-Trust, распределённый Manager, Kafka/Kinesis SIEM |

---

## 📋 v3.0.0 — ENTERPRISE READY (🔄 ФИНАЛЬНЫЙ ЭТАП)

### План по дням

| День | Задача | BACKLOG/BUG | Статус |
|------|--------|-------------|--------|
| 28-50.2 | (WebUI, AD, Findings Refactor, Scanner deep, Мониторинг, Masking, Retention, Блок 9, Блок 6) | см. STATE | ✅ до v3.13.27 |
| **51 (Блок 9)** | **Фикс-спринт Блок 9 (Безопасность)** — 10 BUG | TASK-074…084 | ✅ **v3.13.28** |
| **52 (Блок 6)** | **Блок 6 (Агенты): Windows + Linux + S3 + MinIO** | TASK-085…103 | ✅ **v3.13.28** |
| **53.1a (BACKLOG-097 ч.1)** | **Manager: `source_type` + S3-ресурсы, миграция 006** | TASK-104…109 | ✅ **v3.13.29** |
| **53.1b (BACKLOG-097 ч.2)** | **Scanner: фабрика + `_text_scanner.py` + boto3** | TASK-110…117 | ✅ **v3.13.30** |
| **53.2 (BACKLOG-097 ч.3)** | **Scanner: S3LineConnector (streaming, ENV, OCR)** | TASK-118…123 | ✅ **v3.13.31** |
| **53.3 (BACKLOG-097 ч.4)** | **E2E на MinIO + WebUI-форма S3 + docs** | TASK-129…133 | ✅ **v3.13.32** |
| **53.3-test-stand-fix** | **Тестовый стенд: healthcheck, авто-очистка** | — | ✅ **v3.13.34** |
| **53.3-fix-s3-bucket** | **`S3LineConnector`: bucket только из `scan_config`** | TASK-134…136 | ✅ **v3.13.35** |
| **53.3-fs-regress-ocr-diag (BUG-137)** | **Гонка temp-файлов `OCREngine`** | BUG-137 | ✅ **v3.13.36** |
| **53.3-fs-regress** | **Ручной регресс FS** | — | ✅ **07.10.2026** |
| **B (ручной FS-регресс)** | **12/12 пунктов** | — | ✅ **09.10.2026** |
| **53.4a (BACKLOG-093, этап 1/5)** | **WebUI-редизайн: токены + base + компоненты + grid-wireframe; локальные шрифты; `theme.js` удалён** | BACKLOG-093 | ✅ **v3.13.37** |
| **53.4a-доп (BACKLOG-093)** | **WebUI-фиксы: BUG-138/139/140** | BACKLOG-093 | ✅ **v3.13.38** |
| **53.4a-доп3 (hotfix)** | **Backend-critical hotfix: BUG-201/202/214/223/181/168/142/148** | BUG-201,202,214,223,181,168,142,148 | ✅ **v3.13.39** |
| **53.4a-доп4 (fonts, BUG-212)** | **unicode-range кириллицы + замена jetbrains-mono.woff2 (v2.304 variable) + OFL.txt** | BUG-212 | ✅ **v3.13.40** |
| **53.4a-доп5 (hotfix + sync)** | **BUG-150 (CASCADE 007, DELETE→204), BUG-149 (S3 bucket-фолбэк), BACKLOG-121 (.btn-primary white), BACKLOG-119 (badge /login), sync ARCHITECTURE.md** | BUG-150, BUG-149, BACKLOG-121, BACKLOG-119, BACKLOG-129 | ✅ **v3.13.41** |
| **Мастер-сессия v3.13.38** | **WebUI 1–17 + RBAC-прогон; ~100 BUG + ~40 BACKLOG** | — | ✅ **12.10.2026** |
| **53.4b (BACKLOG-093, этап 2/5)** | **WebUI-редизайн: login, dashboard, resources, findings + RBAC frontend + Responsive** | BACKLOG-093 | 📋 |
| **53.4c (BACKLOG-093, этап 3/5)** | **WebUI-редизайн: finding_detail, catalog, audit, scanners, access, resources** | BACKLOG-093 | 📋 |
| **53.4d (BACKLOG-093, этап 4/5)** | **WebUI-редизайн: roles, users, settings, footer, Chart.js палитра** | BACKLOG-093 | 📋 |
| **53.4e (BACKLOG-093, этап 5/5)** | **WebUI-редизайн: полировка, скриншоты, `docs/DESIGN.md`, favicon, CSP, E2E-очистка** | BACKLOG-093 | 📋 |
| **52.1** | **Linux-агент: метрики + сквозной поток + BUG-130** | — | 📋 |
| **52.2** | **Блок 6.5: сбор прав Windows (BUG-123, 127)** | — | 📋 |
| **54** | **Блок 11 (Отказоустойчивость)** | — | 📋 |
| **55** | **GitHub-пакет** — **только после 53.4e** | BACKLOG-028/046 | 📋 |
| **56** | **BUG-117 (Manager-маскирование, hotfix)** | — | 📋 |
| **57** | **Релиз v3.0.0** | — | 📋 |

> ⚠️ **Условие приёмки GitHub-пакета (день 55):** 53.4a–53.4e закрыты.
> Все 14 страниц WebUI в dark-теме, `theme.js` удалён, скриншоты в `docs/ui-screenshots/`,
> `docs/DESIGN.md` в репо.

### Бэклог v3.0.0 — активные задачи (топ-50)

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| **BUG-201** | Смена пароля не работает | 🔴🔴 | 📋 53.4a-доп3 |
| **BUG-202** | Audit пишется при откате | 🔴🔴 | 📋 53.4a-доп3 |
| **BUG-212** | Fonts unicode-range | 🔴 | 📋 53.4a-доп4 |
| **BUG-214** | /api/audit → viewer / scanner | 🔴🔴 | 📋 53.4a-доп3 |
| **BUG-223** | GET /api/audit/{id} — 404 | 🔴🔴 | 📋 53.4a-доп3 |
| **BUG-181** | Нет аудита ролей | 🔴 | 📋 53.4a-доп3 |
| **BUG-168** | Системные роли редактируются | 🔴 | 📋 53.4a-доп3 |
| **BUG-142** | KPI Ресурсов = 0 | 🔴 | 📋 53.4a-доп3 + 53.4b |
| **BUG-148** | Scanner .env | 🔴 | ✅ v3.13.39 |
| **BUG-150** | DELETE /api/resources/{id} → 500 (FK NO ACTION) | 🔴🔴 | ✅ v3.13.41 |
| **BUG-149** | S3-скан 0 files | 🔴🔴 | ✅ v3.13.41 |
| **BACKLOG-121** | .btn-primary white filled | 🟡 | ✅ v3.13.41 |
| **BACKLOG-119** | Badge режима /login | 🟡 | ✅ v3.13.41 |
| **BACKLOG-129** | FK без CASCADE | 🟡 | ✅ v3.13.41 |
| **BUG-232** | Модалки на mobile | 🔴 | 📋 53.4b |
| **BUG-233** | Гамбургер не работает | 🔴 | 📋 53.4b |
| **BUG-213** | Frontend RBAC не работает | 🔴 | 📋 53.4b |
| **BUG-117** | Manager не маскирует контексты сам | 🔴 | 📋 день 56 |
| **BUG-118** | Auth middleware 2 соединения | 🔴 | 📋 v3.1.0 |
| **BUG-135** | S3-агент: BOM | 🟡 | 📋 v3.1.0 |
| **BUG-123** | Windows-агент: сбор прав = 0 | 🟡 | 📋 52.2 |
| **BACKLOG-093** | Редизайн WebUI (Dovetail) | 🔴 | 🔄 53.4a-доп3/4 + 53.4b–e |
| **Linux-агент дотест** | Метрики, сквозной поток, BUG-130 | 🔴 | 📋 52.1 |
| **BUG-172** | Нет permissions в RBAC | 🔴 | 📋 архитектура |
| **BACKLOG-028** | Публикация на GitHub | 🔴 | 📋 55 |
| **BACKLOG-046** | Полный E2E-прогон на CI | 🔴 | 📋 55 |
| **BACKLOG-044** | Защита `/metrics` | 🟡 | 📋 production |
| **BACKLOG-094** | WebUI/Manager не пересобирается автоматически | 🟡 | 📋 |
| **BUG-155…236** | (все остальные) | 🟡/🟢 | 📋 53.4b–e |
| **BACKLOG-131…155** | (все UI-улучшения) | 🟡/🟢 | 📋 53.4b–e |

### Бэклог v3.0.0 — ЗАКРЫТЫЕ (кратко)

| ID | Название | Закрыт в |
|----|----------|----------|
| BACKLOG-010…086 | (см. предыдущие ROADMAP) | v3.0.0 |
| TASK-051/052 (BUG-080/081) | Heartbeat backoff + graceful shutdown | v3.13.20 |
| TASK-053 (BUG-086) | Masking контекстов | v3.13.21 |
| TASK-054…059 (BUG-087…093) | WebUI фильтры/пагинация/аудит/экспорт | v3.13.22 |
| TASK-060 (BUG-094) | Аудит reveal — ложное | v3.13.23 |
| TASK-061/062 (BUG-095) | Аудит аутентификации | v3.13.24 |
| TASK-064…066 (BUG-096/096b/097) | FP 500, E2E, зависшие задания | v3.13.25 |
| TASK-067…071 (BUG-098…101, 101b) | PATCH/bulk/DELETE аудит, review, FP | v3.13.26 |
| TASK-072/073 (BUG-102) | Retention + sweep (Celery mapper) | v3.13.27 |
| TASK-074…084 (BUG-103, 105…108, 110, 111, 114…116) | **Блок 9 (Безопасность)** | **v3.13.28** |
| TASK-085…103 (BUG-120, 122) | **Блок 6 (Агенты)** | **v3.13.28** |
| TASK-104…109 (BACKLOG-097 ч.1) | **Manager: `source_type` + S3-ресурсы** | **v3.13.29** |
| TASK-110…117 (BACKLOG-097 ч.2) | **Scanner: фабрика + `_text_scanner.py` + boto3** | **v3.13.30** |
| TASK-118…123 (BACKLOG-097 ч.3, BUG-136) | **S3LineConnector + BUG-136 fix** | **v3.13.31** |
| TASK-129…133 (BACKLOG-097 ч.4) | **E2E + WebUI-форма S3 + docs** | **v3.13.32** |
| 53.3-test-stand-fix | **Автоматизация E2E-стенда** | **v3.13.34** |
| TASK-134…136 (53.3-fix-s3-bucket) | **Bucket только из `scan_config`, BACKLOG-103** | **v3.13.35** |
| BUG-137 (53.3-fs-regress-ocr-diag) | **Гонка temp-файлов `OCREngine`** | **v3.13.36** |
| 53.3-fs-regress | **Ручной регресс FS (cp1251, PII, OCR)** | **07.10.2026** |
| B (ручной FS-регресс после BUG-137) | **12/12 пунктов** | **09.10.2026** |
| **53.4a (BACKLOG-093, этап 1/5)** | **WebUI-редизайн: токены + base + компоненты + grid-wireframe; локальные шрифты; `theme.js` удалён** | **v3.13.37** |
| **53.4a-доп (BACKLOG-093)** | **WebUI-фиксы: BUG-138/139/140** | **v3.13.38** |
| **Мастер-сессия v3.13.38** | **WebUI 1–17 + RBAC; ~100 BUG + ~40 BACKLOG** | **12.10.2026** |

---

## 📋 TEST-NOTE (не баги, требуют внимания)

### TEST-NOTE — Блок 3, 5, 7

| ID | Название | Приоритет |
|----|----------|-----------|
| TEST-NOTE-3.1 | `text_extensions` в JSON игнорируется | 📋 док |
| TEST-NOTE-3.2 | `byte_range` для `.bin` не реализован | 🟢 v3.1.0 |
| TEST-NOTE-5.2 | ARCHITECTURE.md: имена полей API | 📋 док |
| TEST-NOTE-5.3 | Export CSV содержит BOM | 🟢 v3.1.0 |
| TEST-NOTE-5.5 | Осиротевшие сканеры после обновления | 🟡 v3.0.0 |
| TEST-NOTE-5.6 | `GET /api/findings` без `task_id` | 📋 док |
| TEST-NOTE-5.7 | `event_type=finding_reveal` vs `action` | 📋 v3.1.0 |
| TEST-NOTE-5.8 | Сканер не перезапускается автоматически | 📋 v3.1.0 |
| TEST-NOTE-5.9 | `by_detector` отсутствует в `/stats` | 🟢 v3.1.0 |
| TEST-NOTE-5.10 | Глобальная статистика устаревшая | 📋 док |
| TEST-NOTE-5.11 | E2E `_assign_task` конкурирует | 🟡 v3.0.0 |
| TEST-NOTE-5.12 | `--remove-orphans` сносит стек | 🟡 v3.0.0 |
| TEST-NOTE-5.13 | Stale-сканеры в БД | 🟢 v3.1.0 |
| TEST-NOTE-7.1 | `findings_archive` — legacy | 📋 док |
| TEST-NOTE-7.2 | `retention.state` — в файле воркера | 📋 v3.1.0 |
| TEST-NOTE-7.3 | `findings.ttl_days=180` — без архивации | 📋 v3.1.0 |
| TEST-NOTE-7.4 | `run` (sync) ≠ `start` (Celery) | 📋 док |
| TEST-NOTE-7.5 | Flower не видит worker'ов | 🟢 v3.1.0 |

### TEST-NOTE — Блок 6

| ID | Название |
|----|----------|
| TEST-NOTE-6.1 | MinIO через нативные бинарники (registry proxy) |
| TEST-NOTE-6.2 | `sudo` требует пароль в WSL |
| TEST-NOTE-6.3 | CloudTrail-формат seed-логов не поддерживается |
| TEST-NOTE-6.4 | Linux-агент использует `watchdog` |
| TEST-NOTE-6.5 | Проверка прав — в PostgreSQL, не в SQLite |
| TEST-NOTE-6.6 | Счётчик S3 `events_sent=16` при 9 валидных |
| TEST-NOTE-6.7 | Python 3.13 `datetime.utcnow()` deprecation |
| TEST-NOTE-6.8 | Кириллица в логах — PS 5.1 читает ANSI |
| TEST-NOTE-6.9 | Docker Desktop зависает после длительной работы |
| TEST-NOTE-6.10 | Rate-limit 300/60s мешает тестированию |
| TEST-NOTE-6.11 | `secure=false` = `verify=False` |

### TEST-NOTE — Блок 9

| ID | Название |
|----|----------|
| TEST-NOTE-9.1 | Rate-limit per-IP, whitelist не параметризован |
| TEST-NOTE-9.2 | Prometheus → Manager plain HTTP |
| TEST-NOTE-9.3 | Prometheus 5/6 при незапущенном сканере |
| TEST-NOTE-9.5 | `check_hostname=False` |
| TEST-NOTE-9.7 | `from_env_or_default` без fail-fast |
| TEST-NOTE-9.8 | `SecretsManager` — мёртвый код |
| TEST-NOTE-9.9 | Ротация ключей не реализована |
| TEST-NOTE-9.10 | Артефакты старых E2E в `audit_logs` |
| TEST-NOTE-9.11 | ORM PK ≠ БД PK (`audit_logs`) |
| TEST-NOTE-9.12 | `default={}` (mutable) в AuditLog |
| TEST-NOTE-9.13 | `source_host` = IP WebUI |
| TEST-NOTE-9.15 | `commit` на каждое событие аудита |
| TEST-NOTE-9.16 | `action` ≠ `event_type` |
| TEST-NOTE-9.17 | `require_viewer` = `require_auth` |
| TEST-NOTE-9.18 | `user_roles` без PK/CASCADE |

### TEST-NOTE — Дни 53.1a–53.4

| ID | Название | Статус |
|----|----------|--------|
| TEST-NOTE-10.1 | Alembic из PowerShell уходит в SQLite | 📋 док |
| TEST-NOTE-10.2 | Артефакты E2E-сканеров накапливаются (106+) | 📋 53.4e |
| TEST-NOTE-10.3 | Дубли секций в `scan_config` старых FS-ресурсов | 📋 бэклог |
| TEST-NOTE-10.4 | BUG-136 меняет поведение FS-пути (cp1251) | ✅ закрыто в B |
| TEST-NOTE-10.5 | Smoke FS в 53.1b был слабый | ✅ закрыто в 53.3-fs-regress |
| TEST-NOTE-10.6 | healthcheck `manager_test`/`webui_test` | ✅ **fixed v3.13.34** |
| TEST-NOTE-10.7 | `run-tests.sh all` делает `down -v` + `up -d --wait` | ✅ **fixed v3.13.34** |
| TEST-NOTE-10.8 | 2 legacy-теста WebUI требуют непустую findings | 📋 отдельный день |
| TEST-NOTE-10.9 | Docker Compose v5.5.1 поддерживает `up -d --wait` | ✅ |
| TEST-NOTE-10.10 | 4 E2E-теста флакают без живого сканера на `:18000` | 📋 микро-день |
| TEST-NOTE-10.11 | `/api/health` в dev-режиме отдаёт `version: unknown` | 📋 док |
| TEST-NOTE-10.12 | Два Manager на одном порту `:8000` | 📋 док |
| TEST-NOTE-10.13 | `GET /api/scanner` возвращает `{value, Count}` | 📋 унификация API |
| TEST-NOTE-10.14 | `files_scanned=10` вместо 9 — не баг | ✅ |
| TEST-NOTE-10.15 | ~40% находок — ложные (url/organization/us_driver_license/nrp) | 📋 качество детекции |
| TEST-NOTE-10.16 | `person` не маскируется — связано с BUG-117 | 🔗 BUG-117 |

### TEST-NOTE — Мастер-сессия v3.13.38

| ID | Название | Статус |
|----|----------|--------|
| **TEST-NOTE-NEW-1** | `/api/resources` — default limit=100 | 📋 53.4c |
| **TEST-NOTE-NEW-2** | `/api/access/resources` — без limit | 📋 53.4c |
| **TEST-NOTE-NEW-3** | Маска `aws_secret` = `=wJalr***` — сохраняет `=` (design по BUG-086) | 📋 design |
| **TEST-NOTE-NEW-4** | 8 проблем в Console — `[DOM]` password field | 📋 53.4e |

---

## 📋 v3.1.0 — RUST + DLP + SIEM + OPTIMIZATION

### План по дням

| День | Задача | ID | Приоритет |
|------|--------|-----|-----------|
| 58-59 | Rust Scanner (CIFS/NFS + параллелизм) | BACKLOG-036 | 🔴 |
| 60 | Cython-оптимизация горячих точек | BACKLOG-089 | 🟡 |
| 61 | Быстрые regex: `cre` / `re2` | BACKLOG-090 | 🟡 |
| 62 | ICAP Connector (DLP) | BACKLOG-032 | 🟡 |
| 63 | DLP Политики (WebUI) | BACKLOG-033 | 🟡 |
| 64 | SMB-сканер (Rust) | BACKLOG-035 | 🟡 |
| 65 | SIEM: генерация событий (Syslog + JSON) | BACKLOG-069 | 🔴 |
| 66 | SIEM: экспорт findings/audit | BACKLOG-070 | 🔴 |
| 67 | SIEM: WebUI настройки | BACKLOG-072 | 🟡 |
| 68 | Per-scanner keys | BACKLOG-068 | 🟡 |
| 69 | Multi-key режим (ротация без downtime) | — | 🟡 |
| 70 | **BUG-135: BOM в JSON S3-агента** | — | 🟡 |
| 71 | **BUG-123: сбор прав Windows** | — | 🟡 |
| 72 | **BUG-118: Auth middleware 1 соединение** | — | 🔴 |
| 73 | **BUG-125/126/129/130: агенты** | — | 🟡 |
| 74 | **BUG-117: Manager-маскирование** (если не в v3.0.0) | — | 🔴 |
| 75 | **Formal Grammars (CFG + AST)** — JSON/XML/CSV + tree-sitter | — | 🔴 |
| 76 | **Post-Processor (NER + relations)** | — | 🟡 |
| 77 | Red teaming, SAST, SCA | BACKLOG-022 | 🔴 |
| 78 | Релиз v3.1.0 | — | 🔴 |

### Бэклог v3.1.0

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-036 | Rust Scanner — CIFS/NFS + параллелизм | 🔴 |
| **BUG-135** | S3-агент: BOM в JSON | 🟡 |
| **BUG-123** | Windows-агент: сбор прав | 🟡 |
| **BUG-118** | Auth middleware: 1 соединение | 🔴 |
| **BUG-125** | Linux-агент: MANAGER_URL env | 🟡 |
| **BUG-126** | S3-агент: verify_ssl строковый | 🟢 |
| **BUG-129** | Windows-агент: шум | 🟡 |
| **BUG-130** | Linux-агент: retry без backoff | 🟡 |
| **BUG-132** | S3-агент: соединение | 🟢 |
| **BUG-121** | README Windows-агента | 🟢 |
| **BUG-124** | `docker-compose.s3.yml` конфликт | 🟢 |
| **BUG-128** | Кириллица в логах | 🟢 |
| **Formal Grammars** | CFG-парсеры (JSON/XML/CSV) + AST | 🔴 |
| **Post-Processor** | NER + relations | 🟡 |
| BACKLOG-089 | Cython-оптимизация | 🟡 |
| BACKLOG-090 | Быстрые regex | 🟡 |
| BACKLOG-091 | TruffleHog | 🟡 |
| BACKLOG-092 | Гибрид Cython + Rust | 🟡 |
| BACKLOG-096 | `run_scanner.py` — `start_metrics_server` | 🟢 |
| BACKLOG-032 | ICAP Connector | 🟡 |
| BACKLOG-033 | DLP Политики | 🟡 |
| BACKLOG-035 | SMB-сканер | 🟡 |
| BACKLOG-040 | Параллельный батч-сканер | 🟡 |
| BACKLOG-048 | Rate-limit bypass для тестов | 🟡 |
| BACKLOG-063 | Presidio: производительность | 🟡 |
| BACKLOG-064 | Бенчмарк сканирования | 🟢 |
| BACKLOG-068 | Per-scanner keys | 🟡 |
| BACKLOG-069 | SIEM: генерация событий | 🔴 |
| BACKLOG-070 | SIEM: экспорт | 🔴 |
| BACKLOG-072 | SIEM: WebUI | 🟡 |
| BACKLOG-076 | Manager: findings_updated | 🟡 |
| BACKLOG-077 | Сканер: heartbeat до инициализации | 🟢 |
| BACKLOG-080…082 | Тестирование агентов | 🟡 |
| BUG-060 | BOM ломает маскирование email | 🟢 |
| BUG-076 | Scanner: current_task | 🟢 |
| BUG-083 | order_by=severity | 🟢 |
| BUG-085 | /fragment text_line → 404 | 🟢 |
| BACKLOG-011 | Webhook для MinIO | 🟢 |
| BACKLOG-012 | Облачные хранилища | 🟢 |
| BACKLOG-017 | Обработка архивов | 🟡 |
| BACKLOG-018 | Распределённая архитектура | 🔴 |
| BACKLOG-022 | Red teaming, SAST, SCA | 🔴 |
| **BACKLOG-099…103** | S3-сканер (skip_prefixes, параллелизм, FA, light, fallback) | 🟢 |
| **Cyrylic-subsets** | unicode-range — закрыть в 53.4a-доп4 | ✅ (перенесено) |

---

## 📋 v3.2.0 — ML + DISTRIBUTED

| День | Задача | Приоритет |
|------|--------|-----------|
| 79-80 | ML-классификаторы (embeddings) | 🔴 |
| 81 | Near-duplicate detection (MinHash) | 🟡 |
| 82 | Аномалии в аудите | 🟡 |
| 83 | Zero-Trust архитектура | 🔴 |
| 84 | Распределённый Manager | 🔴 |
| 85 | SIEM: Kafka / Kinesis | 🟡 |
| 86 | Версионирование данных | 🟢 |
| 87 | Релиз v3.2.0 | 🔴 |

---

## 📊 Статистика

| Версия | Задач | Выполнено | Прогресс |
|--------|-------|-----------|----------|
| v1.0.0-v2.1.0 | 27 | 27 | 100% ✅ |
| **v3.0.0** | **~235** | **~135** | **~57% 🔄** |
| v3.1.0 | 45 | 0 | 0% 📋 |
| v3.2.0 | 9 | 0 | 0% 📋 |
| v4.0.0 | 9 | 0 | 0% 📋 |
| **ИТОГО** | **~325** | **~162** | **~50%** |

> ⚠️ Резкий скачок задач в v3.0.0 — **мастер-сессия 12.10.2026** (WebUI 1–17 + RBAC): ~100 BUG + ~40 BACKLOG.

---

## 📝 Шаблон новой задачи

| BACKLOG-XXX / BUG-XXX / TASK-XXX | Название | 🔴/🟡/🟢 | 📋/🔄/✅/❌ |
|-----------------------------------|----------|----------|-------------|

**Приоритеты:** 🔴 критично / 🟡 важно / 🟢 nice-to-have
**Статусы:** 📋 запланировано / 🔄 в работе / ✅ выполнено / ❌ отменено

---

## 📚 Связанные документы

- **`STATE.md`** — текущее состояние проекта.
- **`STATE_TEST_SESSION.md`** — протокол тестирования.
- **`ARCHITECTURE.md`** — архитектура, модели, API, SIEM.
- **`docs/DESIGN.md`** — style reference WebUI (Dovetail). ⚠️ Пока `DESIGN.md` в корне (перенос в 53.4e).
- **ТЗ (активные):** `prompts/tz/day_53_4b_webui_pages_1.md`, `day_53_4cde_webui_pages_2_5.md`.
- **ТЗ (архив):** `TZ_FIX_SPRINT.md` … `TZ_BLOCK6_*.md`, `day_53_*_*.md`.
- **`SECURITY.md`**, **`docs/security_checklist.md`**, **`docs/admin-guide/05-security.md`**.

---

**Актуально на:** 13.10.2026
**Версия:** v3.13.41
**Следующая цель:** 53.4b → 53.4c/d/e → 55 (GitHub-пакет) → 57 (релиз v3.0.0)