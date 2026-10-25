# 🧪 DCAP Test Session — Состояние на 25.10.2026

> **Мастер-сессия ручного тестирования DCAP v3.14.15**
> Блок 1 (Smoke) — ✅
> Блок 2 (Auth/RBAC) — ✅
> Блок 3 (Scanner deep) — ✅
> Блок 4 (Findings API) — ✅
> Блок 5 (WebUI) — ✅ (блоки 1–13), ⏳ 14–17
> Блок 6 (Агенты) — ⚠️ 5/6 под-блоков
> Блок 7 (Retention) — ✅
> Блок 8 (Мониторинг) — ✅ (Prometheus + Grafana, v3.14.2)
> Блок 9 (Безопасность) — ✅
> **Блок 18 (Retention) — ✅ (v3.14.4)**
> 53.4a–53.4f — ✅ v3.13.37–v3.14.4
> **53.4g (v3.14.5)** — Settings/RBAC/Responsive (частично)
> **53.4h (v3.14.6)** — Dashboard RBAC (BUG-274) ✅
> **53.4i (v3.14.7)** — Scanners checkbox (BUG-278) ✅
> **53.4j (v3.14.8)** — scanner perf, ч.1
> **53.4k (v3.14.9)** — singleton extractor + lru_cache
> **53.4l (v3.14.10)** — дедуп + NER off ✅
> **53.4m (v3.14.11)** — multiprocessing ✅
> **53.4n (v3.14.12)** — resume + логи + reconnect ✅
> **53.4o (v3.14.13)** — pool reuse ✅
> **53.4p (v3.14.14)** — final/release/progress ✅
> **BUG-292 (v3.14.15)** — кодировка `finding_detail.js` ✅
> **WebUI (находки) — ✅** (Reveal, статус, фильтры, аудит)

---

## 🎯 Текущее состояние

| Параметр | Значение |
|----------|----------|
| **Версия** | v3.14.15 |
| **Целевая версия** | v3.0.0 (релиз) |
| **Пройдено** | Блоки 1–9; 53.1a–53.3; 53.4a–53.4p; Retention (Блок 18); WebUI (находки) |
| **Следующий блок** | **53.5 (security_scan)** → 55 (GitHub) → 56 (BUG-117) → 57 (релиз) |
| **Auth mode** | hybrid (SPNEGO → JWT fallback) |
| **Контейнеров** | 15 |
| **Сканер** | На хосте, v3.14.15, multiprocessing (4 воркера) |
| **Unit** | **528 passed** (`pytest tests/unit -q`; +1 flaky s3 — BACKLOG-339) |
| **E2E** | Стенд `:18000/:18001`; эталон **53/7** — при предусловиях |
| **Docker Compose** | v5.5.1 |

---

## ✅ ЗАКРЫТО В ЭТОЙ СЕССИИ (20–25.10.2026)

### 53.4l (v3.14.10) — finding-взрыв
- **BUG-281** — дедуп по `(category, match_text)`, `metadata["locations"]`.
- **BUG-282** — NER off (PERSON/LOCATION/ORG/DATE_TIME/NRP).
- `Files/min` 24.0 → 65.8; findings/файл 666 → 0.6.

### 53.4m (v3.14.11) — multiprocessing
- `ProcessPoolExecutor` ×2.09 (63.7 → 132.9 ф/мин), память ×1.54.
- `max_workers=2` (Windows/16 ГБ), `4` (32 ГБ), `8` (128 ГБ); Linux — `nproc-1`.

### 53.4n (v3.14.12) — resume + логи + reconnect
- **BUG-280** — `ScanState` (chunk-aware), `Ctrl+C` → save + release (pending).
  `[Resume] ... с чанка N+1/M`.
- **BUG-283** — `FileHandler` (rotating 100 МБ × 5) + `StreamHandler`.
- **BUG-284** — `[ManagerClient] [OK] Reconnected (was offline Xs)`.

### 53.4o (v3.14.13) — pool reuse
- **BUG-286** — `ProcessPoolExecutor` 1 раз на задачу. Warmup 4 (не 40).
  `Files/min` 30–40 → 132.9; ETA 22 500 → ~3 ч.

