# 🧪 DCAP Test Session — Состояние на 17.10.2026

> **Мастер-сессия ручного тестирования DCAP v3.14.3**
> Блок 1 (Smoke) — ✅
> Блок 2 (Auth/RBAC) — ✅
> Блок 3 (Scanner deep) — ✅
> Блок 4 (Findings API) — ✅
> Блок 5 (WebUI) — ✅ (блоки 1–13), ⏳ блоки 14–17 (верификация)
> Блок 6 (Агенты) — ⚠️ 5/6 под-блоков
> Блок 7 (Retention) — ✅
> Блок 8 (Мониторинг) — ✅ (Prometheus + Grafana, v3.14.2)
> Блок 9 (Безопасность) — ✅
> 53.1a–53.3-fix (BACKLOG-097) — ✅
> 53.4a (WebUI-редизайн, этап 1) — ✅
> 53.4a-доп (BUG-138/139/140) — ✅
> 53.4a-доп3/4/5 — ✅ v3.13.39–41
> 53.4b (WebUI-редизайн, этап 2) — ✅ v3.14.0
> 53.4c/d/e (WebUI-редизайн, этапы 3–5) — ✅ v3.14.1 (REDESIGN COMPLETE)
> **53.4e-grafana + hotfix — ✅ v3.14.2**
> **53.4e-rbac-hotfix (блоки 12–13: Users, Roles) — ✅ v3.14.3**
> **WebUI-прогон: блоки 1–11 — ✅ (закрыты 10–12.10.2026)**
> **WebUI-прогон: блоки 12–13 — ✅ (v3.14.3); блоки 14–17 — ⏳ верификация (следующий шаг)**

---

## 🎯 Текущее состояние

| Параметр | Значение |
|----------|----------|
| **Версия** | v3.14.3 |
| **Целевая версия** | v3.0.0 (релиз) |
| **Пройдено** | Блоки 1–9; 53.1a–53.3; 53.4a; 53.4a-доп; 53.4a-доп3/4/5; 53.4b; 53.4c/d/e; 53.4e-grafana + hotfix; 53.4e-rbac-hotfix; **WebUI 1–13** |
| **Следующий блок** | **Верификация WebUI 14–17** (Settings, Console, Network, Responsive) |
| **Auth mode** | hybrid (SPNEGO → JWT fallback) |
| **Контейнеров** | 15 |
| **Сканер** | На хосте, `3.14.3`, `S3_*` ENV — ✅ (BUG-148 закрыт в v3.13.39) |
| **Unit** | **472 passed** |
| **E2E** | **+4 v3.14.3 (таргетно PASSED)**; полный прогон — TEST-NOTE-10.8/10.10 |
| **Docker Compose** | v5.5.1 |

---

## 📊 РЕЗУЛЬТАТЫ ТЕСТА WEBUI (блоки 1–11)

*(без изменений — см. предыдущий STATE_TEST_SESSION.md)*

---

## ✅ ЗАКРЫТО В ЭТОЙ СЕССИИ (10–17.10.2026)

### 53.4a-доп (v3.13.38)
*(без изменений)*

### 53.4a-доп3 (v3.13.39)
*(без изменений)*

### 53.4a-доп4 (v3.13.40)
*(без изменений)*

### 53.4a-доп5 (v3.13.41)
*(без изменений)*

### 53.4b (v3.14.0)
*(без изменений)*

### 53.4c (v3.14.1) — страницы 2
*(без изменений)*

### 53.4d (v3.14.1) — роли/пользователи/настройки
*(без изменений)*

### 53.4e-rbac-hotfix (v3.14.3) — блоки 12–13 (Users, Roles)
- ✅ **BUG-253** — нельзя снять роль `admin` с себя (чекбокс disabled + `PUT /users/{self}` без `admin` → 400).
- ✅ **BUG-254** — пользователь без ролей → 400 (backend + frontend-валидация).
- ✅ **BUG-255** — кнопка «Войти» в стиле Dovetail (8px, weight 500; computed style проверен).
- ✅ **BUG-256** — 403 в WebUI → toast «Недостаточно прав» + редирект на главную.
- ✅ **BUG-257** — системные роли иммутабельны по `name`/`ad_group` (400 + поля disabled).
- ✅ **BUG-258** — создание кастомных ролей отключено (`POST /roles` → 403, кнопка disabled); возврат с `permissions` — v3.1.0.
- ✅ **BACKLOG-316** — роль `scanner` скрыта в `/users` (в `/roles` остаётся).
- ✅ **BUG-252 (follow-up)** — `base.css`: `input:not([type=checkbox]):not([type=radio])`; checkbox bg `rgb(103,152,255)` + галочка (headless), text/select — `--color-deep-coal`.

