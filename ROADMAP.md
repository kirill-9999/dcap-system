> **Обновляется архитектором.** План — редко, бэклог — по мере.
> Текущее состояние — в `STATE.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 04.10.2026
**Стратегия:** Windows First → Linux → S3/MinIO → Enterprise Ready → UI-редизайн → Rust + DLP + SIEM

---

## 🚀 Вехи

| Версия | Статус | Ключевые фичи |
|--------|--------|---------------|
| v1.0.0-v2.1.0 | ✅ | Обнаружение, классификация, WebUI, Linux-агент |
| **v3.0.0** | **🔄 Финальный этап** | **Enterprise Ready: S3-сканер, AD, mTLS, архивация, Findings Refactor, ENV-ключи, RBAC, Блок 9, Блок 6, WebUI-редизайн (Dovetail)** |
| v3.1.0 | 📋 | Rust Scanner (CIFS/NFS), DLP/ICAP, SMB, Webhook, облака, Per-scanner keys, SIEM, Cython, BOM fix (BUG-135), BUG-123/125/126/129/130, BUG-118 |
| v4.0.0 | 📋 | ML-классификаторы, Zero-Trust, распределённый Manager, Kafka/Kinesis SIEM |

---

## 📋 v3.0.0 — ENTERPRISE READY (🔄 ФИНАЛЬНЫЙ ЭТАП)

### План по дням

| День | Задача | BACKLOG/BUG | Статус |
|------|--------|-------------|--------|
| 28-47.7 | (WebUI, AD, Findings Refactor, Scanner deep, Мониторинг, Masking) | см. STATE | ✅ до v3.13.21 |
| 48-50.2 | (WebUI, аудит, Retention, BUG-102) | | ✅ до v3.13.27 |
| **51 (Блок 9)** | **Фикс-спринт Блок 9 (Безопасность)** — 10 BUG | TASK-074…084 | ✅ **v3.13.28** |
| **52 (Блок 6)** | **Блок 6 (Агенты): Windows + Linux + S3 + MinIO** | TASK-085…103 | ✅ **v3.13.28** |
| **53.1a (BACKLOG-097 ч.1)** | **Manager: `source_type` + S3-ресурсы, миграция 006** | TASK-104…109 | ✅ **v3.13.29** |
| **53.1b (BACKLOG-097 ч.2)** | **Scanner: фабрика + `_text_scanner.py` + boto3** | TASK-110…117 | ✅ **v3.13.30** |
| **53.2 (BACKLOG-097 ч.3)** | **Scanner: S3LineConnector (streaming, ENV, OCR)** | TASK-118…123 | ✅ **v3.13.31** |
| **53.3 (BACKLOG-097 ч.4)** | **E2E на MinIO + WebUI-форма S3 + docs** | TASK-129…133 | ✅ **v3.13.32** |
| **53.3-fix-s3-bucket** | **`S3LineConnector`: bucket только из `scan_config` (BACKLOG-103 заведён)** | TASK-134…136 | ✅ **v3.13.33** |
| **53.3-fs-regress** | **Ручной регресс FS после 53.1b/53.2 (cp1251, PII, OCR)** | — | 📋 **следующий** |
| **53.4a** | **WebUI-редизайн (этап 1): токены + base + компоненты** | BACKLOG-093 | 📋 |
| **53.4b** | **WebUI-редизайн (этап 2): login, dashboard, resources, findings** | BACKLOG-093 | 📋 |
| **53.4c** | **WebUI-редизайн (этап 3): finding_detail, catalog, audit, scanners, access** | BACKLOG-093 | 📋 |
| **53.4d** | **WebUI-редизайн (этап 4): roles, users, settings, footer, графики** | BACKLOG-093 | 📋 |
| **53.4e** | **WebUI-редизайн (этап 5): полировка, скриншоты, docs/DESIGN.md** | BACKLOG-093 | 📋 |
| **52.1** | **Linux-агент: метрики + сквозной поток + BUG-130** | — | 📋 |
| **52.2** | **Блок 6.5: сбор прав Windows (BUG-123, 127)** | — | 📋 |
| **54** | **Блок 11 (Отказоустойчивость)** | — | 📋 |
| **55** | **GitHub-пакет** — **только после 53.4e** | BACKLOG-028/046 | 📋 |
| **56** | **BUG-117 (Manager-маскирование, hotfix)** | — | 📋 |
| **57** | **Релиз v3.0.0** | — | 📋 |

> ⚠️ **Условие приёмки GitHub-пакета (день 55):** 53.4a–53.4e закрыты.
> Все 14 страниц WebUI в dark-теме, `theme.js` удалён, скриншоты в `docs/ui-screenshots/`,
> `docs/DESIGN.md` в репо.

### Бэклог v3.0.0 — активные задачи

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| **FS-регресс** | Проверка FS-пути после 53.1b/53.2 (cp1251, PII, OCR) | 🔴 | 📋 53.3-fs-regress |
| **BACKLOG-093** | **Редизайн WebUI (Dovetail-style, `DESIGN.md`)** | 🔴 | 📋 **53.4a–53.4e, до GitHub-пакета** |
| **Linux-агент дотест** | Метрики, сквозной поток, BUG-130 | 🔴 | 📋 52.1 |
| **BUG-117** | Manager не маскирует контексты сам | 🔴 | 📋 56 |
| **BUG-123** | Windows-агент: сбор прав = 0 | 🟡 | 📋 52.2 |
| **BUG-135** | S3-агент: `json.loads` падает на BOM | 🟡 | 📋 v3.1.0 |
| **BACKLOG-028** | Публикация на GitHub | 🔴 | 📋 55 |
| **BACKLOG-046** | Полный E2E-прогон на CI | 🔴 | 📋 55 |
| **BACKLOG-044** | Защита `/metrics` | 🟡 | 📋 production |
| **BACKLOG-094** | WebUI/Manager не пересобирается автоматически | 🟡 | 📋 |
| **SQLAlchemy pin** | Закрепить версию в `requirements.txt` | 🟡 | ✅ v3.13.28 |
| **BUG-118** | Auth middleware держит 2 соединения | 🔴 | 📋 v3.1.0 |
| **BUG-125** | Linux-агент: `MANAGER_URL` env игнорируется | 🟡 | 📋 v3.1.0 |
| **BUG-126** | S3-агент: `verify_ssl` строковый | 🟢 | 📋 v3.1.0 |
| **BUG-129** | Windows-агент: шум от собственного чтения | 🟡 | 📋 v3.1.0 |
| **BUG-130** | Linux-агент: retry без backoff | 🟡 | 📋 v3.1.0 |
| **BUG-131** | WSL → Manager: localhost терялся | ✅ | само-исправился |
| **BUG-132** | S3-агент: не переустанавливает соединение | 🟢 | 📋 v3.1.0 |
| **BUG-121** | README Windows-агента: неверный SACL | 🟢 | 📋 v3.1.0 |
| **BUG-124** | `docker-compose.s3.yml` конфликт | 🟢 | 📋 v3.1.0 |
| **BUG-128** | Кириллица в логах | 🟢 | 📋 док |
| **BACKLOG-039** | Аудит NOT NULL полей | 🟡 | 📋 |
| **BACKLOG-045** | Параметризация портов экспортеров | 🟢 | 📋 |
| **BACKLOG-047** | `/api/health` версия — синхронизация | 🟡 | ✅ v3.13.28 |
| **BACKLOG-065** | Удалить `findings_old` + `findings_archive` | 🟢 | 📋 |
| **BACKLOG-078** | Linux-агент вне Docker | 🟢 | ✅ v3.13.28 |
| **BACKLOG-080…082** | Тестирование агентов | 🟡 | ✅ v3.13.28 |
| **BACKLOG-083** | Alertmanager webhook → Manager | 🟡 | 📋 v3.0.0 |
| **TEST-NOTE-5.5** | Осиротевшие сканеры после обновления | 🟡 | 📋 |
| **TEST-NOTE-5.11** | E2E `_assign_task` конкурирует со сканером | 🟡 | 📋 |
| **TEST-NOTE-5.12** | `--remove-orphans` сносит основной стек | 🟡 | 📋 |
| **TEST-NOTE-10.1** | Alembic из PowerShell уходит в SQLite | 🟡 | 📋 док |
| **TEST-NOTE-10.2** | Артефакты E2E-сканеров накапливаются | 🟡 | 📋 бэклог |
| **TEST-NOTE-10.3** | Дубли секций в `scan_config` старых FS-ресурсов | 🟡 | 📋 бэклог |
| **TEST-NOTE-10.4** | BUG-136 меняет поведение FS-пути | 🟡 | ⏳ 53.3-fs-regress |
| **TEST-NOTE-10.5** | Smoke FS в 53.1b был слабый | 🟡 | ⏳ 53.3-fs-regress |
| **BACKLOG-099 (внутр.)** | S3-сканер: `skip_prefixes` (аналог `skip_dirs`) | 🟢 | 📋 v3.1.0 |
| **BACKLOG-100 (внутр.)** | S3-сканер: параллельное сканирование | 🟢 | 📋 v3.1.0 |
| **BACKLOG-103** | S3-сканер: fallback на config-секреты (политика TASK-018) | 🟡 | 📋 v3.1.0 |

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
| **TASK-129…133 (BACKLOG-097 ч.4)** | **E2E + WebUI-форма S3 + docs** | **v3.13.32** |

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

### TEST-NOTE — День 53.1a

| ID | Название |
|----|----------|
| TEST-NOTE-10.1 | Alembic из PowerShell на Windows уходит в SQLite |
| TEST-NOTE-10.2 | Артефакты E2E-сканеров накапливаются (101+) |
| TEST-NOTE-10.3 | Дубли секций в `scan_config` старых FS-ресурсов |

### TEST-NOTE — День 53.2

| ID | Название |
|----|----------|
| TEST-NOTE-10.4 | BUG-136 меняет поведение FS-пути (cp1251 теперь декодируется) |
| TEST-NOTE-10.5 | Smoke FS в 53.1b был слабый (1 файл) |

### TEST-NOTE — День 53.3

| ID | Название |
|----|----------|
| TEST-NOTE-10.6 | ✅ **fixed v3.13.34** — healthcheck `manager_test`/`webui_test` + `up --wait` вместо ручного `restart manager_test` |
| TEST-NOTE-10.7 | ✅ **fixed v3.13.34** — `scripts/run-tests.sh all` делает `down -v` + `up -d --wait` автоматически |
| TEST-NOTE-10.8 | 2 legacy-теста WebUI требуют непустую таблицу findings (`X-Total-Count != "0"`) — вне ТЗ стенда, отдельный день |

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
| 75 | Red teaming, SAST, SCA | BACKLOG-022 | 🔴 |
| 76 | Релиз v3.1.0 | — | 🔴 |

### Бэклог v3.1.0

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-036 | Rust Scanner — **CIFS/NFS + параллелизм** | 🔴 |
| **BUG-135** | S3-агент: `json.loads` падает на BOM | 🟡 |
| **BUG-123** | Windows-агент: сбор прав = 0 | 🟡 |
| **BUG-118** | Auth middleware: 1 соединение (eager roles) | 🔴 |
| **BUG-125** | Linux-агент: `MANAGER_URL` env | 🟡 |
| **BUG-126** | S3-агент: `verify_ssl` строковый | 🟢 |
| **BUG-129** | Windows-агент: шум от собственного чтения | 🟡 |
| **BUG-130** | Linux-агент: retry без backoff | 🟡 |
| **BUG-132** | S3-агент: не переустанавливает соединение | 🟢 |
| **BUG-121** | README Windows-агента | 🟢 |
| **BUG-124** | `docker-compose.s3.yml` конфликт | 🟢 |
| **BUG-128** | Кириллица в логах | 🟢 |
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
| BACKLOG-076 | Manager: `findings_updated` | 🟡 |
| BACKLOG-077 | Сканер: heartbeat до инициализации | 🟢 |
| BACKLOG-080…082 | Тестирование агентов | 🟡 |
| BUG-060 | BOM ломает маскирование email | 🟢 |
| BUG-076 | Scanner: `current_task` | 🟢 |
| BUG-083 | `order_by=severity` | 🟢 |
| BUG-085 | `/fragment` text_line → 404 | 🟢 |
| BACKLOG-011 | Webhook для MinIO | 🟢 |
| BACKLOG-012 | Облачные хранилища | 🟢 |
| BACKLOG-017 | Обработка архивов | 🟡 |
| BACKLOG-018 | Распределённая архитектура | 🔴 |
| BACKLOG-022 | Red teaming, SAST, SCA | 🔴 |
| **BACKLOG-103** | **Убрать fallback на config-секреты в `S3LineConnector`/`S3Connector`** (политика TASK-018 — только ENV) | 🟡 |
| **BACKLOG-099 (внутр.)** | S3-сканер: `skip_prefixes` | 🟢 |
| **BACKLOG-100 (внутр.)** | S3-сканер: параллельное сканирование | 🟢 |
| **BACKLOG-101 (внутр.)** | WebUI: stroke-SVG иконки (замена FA) | 🟢 |
| **BACKLOG-102 (внутр.)** | WebUI: light-тема (после dark-only) | 🟢 |

---

## 📋 v4.0.0 — AI/ML + DISTRIBUTED

| День | Задача | Приоритет |
|------|--------|-----------|
| 77-78 | ML-классификаторы | 🔴 |
| 79 | Аномалии в аудите | 🟡 |
| 80-81 | Zero-Trust архитектура | 🔴 |
| 82 | Распределённый Manager | 🔴 |
| 83 | SIEM: Kafka / Kinesis | 🟡 |
| 84 | Версионирование данных | 🟢 |
| 85 | Релиз v4.0.0 | 🔴 |

---

## 📊 Статистика

| Версия | Задач | Выполнено | Прогресс |
|--------|-------|-----------|----------|
| v1.0.0-v2.1.0 | 27 | 27 | 100% ✅ |
| **v3.0.0** | **~130** | **~123** | **~95% 🔄** |
| v3.1.0 | 40 | 0 | 0% 📋 |
| v4.0.0 | 9 | 0 | 0% 📋 |
| **ИТОГО** | **~206** | **~150** | **~73%** |

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
- **`docs/DESIGN.md`** — style reference WebUI (Dovetail).
- **ТЗ (архив):** `TZ_FIX_SPRINT.md` … `TZ_BLOCK6_*.md`, `day_53_*_*.md`.
- **`SECURITY.md`**, **`docs/security_checklist.md`**, **`docs/admin-guide/05-security.md`**.

---

**Актуально на:** 04.10.2026
**Версия:** v3.13.33
**Следующая цель:** 53.3-fs-regress → 53.4a–53.4e (WebUI-редизайн) → 55 (GitHub-пакет) → 57 (релиз v3.0.0)