### 53.4p (v3.14.14) — final/release/progress
- **BUG-287** — `final=True` только последний чанк (200, не 400).
- **BUG-288** — `release` для `completed` → 204 (no-op).
- **BUG-289** — `ScanProgress` монотонный.

### BUG-292 (v3.14.15) — кодировка `finding_detail.js`
- CP1251 → UTF-8 (без BOM). Подписи/кнопки — RU, Console — 0 ошибок.

### WebUI (находки) — ручная приёмка
- `/findings`: список, фильтры (категория, статус, детектор), пагинация — ✅.
- `/findings/{id}`: детали, `context_*`, **Reveal** (расшифровка + подсветка match),
  смена статуса (confirmed/FP/duplicate/archived) — ✅.
- `/audit`: `finding_reveal`, `fragment_accessed`, `auth_login` — ✅.
- ⚠️ BUG-293 (UX): `finding_reveal — просмотр оригинала` (дублирование) — v3.0.1.

---

## 🔴 ОТКРЫТЫЕ ПРОБЛЕМЫ

### 🔴 Критичные (блокеры v3.0.0)

| ID | Название | Фаза |
|----|----------|------|
| **BUG-117** | Manager не маскирует контексты сам | день 56 |
| **BUG-172** | Нет `permissions` в RBAC | v3.1.0 |
| **BUG-118** | Auth middleware — 2 соединения | v3.1.0 |
| **BUG-135** | S3-агент: BOM | v3.1.0 |
| **BACKLOG-044** | `/metrics` публичный | production |
| **BACKLOG-307** | Grafana RBAC + DCAP RBAC | v3.1.0 |

### 🟡 Важные (не блокеры v3.0.0)

| ID | Проблема | ТЗ |
|----|----------|-----|
| **BUG-293** | `/audit`: дублирование перевода | **v3.0.1** |
| **BACKLOG-339** | 1 flaky s3 (unit) | v3.0.1 |
| BUG-123 | Windows-агент: сбор прав | 52.2 |
| BUG-125 | Linux-агент: `MANAGER_URL` env | v3.1.0 |
| BUG-130 | Linux-агент: retry без backoff | v3.1.0 |
| BUG-221 | Reveal — странные email | v3.1.0 |
| BUG-235 | SIEM-страницы 404 | v3.1.0 |
| BACKLOG-101/102/103 | stroke-SVG, light-тема, S3 fallback | v3.1.0 |
| BACKLOG-315 | Alertmanager webhook | v3.1.0 |

### 🟢 Мелкие

| ID | Проблема | ТЗ |
|----|----------|-----|
| BUG-248 | `Celery tasks (total)` → `No data` | v3.1.0 |
| BUG-249 | `PostgreSQL connections` — легенда | v3.1.0 |
| TEST-NOTE-3.1/5.2/10.1/10.3/10.8/10.10/10.11/10.12/10.13/10.15/NEW-3 | docs/бэклог | — |

---

## ✅ ЧТО ПОДТВЕРЖДЕНО РАБОТАЮЩИМ

### Retention (Блок 18) — ✅ v3.14.4
- `/status`, `/policies`, `/stats` — корректно.
- Dry-run — stats не меняются.
- Sync run — findings/tasks уменьшились.
- Celery (API + Beat) — без Mapper-ошибок.
- Export — файл (JSON).

### Scanner (v3.14.10–15)
- Дедуп (609 → 0.6/файл), NER off.
- Multiprocessing (132.9 ф/мин на 4 ядрах; `max_workers=2` — 55–60 на 16 ГБ).
- Resume: `Ctrl+C` → state → `[Resume] с чанка N+1/M` → завершение (findings = baseline).
- Pool reuse: `ProcessPoolExecutor` 1 раз; warmup 4 (не 40).
- Логи: `logs/scanner.log` (INFO, ротация); консоль — всё (DEBUG).
- Reconnect: `[OK] Reconnected (was offline Xs)`.

### WebUI (находки) — ✅ v3.14.15
- Список, фильтры, пагинация.
- Детали, `context_*`.
- **Reveal** — расшифровка + подсветка match (Auditor+).
- Смена статуса — confirmed/FP/duplicate/archived.
- Аудит — `finding_reveal`, `fragment_accessed`, `auth_login`.
- **Кодировка** — UTF-8 (0 ошибок в Console).