### 53.4e (v3.14.1) — полировка
*(без изменений)*

### 53.4e-grafana + hotfix (v3.14.2)
| ID | Название |
|----|----------|
| **BUG-245** | `scanner_id=""` в heartbeat_age — hardening + warning-лог + `+Inf` при `None` |
| **BUG-246** | `dcap_findings_total` → Gauge из БД; `dcap_findings_created_total` — Counter |
| **BUG-247** | `dcap_findings_created` — FP (авто-метрика) |
| **BUG-236** | `/api/alerts/webhook` → 401 (webhook убран) |
| **BUG-241** | `HTTP error rate (5xx)` → `or vector(0)` |
| **BUG-243** | S3-агент `DOWN` (target убран) |
| **BUG-239** | 2 пустые панели `dcap-scanner` (удалены) |

### Проверено на v3.14.2 (17.10.2026)
- Grafana: `dcap-overview` — 10 панелей, `dcap-scanner` — 6 панелей, все с данными (кроме 🟢 low).
- `/metrics` Manager: `scanner_id="1"`, `findings_total` из БД (`pii=1458`, `credentials=51`).
- Prometheus targets: 5/5 up (без s3-agent).
- Alertmanager: `ScannerInactive` fire → resolve, `scanner_id="1"` в labels.
- RBAC: Users = 1 (`admin`), Auth Proxy = отсутствует → BACKLOG-307 подтверждён.

---

## 🔴 ОТКРЫТЫЕ ПРОБЛЕМЫ

### 🔴 Критичные (блокеры v3.0.0)

| ID | Название | Фаза |
|----|----------|------|
| **BUG-117** | Manager не маскирует контексты сам | v3.0.0 hotfix (день 56) |
| **BUG-172** | Нет `permissions` в модели RBAC | архитектура v3.1.0 |
| **BUG-118** | Auth middleware держит 2 соединения | v3.1.0 |
| **BUG-135** | S3-агент: BOM | v3.1.0 |
| **BACKLOG-044** | `/metrics` публичный | production |
| **BACKLOG-307** | Grafana RBAC + DCAP RBAC (Auth Proxy) | v3.1.0 |

### 🟡 Важные (не блокеры v3.0.0)

| ID | Проблема | ТЗ |
|----|----------|-----|
| BUG-123 | Windows-агент: сбор прав | 52.2 |
| BUG-125 | Linux-агент: MANAGER_URL env | v3.1.0 |
| BUG-130 | Linux-агент: retry без backoff | v3.1.0 |
| BUG-221 | Reveal — странные email | v3.1.0 |
| BUG-235 | SIEM-страницы 404 | v3.1.0 |
| BACKLOG-101 | stroke-SVG иконки | v3.1.0 |
| BACKLOG-102 | light-тема | v3.1.0 |
| BACKLOG-103 | S3 fallback на config-секреты | v3.1.0 |
| BACKLOG-315 | Alertmanager webhook → Manager | v3.1.0 |

### 🟢 Мелкие

| ID | Проблема | ТЗ |
|----|----------|-----|
| BUG-248 | `Celery tasks (total)` → `No data` | v3.1.0 |
| BUG-249 | `PostgreSQL connections` — легенда | v3.1.0 |
| TEST-NOTE-3.1 | `text_extensions` в JSON игнорируется | docs |
| TEST-NOTE-5.2 | ARCHITECTURE.md: имена полей API | docs |
| TEST-NOTE-5.5 | Осиротевшие сканеры после обновления | v3.0.0 |
| TEST-NOTE-5.11 | E2E `_assign_task` конкурирует | v3.0.0 |
| TEST-NOTE-5.12 | `--remove-orphans` сносит стек | v3.0.0 |
| TEST-NOTE-10.1 | Alembic из PowerShell уходит в SQLite | docs |
| TEST-NOTE-10.3 | Дубли секций в `scan_config` | бэклог |
| TEST-NOTE-10.8 | 2 legacy-теста WebUI требуют непустую findings | v3.0.0 |
| TEST-NOTE-10.10 | 4 E2E-теста флакают без живого сканера | v3.0.0 |
| TEST-NOTE-10.11 | `/api/health` в dev-режиме `version: unknown` | docs |
| TEST-NOTE-10.12 | Два Manager на одном порту `:8000` | docs |
| TEST-NOTE-10.13 | `GET /api/scanner` возвращает `{value, Count}` | унификация API |
| TEST-NOTE-10.15 | ~40% находок — ложные | качество детекции |
| TEST-NOTE-NEW-3 | Маска `aws_secret` = `=wJalr***` | design |

