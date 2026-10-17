> **Обновляется архитектором.** План — редко, бэклог — по мере.
> Текущее состояние — в `STATE.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 14.10.2026
**Стратегия:** Windows First → Linux → S3/MinIO → Enterprise Ready → UI-редизайн → Rust + DLP + SIEM + IoC → Enterprise Operations → OAuth + ML

---

## 🚀 Вехи

| Версия | Статус | Ключевые фичи |
|--------|--------|---------------|
| v1.0.0-v2.1.0 | ✅ | Обнаружение, классификация, WebUI, Linux-агент |
| **v3.0.0** | **🔄 Финальный этап** | **Enterprise Ready + WebUI-редизайн (Dovetail).** 53.4a-доп5 (v3.13.41), 53.4b (v3.14.0), **53.4c/d/e (v3.14.1) — закрыты (REDESIGN COMPLETE)**. Далее: Grafana-тестирование + RBAC — 53.4e-grafana. |
| **v3.1.0** | **📋 Расширение** | **13 направлений: IoC, специализация сканеров, диагностика ошибок, экспорт каталога, лёгкий агент, шина событий, Model Registry, централизованное обновление, бэкап, Key Store, кастомные регулярки, метрики в WebUI, OAuth.** + Rust, DLP, SIEM, Cython, Formal Grammars. |
| v3.2.0 | 📋 | ML-классификаторы, Kafka, Vault, HSM, PITR, macOS, CMDB/DLP consumer |
| v4.0.0 | 📋 | Zero-Trust, распределённый Manager, Kafka/Kinesis, CEF/LEEF |

---

## 📋 v3.0.0 — ENTERPRISE READY (🔄 ФИНАЛЬНЫЙ ЭТАП)

### План по дням

| День | Задача | BACKLOG/BUG | Статус |
|------|--------|-------------|--------|
| 28-50.2 | (WebUI, AD, Findings Refactor, Scanner deep, Мониторинг, Masking, Retention, Блок 9, Блок 6) | см. STATE | ✅ до v3.13.27 |
| 51 (Блок 9) | Фикс-спринт Блок 9 (Безопасность) — 10 BUG | TASK-074…084 | ✅ v3.13.28 |
| 52 (Блок 6) | Блок 6 (Агенты): Windows + Linux + S3 + MinIO | TASK-085…103 | ✅ v3.13.28 |
| 53.1a (BACKLOG-097 ч.1) | Manager: `source_type` + S3-ресурсы, миграция 006 | TASK-104…109 | ✅ v3.13.29 |
| 53.1b (BACKLOG-097 ч.2) | Scanner: фабрика + `_text_scanner.py` + boto3 | TASK-110…117 | ✅ v3.13.30 |
| 53.2 (BACKLOG-097 ч.3) | Scanner: S3LineConnector (streaming, ENV, OCR) | TASK-118…123 | ✅ v3.13.31 |
| 53.3 (BACKLOG-097 ч.4) | E2E на MinIO + WebUI-форма S3 + docs | TASK-129…133 | ✅ v3.13.32 |
| 53.3-test-stand-fix | Тестовый стенд: healthcheck, авто-очистка | — | ✅ v3.13.34 |
| 53.3-fix-s3-bucket | `S3LineConnector`: bucket только из `scan_config` | TASK-134…136 | ✅ v3.13.35 |
| 53.3-fs-regress-ocr-diag (BUG-137) | Гонка temp-файлов `OCREngine` | BUG-137 | ✅ v3.13.36 |
| 53.3-fs-regress | Ручной регресс FS | — | ✅ 07.10.2026 |
| B (ручной FS-регресс) | 12/12 пунктов | — | ✅ 09.10.2026 |
| 53.4a (BACKLOG-093, этап 1/5) | WebUI-редизайн: токены + base + компоненты + grid-wireframe; локальные шрифты; `theme.js` удалён | BACKLOG-093 | ✅ v3.13.37 |
| 53.4a-доп (BACKLOG-093) | WebUI-фиксы: BUG-138/139/140 | BACKLOG-093 | ✅ v3.13.38 |
| **53.4a-доп3 (hotfix)** | **Backend-critical hotfix: BUG-201/202/214/223/181/168/142/148** | BUG-201,202,214,223,181,168,142,148 | ✅ v3.13.39 |
| **53.4a-доп4 (fonts, BUG-212)** | **unicode-range кириллицы + замена jetbrains-mono.woff2 (v2.304 variable) + OFL.txt** | BUG-212 | ✅ v3.13.40 |
| **53.4a-доп5 (hotfix + sync)** | **BUG-150/149 + BACKLOG-121/119 + sync ARCHITECTURE.md** | BUG-150,149, BACKLOG-121,119 | ✅ v3.13.41 |
| **53.4b (BACKLOG-093, этап 2/5)** | **WebUI-редизайн: login, dashboard, resources, findings + RBAC frontend + Responsive** | BUG-141…233 | ✅ v3.14.0 |
| **Мастер-сессия v3.13.38** | **WebUI 1–17 + RBAC-прогон; ~100 BUG + ~40 BACKLOG** | — | ✅ 12.10.2026 |
| **53.4c (BACKLOG-093, этап 3/5)** | **WebUI-редизайн: finding_detail, catalog, audit, scanners, access, resources** | BUG-104…234 | ✅ v3.14.1 |
| **53.4d (BACKLOG-093, этап 4/5)** | **WebUI-редизайн: roles, users, settings, footer, Chart.js палитра** | BACKLOG-131…155 | ✅ v3.14.1 |
| **53.4e (BACKLOG-093, этап 5/5)** | **WebUI-редизайн: полировка, скриншоты, `docs/DESIGN.md`, favicon, CSP, E2E-очистка** | BACKLOG-093 | ✅ v3.14.1 |
| **53.4e-grafana** | **Grafana: тестирование (TEST-NOTE-8.1…8.6) + RBAC (BACKLOG-307)** | TEST-NOTE-8.1…8.6, BACKLOG-307 | 📋 |
| **53.4e-grafana-hotfix** | **Grafana: хотфикс (метрики findings/scanner, Alertmanager, targets, панели)** | BUG-245/236/241/243/246/247/239 | ✅ v3.14.2 |
| 52.1 | Linux-агент: метрики + сквозной поток + BUG-130 | — | 📋 |
| 52.2 | Блок 6.5: сбор прав Windows (BUG-123, 127) | — | 📋 |
| 54 | Блок 11 (Отказоустойчивость) | — | 📋 |
| 55 | GitHub-пакет — **только после 53.4e** | BACKLOG-028/046 | 📋 |
| 56 | BUG-117 (Manager-маскирование, hotfix) | — | 📋 |
| 57 | Релиз v3.0.0 | — | 📋 |

> ⚠️ **Условие приёмки GitHub-пакета (день 55):** 53.4a–53.4e закрыты.
> Все 14 страниц WebUI в dark-теме, `theme.js` удалён, скриншоты в `docs/ui-screenshots/`,
> `docs/DESIGN.md` в репо, Grafana протестирована + RBAC (BACKLOG-307).

### Бэклог v3.0.0 — активные задачи (топ-50)

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| **BUG-232** | Модалки на mobile | 🔴 | 📋 53.4c |
| **BUG-233** | Гамбургер не работает | 🔴 | 📋 53.4c |
| **BUG-213** | Frontend RBAC не работает | 🔴 | ✅ 53.4b |
| **BUG-117** | Manager не маскирует контексты сам | 🔴 | 📋 день 56 |
| **BUG-118** | Auth middleware 2 соединения | 🔴 | 📋 v3.1.0 |
| **BUG-172** | Нет permissions в RBAC | 🔴 | 📋 архитектура |
| **BUG-135** | S3-агент: BOM | 🟡 | 📋 v3.1.0 |
| **BUG-123** | Windows-агент: сбор прав = 0 | 🟡 | 📋 52.2 |
| **BACKLOG-093** | Редизайн WebUI (Dovetail) | 🔴 | ✅ v3.14.1 |
| **BACKLOG-307** | **Grafana RBAC + DCAP RBAC (Auth Proxy)** | 🔴 | 📋 53.4e |
| **TEST-NOTE-8.1…8.6** | **Grafana: тестирование** | 🔴 | 📋 53.4e |
| **Linux-агент дотест** | Метрики, сквозной поток, BUG-130 | 🔴 | 📋 52.1 |
| **BACKLOG-028** | Публикация на GitHub | 🔴 | 📋 55 |
| **BACKLOG-046** | Полный E2E-прогон на CI | 🔴 | 📋 55 |
| **BACKLOG-044** | Защита `/metrics` | 🟡 | 📋 production |
| **BACKLOG-094** | WebUI/Manager не пересобирается автоматически | 🟡 | 📋 |
| **BUG-155…234** | (все остальные) | 🟡/🟢 | ✅ 53.4c/d/e |
| **BACKLOG-131…155** | (все UI-улучшения) | 🟡/🟢 | ✅ 53.4c/d/e |

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
| TASK-074…084 | **Блок 9 (Безопасность)** | v3.13.28 |
| TASK-085…103 | **Блок 6 (Агенты)** | v3.13.28 |
| TASK-104…136 | **S3-коннектор (BACKLOG-097)** | v3.13.29–35 |
| BUG-137 | **Гонка temp-файлов `OCREngine`** | v3.13.36 |
| 53.4a | **WebUI-редизайн, этап 1** | v3.13.37 |
| 53.4a-доп | **BUG-138/139/140** | v3.13.38 |
| **BUG-201/202/214/223/181/168/142/148** | **Backend-critical hotfix** | **v3.13.39** |
| **BUG-212** | **Шрифты кириллицы** | **v3.13.40** |
| **BUG-150/149, BACKLOG-121/119** | **Hotfix + sync ARCHITECTURE.md** | **v3.13.41** |
| **BUG-141/203/204/205/206/207/216/228/229/232/233** | **WebUI RBAC + Responsive** | **v3.14.0** |

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

### TEST-NOTE — Блок 8 (Мониторинг, Grafana)

| ID | Название | Приоритет |
|----|----------|-----------|
| TEST-NOTE-8.1 | Grafana: smoke (запуск, health, datasource) | 🔴 53.4e |
| TEST-NOTE-8.2 | Grafana: дашборды (все) | 🔴 53.4e |
| TEST-NOTE-8.3 | Grafana: метрики (Manager / scanner / agents) | 🔴 53.4e |
| TEST-NOTE-8.4 | Grafana: алерты (fire + resolve) | 🔴 53.4e |
| TEST-NOTE-8.5 | Grafana: RBAC (viewer / editor / admin) | 🔴 53.4e |
| TEST-NOTE-8.6 | Grafana: производительность | 🟡 53.4e |

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
| **TEST-NOTE-NEW-1** | `/api/resources` — default limit=100 | ✅ 53.4c (пагинация) |
| **TEST-NOTE-NEW-2** | `/api/access/resources` — без limit | ✅ 53.4c (пагинация) |
| **TEST-NOTE-NEW-3** | Маска `aws_secret` = `=wJalr***` — сохраняет `=` (design по BUG-086) | 📋 design |
| **TEST-NOTE-NEW-4** | 8 проблем в Console — `[DOM]` password field | ✅ 53.4e (BUG-193) |

---

## 📋 v3.1.0 — EXTENDED ENTERPRISE (📋 РАСШИРЕНИЕ)

> **Стратегия:** расширение функциональности от «поиска данных» к «платформе безопасности».
> **13 направлений** (10 новых + 3 существующих).

### 🎯 Направления v3.1.0

| # | Направление | Задачи | Ядро | Приоритет |
|---|-------------|--------|------|-----------|
| 1 | **IoC-поиск** | BACKLOG-156…160 | 156, 157 | 🟡 |
| 2 | **Специализация сканеров** | BACKLOG-161…166 | 161, 164 | 🟡 |
| 3 | **Диагностика ошибок сканирования** | BACKLOG-167…177 | 167…170, 173 | 🟡 |
| 4 | **Экспорт каталога в CMDB** | BACKLOG-178…186 | 178, 179, 181, 182 | 🟡 |
| 5 | **Лёгкий агент сканирования** | BACKLOG-187…202 | 187…191, 195, 196, 199, 200, 201 | 🟡 |
| 6 | **Шина событий** | BACKLOG-203…214 | 203…206, 208, 210, 214 | 🟡 |
| 7 | **Model Registry** | BACKLOG-215…226 | 215…221, 226 | 🟡 |
| 8 | **Централизованное обновление** | BACKLOG-227…240 | 227…232, 234, 239 | 🟡 |
| 9 | **Бэкап и восстановление** | BACKLOG-241…259 | 241…244, 246…248, 250…252, 254, 255 | 🟡 |
| 10 | **Key Store** | BACKLOG-260…277 | 260…264, 267, 268, 270, 271, 272 | 🟡 |
| 11 | **Кастомные регулярки** | BACKLOG-278…291 | 278…284, 287, 288 | 🟡 |
| 12 | **Метрики в WebUI** | BACKLOG-292…309 | 292…302, 305 | 🟡 |
| 13 | **OAuth для всех сервисов** | BACKLOG-310…314 | 310, 311, 314 | 🟡 |
| 14 | Rust Scanner (CIFS/NFS + параллелизм) | BACKLOG-036 | 036 | 🔴 |
| 15 | DLP (ICAP + политики) | BACKLOG-032/033 | 032, 033 | 🟡 |
| 16 | SIEM (через шину событий) | BACKLOG-069/070/072 | 069, 070 | 🔴 |
| 17 | Cython-оптимизация | BACKLOG-089/090 | 089, 090 | 🟡 |
| 18 | Formal Grammars (CFG + AST) | — | — | 🔴 |
| 19 | TruffleHog | BACKLOG-091 | 091 | 🟡 |
| 20 | Прочие BUG-фиксы | BUG-117/118/123/125/126/129/130/135 | — | 🟡 |

### 📅 План по дням v3.1.0

| День | Задача | Направление | Приоритет |
|------|--------|-------------|-----------|
| 58–59 | Rust Scanner (CIFS/NFS + параллелизм) | 14 | 🔴 |
| 60 | Cython-оптимизация горячих точек | 17 | 🟡 |
| 61 | Быстрые regex: `cre` / `re2` | 17 | 🟡 |
| 62 | ICAP Connector (DLP) | 15 | 🟡 |
| 63 | DLP Политики (WebUI) | 15 | 🟡 |
| 64 | SMB-сканер (Rust) | 14 | 🟡 |
| 65 | Шина событий: Redis Streams | 6 | 🔴 |
| 66 | SIEM: consumer из шины | 16 | 🔴 |
| 67 | SIEM: WebUI настройки | 16 | 🟡 |
| 68 | Key Store: модель + API | 10 | 🔴 |
| 69 | Key Store: ротация (авто + multi-key) | 10 | 🔴 |
| 70 | Key Store: интеграция (findings/JWT/S3) | 10 | 🔴 |
| 71 | Бэкап: BackupManager + API | 9 | 🔴 |
| 72 | Бэкап: Restore + WebUI | 9 | 🔴 |
| 73 | Model Registry: модель + API | 7 | 🔴 |
| 74 | Model Registry: сканер bootstrap | 7 | 🔴 |
| 75 | Централизованное обновление: manifest + API | 8 | 🟡 |
| 76 | Централизованное обновление: сканер self-update | 8 | 🟡 |
| 77 | Диагностика ошибок: модель + API | 3 | 🟡 |
| 78 | Диагностика ошибок: WebUI `/scanner-errors` | 3 | 🟡 |
| 79 | IoC-поиск: хэши | 1 | 🟡 |
| 80 | IoC-поиск: YARA | 1 | 🟡 |
| 81 | IoC-поиск: WebUI | 1 | 🟡 |
| 82 | Лёгкий агент: базовый (server + workstation) | 5 | 🟡 |
| 83 | Лёгкий агент: службы (MSI/DEB) | 5 | 🟡 |
| 84 | Лёгкий агент: WebUI `/agents` | 5 | 🟡 |
| 85 | Специализация: capabilities + segment | 2 | 🟡 |
| 86 | Экспорт каталога: API + WebUI | 4 | 🟡 |
| 87 | Кастомные регулярки: модель + API + WebUI | 11 | 🟡 |
| 88 | Formal Grammars (CFG + AST) | 18 | 🔴 |
| 89 | Post-Processor (NER + relations) | 18 | 🟡 |
| 90 | Метрики в WebUI: прокси + графики | 12 | 🟡 |
| 91 | OAuth: провайдер + интеграция | 13 | 🟡 |
| 92 | BUG-117/118/123/125/126/129/130/135 | 20 | 🟡 |
| 93 | TruffleHog | 19 | 🟡 |
| 94 | Red teaming, SAST, SCA | — | 🔴 |
| 95 | Релиз v3.1.0 | — | 🔴 |

### 📋 Бэклог v3.1.0 — детально

#### 1. IoC-поиск (BACKLOG-156…160)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-156 | IoC-поиск: хэши SHA256/MD5 | 🟡 |
| BACKLOG-157 | IoC-поиск: YARA-интеграция | 🟡 |
| BACKLOG-158 | IoC-поиск: WebUI CRUD правил | 🟡 |
| BACKLOG-159 | IoC-поиск: внешние фиды (MISP/OpenIOC) | 🟢 |
| BACKLOG-160 | IoC-поиск: Windows-агент (реестр, tasks) | 🟡 |

#### 2. Специализация сканеров (BACKLOG-161…166)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-161 | Capabilities + фильтрация задач | 🟡 |
| BACKLOG-162 | ScanTask: priority | 🟢 |
| BACKLOG-163 | ScanTask: assigned_to | 🟢 |
| BACKLOG-164 | Resource + Scanner: segment / network_zone | 🟡 |
| BACKLOG-165 | WebUI `/scanners`: capabilities + segment | 🟡 |
| BACKLOG-166 | WebUI `/resources`: segment | 🟢 |

#### 3. Диагностика ошибок (BACKLOG-167…177)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-167 | `FailedFile`: retryable, retry_count, occurred_at | 🟡 |
| BACKLOG-168 | `ScanTask`: error_type, error_message, failed_at | 🟡 |
| BACKLOG-169 | Классификация errno/ClientError → error_type | 🟡 |
| BACKLOG-170 | `GET /api/scanner/tasks/{id}/errors` | 🟡 |
| BACKLOG-171 | `POST /api/scanner/tasks/{id}/retry` | 🟡 |
| BACKLOG-172 | Авто-retry | 🟢 |
| BACKLOG-173 | WebUI `/scanner-errors` | 🟡 |
| BACKLOG-174 | WebUI `/resources`: статус ошибки | 🟡 |
| BACKLOG-175 | WebUI Dashboard: KPI «Ошибки» | 🟢 |
| BACKLOG-176 | Уведомления email/webhook | 🟢 |
| BACKLOG-177 | SIEM: `scan_failed` | 🟢 |

#### 4. Экспорт каталога (BACKLOG-178…186)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-178 | `GET /api/catalog/export` (JSON) | 🟡 |
| BACKLOG-179 | `GET /api/catalog/export` (CSV) | 🟡 |
| BACKLOG-180 | `GET /api/catalog/export` (JSON-LD) | 🟢 |
| BACKLOG-181 | Фильтры экспорта | 🟡 |
| BACKLOG-182 | WebUI `/catalog`: кнопка «Экспорт» | 🟡 |
| BACKLOG-183 | Webhook push в CMDB | 🟢 |
| BACKLOG-184 | WebUI `/settings`: настройки экспорта | 🟢 |
| BACKLOG-185 | Адаптеры: ServiceNow, Jira SM, 1С | 🟢 |
| BACKLOG-186 | `POST /api/catalog/export/schedule` (cron) | 🟢 |

#### 5. Лёгкий агент (BACKLOG-187…202)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-187 | Лёгкий агент: базовый | 🟡 |
| BACKLOG-188 | Служба Windows (MSI) | 🟡 |
| BACKLOG-189 | Демон Linux (DEB/RPM) | 🟡 |
| BACKLOG-190 | Offline-буфер (SQLite) | 🟡 |
| BACKLOG-191 | Managed-режим | 🟡 |
| BACKLOG-192 | Standalone (cron) | 🟢 |
| BACKLOG-193 | One-shot | 🟢 |
| BACKLOG-194 | Auto-update | 🟢 |
| BACKLOG-195 | WebUI `/agents` | 🟡 |
| BACKLOG-196 | Skip-папки / skip-расширения | 🟡 |
| BACKLOG-197 | Throttling (CPU/IO) | 🟢 |
| BACKLOG-198 | macOS (PKG) | 🟢 |
| BACKLOG-199 | Профиль «server» | 🟡 |
| BACKLOG-200 | Профиль «workstation» | 🟡 |
| BACKLOG-201 | Интеграция с capabilities + segment | 🟡 |
| BACKLOG-202 | WebUI: различие workstation / server | 🟢 |

#### 6. Шина событий (BACKLOG-203…214)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-203 | Шина: Redis Streams | 🟡 |
| BACKLOG-204 | EventPublisher в Manager | 🟡 |
| BACKLOG-205 | UnifiedEvent: расширить | 🟡 |
| BACKLOG-206 | SIEM: consumer из шины | 🟡 |
| BACKLOG-207 | SOAR: consumer | 🟢 |
| BACKLOG-208 | Dead-letter queue | 🟡 |
| BACKLOG-209 | WebUI `/settings`: настройки шины | 🟡 |
| BACKLOG-210 | Фильтрация событий | 🟡 |
| BACKLOG-211 | Kafka (v3.2.0+) | 🟢 |
| BACKLOG-212 | CMDB: consumer | 🟢 |
| BACKLOG-213 | DLP: consumer | 🟢 |
| BACKLOG-214 | Метрики шины | 🟡 |

#### 7. Model Registry (BACKLOG-215…226)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-215 | Model Registry: модуль + API | 🟡 |
| BACKLOG-216 | LocalStorage + S3Storage | 🟡 |
| BACKLOG-217 | Манифест + SHA256 | 🟡 |
| BACKLOG-218 | Сканер: `bootstrap` | 🟡 |
| BACKLOG-219 | Сканер: проверка при старте | 🟡 |
| BACKLOG-220 | Offline-пакет | 🟡 |
| BACKLOG-221 | WebUI `/settings/models` | 🟡 |
| BACKLOG-222 | Внутренний PyPI | 🟢 |
| BACKLOG-223 | Внутренний Docker Registry | 🟢 |
| BACKLOG-224 | Обновление моделей | 🟢 |
| BACKLOG-225 | Подписи моделей | 🟢 |
| BACKLOG-226 | Метрики Model Registry | 🟡 |

#### 8. Централизованное обновление (BACKLOG-227…240)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-227 | Версия в heartbeat | 🟡 |
| BACKLOG-228 | `GET /api/updates/manifest` | 🟡 |
| BACKLOG-229 | `GET /api/updates/components` | 🟡 |
| BACKLOG-230 | `POST /api/scanner/update` | 🟡 |
| BACKLOG-231 | Сканер: self-update | 🟡 |
| BACKLOG-232 | WebUI `/updates` | 🟡 |
| BACKLOG-233 | Откат (rollback) | 🟢 |
| BACKLOG-234 | Обновление моделей | 🟡 |
| BACKLOG-235 | Обновление агентов | 🟡 |
| BACKLOG-236 | Матрица совместимости | 🟡 |
| BACKLOG-237 | Каналы (stable/beta/nightly) | 🟢 |
| BACKLOG-238 | Подписи обновлений | 🟢 |
| BACKLOG-239 | Offline-пакет обновления | 🟡 |
| BACKLOG-240 | Метрики обновлений | 🟡 |

#### 9. Бэкап и восстановление (BACKLOG-241…259)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-241 | BackupManager: создание | 🟡 |
| BACKLOG-242 | manifest.json + SHA256 | 🟡 |
| BACKLOG-243 | Шифрование (AES-256-GCM) | 🟡 |
| BACKLOG-244 | LocalStorage | 🟡 |
| BACKLOG-245 | S3Storage (off-site) | 🟡 |
| BACKLOG-246 | Расписание (Celery Beat) | 🟡 |
| BACKLOG-247 | Retention бэкапов | 🟡 |
| BACKLOG-248 | RestoreManager | 🟡 |
| BACKLOG-249 | Dry-run | 🟡 |
| BACKLOG-250 | API `/api/backup/*` | 🟡 |
| BACKLOG-251 | WebUI `/backup` | 🟡 |
| BACKLOG-252 | Аудит бэкапов | 🟡 |
| BACKLOG-253 | События в шину | 🟡 |
| BACKLOG-254 | Бэкап перед обновлением | 🟡 |
| BACKLOG-255 | Verify целостности | 🟡 |
| BACKLOG-256 | Инкрементальный бэкап | 🟢 |
| BACKLOG-257 | PITR (WAL) | 🟢 |
| BACKLOG-258 | Метрики бэкапов | 🟡 |
| BACKLOG-259 | Vault integration | 🟢 |

#### 10. Key Store (BACKLOG-260…277)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-260 | Key Store: модель | 🟡 |
| BACKLOG-261 | Master key (ENV bootstrap) | 🟡 |
| BACKLOG-262 | API `/api/keys/*` | 🟡 |
| BACKLOG-263 | KeyClient (cache) | 🟡 |
| BACKLOG-264 | Findings: Key Store | 🟡 |
| BACKLOG-265 | JWT: Key Store | 🟡 |
| BACKLOG-266 | S3: Key Store | 🟡 |
| BACKLOG-267 | Ротация: авто | 🟡 |
| BACKLOG-268 | Ротация: multi-key | 🟡 |
| BACKLOG-269 | Re-encryption findings | 🟢 |
| BACKLOG-270 | Аудит ключей | 🟡 |
| BACKLOG-271 | WebUI `/settings/keys` | 🟡 |
| BACKLOG-272 | Backup: Key Store | 🟡 |
| BACKLOG-273 | Master key: backup + Shamir | 🟢 |
| BACKLOG-274 | Vault: адаптер | 🟢 |
| BACKLOG-275 | HSM / TPM | 🟢 |
| BACKLOG-276 | События ключей в шину | 🟡 |
| BACKLOG-277 | Метрики Key Store | 🟡 |

#### 11. Кастомные регулярки (BACKLOG-278…291)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-278 | `CustomRegex`: модель | 🟡 |
| BACKLOG-279 | API `/api/regexes/*` | 🟡 |
| BACKLOG-280 | Валидация (ReDoS) | 🟡 |
| BACKLOG-281 | `CustomRegexClassifier` | 🟡 |
| BACKLOG-282 | Передача в `scan_config` | 🟡 |
| BACKLOG-283 | WebUI `/settings/regexes` | 🟡 |
| BACKLOG-284 | WebUI: тест | 🟡 |
| BACKLOG-285 | Импорт/экспорт | 🟢 |
| BACKLOG-286 | Версионирование | 🟢 |
| BACKLOG-287 | Аудит | 🟡 |
| BACKLOG-288 | Лёгкий агент: регулярки | 🟡 |
| BACKLOG-289 | События в шину | 🟢 |
| BACKLOG-290 | Метрики | 🟢 |
| BACKLOG-291 | `MASK_RULES` в БД | 🟢 |

#### 12. Метрики в WebUI (BACKLOG-292…309)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-292 | Прокси к Prometheus | 🟡 |
| BACKLOG-293 | Прокси к Alertmanager | 🟡 |
| BACKLOG-294 | API query/query_range | 🟡 |
| BACKLOG-295 | API health | 🟡 |
| BACKLOG-296 | API alerts | 🟡 |
| BACKLOG-297 | Кэш (Redis) | 🟡 |
| BACKLOG-298 | PromQL → Chart.js | 🟡 |
| BACKLOG-299 | WebUI `/monitoring` | 🟡 |
| BACKLOG-300 | WebUI `/alerts` | 🟡 |
| BACKLOG-301 | Dashboard: здоровье | 🟡 |
| BACKLOG-302 | `/scanners`: метрики | 🟡 |
| BACKLOG-303 | `/resources`: метрики | 🟢 |
| BACKLOG-304 | Silence | 🟢 |
| BACKLOG-305 | RBAC метрик | 🟡 |
| BACKLOG-306 | События в шину | 🟢 |
| BACKLOG-307 | Grafana RBAC + DCAP RBAC (Auth Proxy) | 🔴 v3.0.0 (53.4e) |
| BACKLOG-308 | Метрики мониторинга | 🟢 |
| BACKLOG-309 | Fallback без Prometheus | 🟢 |

#### 13. OAuth для всех сервисов (BACKLOG-310…314)

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-310 | OAuth-провайдер в Manager | 🟡 |
| BACKLOG-311 | Grafana: OAuth (вместо Auth Proxy) | 🟡 |
| BACKLOG-312 | Prometheus / Alertmanager: OAuth | 🟢 |
| BACKLOG-313 | Keycloak / Authentik: интеграция | 🟢 |
| BACKLOG-314 | SSO: единая сессия | 🟡 |

#### 14–20. Существующие направления v3.1.0

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-036 | Rust Scanner (CIFS/NFS + параллелизм) | 🔴 |
| BACKLOG-032 | ICAP Connector (DLP) | 🟡 |
| BACKLOG-033 | DLP Политики (WebUI) | 🟡 |
| BACKLOG-035 | SMB-сканер (Rust) | 🟡 |
| BACKLOG-069 | SIEM: генерация событий | 🔴 |
| BACKLOG-070 | SIEM: экспорт | 🔴 |
| BACKLOG-072 | SIEM: WebUI | 🟡 |
| BACKLOG-089 | Cython-оптимизация | 🟡 |
| BACKLOG-090 | Быстрые regex | 🟡 |
| BACKLOG-091 | TruffleHog | 🟡 |
| Formal Grammars | CFG + AST | 🔴 |
| Post-Processor | NER + relations | 🟡 |
| BUG-117 | Manager-маскирование | 🔴 |
| BUG-118 | Auth middleware 1 соединение | 🔴 |
| BUG-123 | Windows-агент: сбор прав | 🟡 |
| BUG-125 | Linux-агент: MANAGER_URL env | 🟡 |
| BUG-126 | S3-агент: verify_ssl | 🟢 |
| BUG-129 | Windows-агент: шум | 🟡 |
| BUG-130 | Linux-агент: retry без backoff | 🟡 |
| BUG-135 | S3-агент: BOM | 🟡 |

---

## 📋 v3.2.0 — ML + DISTRIBUTED + ADVANCED OPS (📋)

| # | Направление | Задачи |
|---|-------------|--------|
| 1 | ML-классификаторы (embeddings) | — |
| 2 | Near-duplicate detection (MinHash) | — |
| 3 | Аномалии в аудите | — |
| 4 | Kafka (шина) | BACKLOG-211 |
| 5 | Vault / HSM | BACKLOG-273/274/275 |
| 6 | PITR | BACKLOG-257 |
| 7 | macOS-агент | BACKLOG-198 |
| 8 | Лёгкий агент: расширенный | BACKLOG-192/193/194 |
| 9 | IoC: внешние фиды | BACKLOG-159 |
| 10 | CMDB/DLP consumer | BACKLOG-212/213 |
| 11 | Каналы обновлений | BACKLOG-237 |
| 12 | Подписи обновлений | BACKLOG-238 |
| 13 | Zero-Trust | — |
| 14 | Распределённый Manager | — |
| 15 | Версионирование данных | — |

---

## 📋 v4.0.0 — ZERO-TRUST + DISTRIBUTED (📋)

| # | Направление |
|---|-------------|
| 1 | Zero-Trust архитектура |
| 2 | Распределённый Manager |
| 3 | Kafka / Kinesis (streaming) |
| 4 | CEF / LEEF |
| 5 | Multi-tenancy |
| 6 | Global policy engine |
| 7 | Federated learning (ML) |
| 8 | Blockchain audit trail |

---

## 📊 Статистика

| Версия | Задач | Выполнено | Прогресс |
|--------|-------|-----------|----------|
| v1.0.0-v2.1.0 | 27 | 27 | 100% ✅ |
| **v3.0.0** | **~235** | **~185** | **~79% 🔄** |
| **v3.1.0** | **~210** | **0** | **0% 📋** |
| v3.2.0 | ~30 | 0 | 0% 📋 |
| v4.0.0 | ~10 | 0 | 0% 📋 |
| **ИТОГО** | **~512** | **~212** | **~41%** |

> ⚠️ v3.1.0 вырос до ~210 задач после **13 направлений** (BACKLOG-156…314).

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
- **`docs/DESIGN.md`** — style reference WebUI (Dovetail). ✅ Перенесён в `docs/` (53.4e, v3.14.1).
- **ТЗ (активные):** — (53.4c/d/e архивируется).
- **ТЗ (архив):** `prompts/archive/*`.
- **`SECURITY.md`**, **`docs/security_checklist.md`**, **`docs/admin-guide/05-security.md`**.

---

**Актуально на:** 17.10.2026
**Версия:** v3.14.2
**Следующая цель:** 55 (GitHub-пакет) → 56 → 57 (релиз v3.0.0) → v3.1.0 (13 направлений).