---

## 📋 СЛЕДУЮЩИЕ ШАГИ

### Следующий шаг — 53.5 (security_scan)
- **ТЗ:** `prompts/tz/day_53_5_security_checks.md` (SAST/SCA/DAST/secrets/containers).
- **Скрипт:** `scripts/security_scan.ps1` (Bandit, Semgrep, Gitleaks, pip-audit, Trivy, ZAP).
- **Dogfooding:** DCAP-сканер на собственном репозитории (поиск секретов).

### Далее
- **55 (GitHub-пакет):** BACKLOG-028/046.
- **56 (BUG-117 hotfix).**
- **57 (релиз v3.0.0).**

### Долгосрочно
- **v3.0.1** — BUG-293, BACKLOG-339.
- **v3.1.0** — 13 направлений + Cython/Rust + BACKLOG-307/315, BUG-248/249.
- **v4.0.0** — Zero-Trust, распределённый Manager, **Security Gateway (MTA + Squid + ICAP + AI Gateway)**.

---

## 🔧 СТЕК

| Компонент | Версия | Статус |
|-----------|--------|--------|
| Manager | `dcap/manager:3.14.15` | healthy |
| WebUI | `dcap/webui:3.14.15` | healthy |
| Celery worker/beat | `dcap/manager:3.14.15` | healthy |
| Postgres | 16-alpine | healthy |
| Redis | 7-alpine | healthy |
| Scanner | v3.14.15 (host) | running |
| MinIO | native `localhost:9000` | running |
| Grafana | `:3000` | ✅ v3.14.2 |
| Prometheus | `:9090` | healthy (5/5 up) |
| Alertmanager | `:9093` | healthy |
| Docker Compose | v5.5.1 | up |

**Порты:** WebUI 8001, Manager 8000, Grafana 3000, Prometheus 9090,
Alertmanager 9093, PostgreSQL 5432, MinIO 9000 (console 9001).

**Роли (тестовые):** `admin/admin123`, `auditor/auditor123`, `viewer/viewer123`,
`scanner/scanner123`.

**Тестовые данные:** Resources 9 (`E:\much_of_test_files`), 142 (fs-regress),
143 (png-only), 144 (minio); Findings: 2043 (text_line, person), 2044/2045/2046
(image_region, OCR), 1995 (high_entropy), 1987 (aws_key FP), 2035 (phone FP);
MinIO: 4 объекта; Audit: 2107+ событий, 20 типов.

---

## 📌 ИНСТРУКЦИЯ ДЛЯ НОВОЙ БЕСЕДЫ

**Приложить:**
1. `STATE_TEST_SESSION.md` (этот файл).
2. `STATE.md`.
3. `ROADMAP.md`.
4. `ARCHITECTURE.md`.
5. `docs/testing.md`.

**Триггер:**
Продолжаем мастер-сессию DCAP v3.14.15.
Приложены: STATE_TEST_SESSION.md, STATE.md, ROADMAP.md, ARCHITECTURE.md, docs/testing.md.

Пройдено: Блоки 1–9; 53.1a–53.3; 53.4a–53.4p; Retention (Блок 18) ✅;
53.4l (дедуп + NER off) ✅; 53.4m (multiprocessing) ✅;
53.4n (resume + логи + reconnect) ✅; 53.4o (pool reuse) ✅;
53.4p (final/release/progress) ✅; BUG-292 (кодировка UI) ✅;
WebUI (находки) ✅ (Reveal, статус, фильтры, аудит).

Следующий: **53.5 (security_scan)** → 55 (GitHub) → 56 (BUG-117) → 57 (релиз v3.0.0).

Unit: 528 passed (`pytest tests/unit -q`).
E2E: стенд `:18000/:18001`; эталон 53/7 — при предусловиях.
Стек: v3.14.15 (Docker Compose v5.5.1). Scanner (host): 3.14.15.

Начни с проверки: git log --oneline -10.

---

**Конец STATE_TEST_SESSION.md** — актуализирован под v3.14.15 (25.10.2026)