---

## ✅ ЧТО ПОДТВЕРЖДЕНО РАБОТАЮЩИМ

*(блоки 1–11 — без изменений)*

### Блок 8 (Мониторинг) — ✅ v3.14.2

- ✅ Prometheus targets (5/5 up: manager, scanner, celery, postgres, redis; s3-agent закомментирован).
- ✅ Метрики Manager (`:8000/metrics`): `dcap_scanner_heartbeat_age_seconds{scanner_id="1"}`, `dcap_findings_total{type="pii"}=1458`, `{type="credentials"}=51`.
- ✅ Метрики сканера (`:9101`).
- ✅ Алерты: `ScannerInactive` → Firing → Normal, Alertmanager active → resolved.
- ✅ Grafana: `dcap-overview` (10 панелей), `dcap-scanner` (6 панелей), все с данными.
- ✅ RBAC: отсутствует (BACKLOG-307 подтверждён).
- ✅ Производительность: `Last 7 days` — быстро (< 2 с).

---

## 🔍 КЛЮЧЕВЫЕ ДИАГНОСТИКИ

### BUG-245 (`scanner_id=""`) — ✅ закрыт v3.14.2
**Причина:** `_refresh_scanner_gauges()` — `.clear()` + `.set()` в цикле; transient-состояние между ними → `{scanner_id=""}` при scrape. Hardening + warning-лог.
**Фикс:** `manager/src/metrics.py` — пер-строчная изоляция, warning-лог, `+Inf` при `None`. Юнит-тесты (6 passed).

### BUG-246 (`findings_total` за сессию) — ✅ закрыт v3.14.2
**Причина:** `Counter` инкрементировался при создании → `credentials` не появлялись (0 создано за сессию).
**Фикс:** `Gauge` из БД (`_refresh_findings_gauges()`), новый `dcap_findings_created_total` (Counter).

### BUG-236 (`/api/alerts/webhook` → 401) — ✅ закрыт v3.14.2
**Причина:** эндпоинта нет в коде, `AuthMiddleware` → 401.
**Фикс:** webhook убран из `alertmanager.yml` (вариант A). Вариант B — BACKLOG-315 (v3.1.0).

### BUG-239 (пустые панели `dcap-scanner`) — ✅ закрыт v3.14.2
**Причина:** `dcap_scanner_file_duration_seconds` (Histogram) определена, но **никогда не observes**; `ocr_latency` — не определена.
**Фикс:** 2 пустые панели удалены из `dcap-scanner.json` (вариант A).

---

## 🎯 КЛЮЧЕВЫЕ АРХИТЕКТУРНЫЕ РЕШЕНИЯ

### Grafana (17.10.2026)
- **RBAC:** BACKLOG-307 подтверждён (Users=1, Auth Proxy отсутствует), реализация — **v3.1.0**.
- **Маппинг:** admin→Admin, auditor→Editor, scanner/viewer→Viewer.
- **BUG-236:** вариант A (webhook убран). Вариант B — BACKLOG-315.
- **BUG-239:** вариант A (панели удалены). Вариант B — v3.1.0.
- **`dcap_findings_total`:** Gauge из БД (не Counter за сессию).

### Остальные (без изменений)
- `.btn-primary` → white filled (BACKLOG-121, v3.13.41).
- `hybrid` auth → убрать badge (BACKLOG-119, v3.13.41).
- `start_scanner.bat` — S3-ENV (BUG-148, v3.13.39).
- `delete_resource` — ON DELETE CASCADE (BUG-150, v3.13.41).

---

## 📋 СЛЕДУЮЩИЕ ШАГИ

### Следующий шаг — верификация WebUI 12–17

**Порядок:**
**Порядок:**
1. ~~**Блок 12 (Users)** — `/users` (admin): CRUD, роли, пароль, GMT, локализация.*~~ — ✅ v3.14.3
2. **Блок 13 (Roles)** — `/roles` (admin): список, системные роли — ✅ v3.14.3 (создание отключено, BUG-258).
3. **Блок 14 (Settings)** — `/settings` (admin): retention policies, смена пароля.
4. **Блок 15 (Console)** — все страницы: `favicon.ico`, CSP, `[DOM]` password.
5. **Блок 16 (Network)** — woff2 + API-запросы.
6. **Блок 17 (Responsive)** — sidebar collapse, таблицы, 768px / 393px.

**После 14–17:**
- Обновить `STATE_TEST_SESSION.md` (статусы 14–17).
- **55 (GitHub-пакет):** BACKLOG-028/046.
- **56 (BUG-117 hotfix).**
- **57 (релиз v3.0.0).**

### Долгосрочно

- **v3.1.0** — 13 направлений + BACKLOG-307/315, BUG-248/249.
- **v3.2.0** — ML, Kafka, Vault, HSM, PITR, macOS.
- **v4.0.0** — Zero-Trust, распределённый Manager.

---

## 🔧 СТЕК

| Компонент | Версия | Статус |
|-----------|--------|--------|
| Manager | `dcap/manager:3.14.3` | healthy |
| WebUI | `dcap/webui:3.14.3` | healthy |
| Celery worker/beat | `dcap/manager:3.14.3` | healthy |
| Postgres | 16-alpine | healthy |
| Redis | 7-alpine | healthy |
| Scanner | v3.14.3 (host) | running |
| MinIO | native `localhost:9000` | running |
| Grafana | `:3000` | ✅ протестирована (v3.14.2) |
| Prometheus | `:9090` | healthy (5/5 up) |
| Alertmanager | `:9093` | healthy (fire + resolve ✅) |
| Docker Compose | v5.5.1 | up |

**Порты:**
- WebUI: 8001
- Manager: 8000
- Grafana: 3000
- Prometheus: 9090
- Alertmanager: 9093
- PostgreSQL: 5432
- MinIO: 9000 (console 9001)

**Роли и пароли (тестовые):**
- `admin` / `admin123`
- `auditor` / `auditor123`
- `viewer` / `viewer123`
- `scanner` / `scanner123`

**Тестовые данные:**
- Resources: 142 (fs-regress, 210 findings), 143 (png-only, 4 findings), 144 (minio)
- Findings: 2043 (text_line, person), 2044/2045/2046 (image_region, OCR), 1995 (high_entropy), 1987 (aws_key FP), 2035 (phone FP)
- MinIO: 4 объекта в `dcap-audit-logs/access-logs/`
- Audit: 1908+ событий, 20 типов

---

## 📌 ИНСТРУКЦИЯ ДЛЯ НОВОЙ БЕСЕДЫ

**Приложить:**
1. `STATE_TEST_SESSION.md` (этот файл).
2. `STATE.md`.
3. `ROADMAP.md`.
4. `ARCHITECTURE.md`.
5. `docs/DESIGN.md`.

**Триггер:**
Продолжаем мастер-сессию DCAP v3.14.3.
Приложены: STATE_TEST_SESSION.md, STATE.md, ROADMAP.md, ARCHITECTURE.md, docs/DESIGN.md.

Пройдено: Блоки 1–9; 53.1a–53.3; 53.4a; 53.4a-доп; 53.4a-доп3/4/5; 53.4b; 53.4c/d/e; 53.4e-grafana + hotfix; 53.4e-rbac-hotfix; WebUI-прогон (блоки 1–13).
Закрыты в v3.14.2: BUG-245/246/247/236/241/243/239.
Закрыты в v3.14.3: BUG-253/254/255/256/257/258, BACKLOG-316.
Подтверждён: BACKLOG-307 (RBAC Grafana — v3.1.0).
Новые 🟢: BUG-248 (`Celery tasks (total)`), BUG-249 (`PostgreSQL connections`).

Следующий: верификация WebUI-блоков 14–17.
Затем — 55 (GitHub) → 56 (BUG-117) → 57 (релиз v3.0.0).

Unit: 472 passed. E2E: +4 v3.14.3 (таргетно PASSED; полный прогон — TEST-NOTE-10.8/10.10).
Стек: v3.14.3 (Docker Compose v5.5.1). Scanner (host): 3.14.3.

Начни с проверки: git log --oneline -10.

---

**Конец STATE_TEST_SESSION.md** — актуализирован под v3.14.3 (17.10.2026)