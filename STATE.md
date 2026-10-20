> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 20.10.2026
**Текущая версия:** v3.14.4 (v3.14.5 в работе)
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блоки 1–9 закрыты. BACKLOG-097 (S3-коннектор) закрыт. WebUI-редизайн этапы 1–5 закрыты — **REDESIGN COMPLETE (v3.14.1)**. Grafana протестирована (TEST-NOTE-8.1…8.6), 6 багов закрыто в hotfix v3.14.2, RBAC подтверждён (BACKLOG-307 → v3.1.0). RBAC hotfix (блоки 12–13: Users, Roles) — 7 задач (BUG-253/254/255/256/257/258, BACKLOG-316) закрыто в v3.14.3. UI hotfix v3.14.4 (блоки 15/17): закрыты BUG-265/266/267 (dashboard RBAC + 403-спам), BUG-270/271 (users responsive), BACKLOG-320/321/324 (BACKLOG-325 закрыт ранее). **Retention (Блок 18) — ✅ ЗАКРЫТ (v3.14.4, 20.10.2026) — проверены все 5 шагов + Celery Beat.** Найдены новые баги (BUG-NEW-4…7, BUG-272, BUG-273) — **переданы в 53.4g (v3.14.5)**. Unit **521 passed** (`pytest tests/unit manager/tests -q`), e2e **51/16/2/0** без предусловий (эталон **53/7**). **Следующий шаг — 53.4g (v3.14.5) → 55 (GitHub) → 56 (BUG-117) → 57 (релиз v3.0.0).**

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 53.4g (UI hotfix) — **в работе** |
| Статус дня | 🔄 Выполняется (v3.14.5) |
| Последний принятый отчёт | `day_53_4f_ui_hotfix_report.md` (v3.14.4); `day_53_4g_retention_report.md` (Блок 18, v3.14.4) |
| Следующий шаг | **53.4g (v3.14.5)** → **55 (GitHub) → 56 (BUG-117) → 57 (релиз v3.0.0)** |
| Открытых BUG | ~15 (включая новые BUG-NEW-4…7, BUG-272, BUG-273) |
| Открытых BACKLOG | ~50 (BACKLOG-156…315 — v3.1.0/бэклог) |
| ТЗ собраны | 1 активное (`prompts/tz/day_53_4g_ui_hotfix.md`) |
| Открытые вопросы к архитектору | 1) BUG-248/249 (Grafana, 🟢 low) — в бэклог; 2) BACKLOG-307 (RBAC Grafana) — v3.1.0; 3) BUG-236 вариант B (webhook) — v3.1.0 (BACKLOG-315) |

---

## ✅ Выполненные дни (v3.0.0)

| День | Задача | Версия | Отчёт |
|------|--------|--------|-------|
| 28-40.4 | WebUI, AD, безопасность, Findings Refactor | до v3.12.0 | *(см. предыдущие STATE)* |
| ... | ... | ... | ... |
| **53.4c (BACKLOG-093, этап 3/5)** | **Страницы: `/catalog`, `/resources`, `/access`, `/audit`, `/scanners`, `/findings`** | **v3.14.1** | `day_53_4cde_webui_pages_2_5_report.md` |
| **53.4d (BACKLOG-093, этап 4/5)** | **Роли/пользователи/настройки, футер, палитра Chart.js** | **v3.14.1** | `day_53_4cde_webui_pages_2_5_report.md` |
| **53.4e (BACKLOG-093, этап 5/5)** | **Полировка: favicon, CSP, DESIGN.md, скриншоты, E2E-очистка** | **v3.14.1** | `day_53_4cde_webui_pages_2_5_report.md` |
| **53.4e-grafana + hotfix** | **Grafana: тестирование (TEST-NOTE-8.1…8.6) + hotfix (BUG-245/246/247/236/241/243/239)** | **v3.14.2** | `day_53_4e_grafana_hotfix_report.md` |
| **53.4e-rbac-hotfix** | **RBAC блоки 12–13 (Users, Roles): BUG-253/254/255/256/257/258 + BACKLOG-316** | **v3.14.3** | `day_53_4e_rbac_hotfix_report.md` |
| **53.4f (тест-инфра)** | **BUG-259/260/261/263, BACKLOG-317, BUG-262 этап A** | **v3.14.3** | `day_53_4f_test_infra_report.md`, `day_53_4f_bug263_report.md` |
| **53.4f (UI hotfix)** | **BUG-265/266/267 (dashboard RBAC/403), BUG-270/271 (users responsive), BACKLOG-320/321/324** | **v3.14.4** | `day_53_4f_ui_hotfix_report.md` |
| **Блок 18 (Retention)** | **Полный цикл: status/policies/stats, dry-run, sync run, Celery (API + Beat), export** | **v3.14.4** | `day_53_4g_retention_report.md` |

---

## 🔴 Открытые проблемы (накопительно, топ-35)

### 🔴🔴 Критичные (блокеры v3.0.0)

| ID | Проблема | Статус | ТЗ |
|----|----------|--------|-----|
| **BUG-NEW-4** | Dashboard: фикс RBAC не работает (viewer → 403-спам) | 📋 | 53.4g (v3.14.5) |
| **BUG-273** | Dashboard (393px): KPI-карточки вылезают за экран | 📋 | 53.4g (v3.14.5) |
| **BUG-117** | Manager не маскирует контексты сам | 📋 | день 56 (hotfix) |
| **BUG-172** | Нет `permissions` в RBAC | 📋 | архитектура v3.1.0 |
| **BUG-118** | Auth middleware держит 2 соединения | 📋 | v3.1.0 |
| **BUG-135** | S3-агент: BOM | 📋 | v3.1.0 |
| **BACKLOG-044** | `/metrics` публичный | 📋 | production |
| **BACKLOG-307** | Grafana RBAC + DCAP RBAC (Auth Proxy) | 📋 | v3.1.0 |

### 🟡 Важные (не блокеры v3.0.0)

| ID | Проблема | ТЗ |
|----|----------|-----|
| **BUG-NEW-5** | Settings: редирект на /login при неверном пароле | 📋 53.4g (v3.14.5) |
| **BUG-NEW-6** | Settings: не отображается last_run | 📋 53.4g (v3.14.5) |
| **BUG-NEW-7** | Settings: CSS-баг (слипшийся текст счётчиков) | 📋 53.4g (v3.14.5) |
| **BUG-272** | Dashboard: пустые графики при 0 находок | 📋 53.4g (v3.14.5, опц.) |
| BUG-248 | `Celery tasks (total)` → `No data` | 🟢 v3.1.0 |
| BUG-249 | `PostgreSQL connections` — легенда | 🟢 v3.1.0 |
| BACKLOG-101 | stroke-SVG иконки | v3.1.0 |
| BACKLOG-102 | light-тема | v3.1.0 |
| BACKLOG-103 | S3 fallback на config-секреты | v3.1.0 |
| BACKLOG-315 | Alertmanager webhook → Manager (вариант B) | v3.1.0 |
| BUG-123 | Windows-агент: сбор прав | 52.2 |
| BUG-125/130 | Linux-агент: env / retry | v3.1.0 |
| BUG-221 | Reveal — странные email | v3.1.0 |
| BUG-235 | SIEM-страницы 404 | v3.1.0 |
| BUG-259 | `test_ad_permissions` — `ModuleNotFoundError` в combined-прогоне | ✅ v3.14.3 |
| BUG-260 | Windows: `PermissionError` на `pytest-current` | ✅ v3.14.3 |
| BUG-261 | `test_archiver_findings` — `TypeError` (устаревшая схема `Finding`) | ✅ v3.14.3 |
| BUG-262 | E2E-эталон не воспроизводим без предусловий (51/16/2/0 vs 53/7) | 🟡 этап A ✅ (v3.14.3); этап B — до 55 |
| BUG-263 | `test_webui_block5_v31322` — `X-Total-Count=0`, `loadFilterOptions` только в `audit.js` | ✅ v3.14.3 (`loadFilterOptions` — тест-инфра, не UI; `X-Total-Count` — BUG-262 этап B) |
| BACKLOG-317 | `docker-compose.test.yml` — общее имя проекта сносит основной стек | ✅ v3.14.3 (`name: dcap-test`) |
| BACKLOG-046 | Полный E2E-прогон на CI | день 55 |

---

## 🎯 Ключевые решения (обновление)

**Закрыто в 53.4e-grafana hotfix (v3.14.2):**
- BUG-245 — `scanner_id=""` (hardening, warning-лог, `+Inf` при `None`).
- BUG-246 — `dcap_findings_total` → Gauge из БД; `dcap_findings_created_total` — Counter сессии.
- BUG-247 — FP (авто-метрика `<counter>_created`).
- BUG-236 — webhook убран из `alertmanager.yml`.
- BUG-241 — `or vector(0)` в `dcap-overview.json`.
- BUG-243 — `s3-agent` target закомментирован.
- BUG-239 — 2 пустые панели удалены из `dcap-scanner.json`.

**Закрыто в 53.4e-rbac-hotfix (v3.14.3):**
- BUG-253 — нельзя снять роль `admin` с себя: чекбокс disabled + `PUT /users/{self}` без `admin` → 400.
- BUG-254 — пользователь без ролей → 400 (backend + frontend-валидация).
- BUG-255 — кнопка «Войти» в стиле Dovetail (8px, weight 500).
- BUG-256 — 403 в WebUI: toast «Недостаточно прав» + редирект на главную.
- BUG-257 — системные роли иммутабельны по `name`/`ad_group` (backend 400 + disabled).
- BUG-258 — кастомные роли отключены до v3.1.0 (`POST /roles` → 403, кнопка disabled).
- BACKLOG-316 — роль `scanner` скрыта в `/users` (в `/roles` остаётся).
- BUG-252 (follow-up) — `base.css`: `input:not([type=checkbox]):not([type=radio])` — чекбоксы/радио выведены из глобального `input`-фона (`:checked`-галочка — `components.css`, `ae40933`; follow-up `eb7ee30`).

**Закрыто в тест-инфре (v3.14.3, 17.10.2026):**
- BUG-259 — `manager/src/connectors/` стал regular-пакетом (`__init__.py`) + зачистка `sys.modules['connectors*']` в `test_ad_permissions`; combined `tests/unit + manager/tests` → 517 collected, 0 errors.
- BUG-260 — корневой `conftest.py` переносит `basetemp` в `.pytest-tmp/` (Windows), добавлено в `.gitignore`.
- BUG-261 — `test_archiver_findings` приведён к схеме `Finding` v3.9.0 (`finding_type`/`fragment_type`/`fingerprint`/`encryption_key_id`/`first_seen_at`).
- BACKLOG-317 — `docker-compose.test.yml`: `name: dcap-test` (отдельный project name, больше не сносит основной стек).
- BUG-262 этап A — документация стенда (`docs/testing.md`, реальные 48/12/5); этап B (seed + маркеры) — до 55.
- BUG-263 — ✅ `test_webui_pages_with_filters` проверяет подключение `/static/js/audit.js` + наличие `loadFilterOptions` в JS (было — в серверном HTML, ложно-отрицательный). UI корректен, тест-инфра.
- Unit-команда зафиксирована: `pytest tests/unit manager/tests -q` → **517 passed** (корневой `conftest.py`, без `--basetemp`).

**Закрыто в UI hotfix (v3.14.4, 18.10.2026):**
- BUG-265/267 — `dashboard.js`: `checkAuditAccess()` (через `RBAC.isAuditor()` + `whenSessionReady()`, fallback `Auth.me()`) — viewer/scanner больше не вызывают `/api/audit/*`; KPI «—» + плашка «Нет прав на аудит» (`#auditCharts`, `#recentEvents`).
- BUG-266 — `api.js`: `console.warn` только для `status !== 403` (RBAC-403 — ожидаемые, без спама); `e.status` заполняется.
- BUG-270/271 — `/users`: `.table-responsive-users` (`overflow-x: auto`; `min-width: 760px` ≤900px, `900px` ≤480px).
- BACKLOG-324 — `/findings`: мобильный collapse фильтров (кастомный тоггл `toggleFindingsFilters` + CSS, т.к. Bootstrap JS bundle не подключён).
- BACKLOG-320/321 — a11y: скрытый `username` в `#passwordForm`, `autocomplete` на inputs (`users.html`, `findings.html`).
- BACKLOG-325 — затемнение overlay уже в `main.css` (`rgba(0,0,0,.5)`), правок не требовалось.
- Unit-команда: `pytest tests/unit manager/tests -q` → **521 passed** (было 517; +4 новых).

**Блок 18 (Retention) — закрыт (v3.14.4, 20.10.2026):**
- Все 5 шагов пройдены: status/policies/stats, dry-run (0 изменений), sync run (findings 5→0, tasks 1→0), Celery (API + Beat: `16:01:00` — архивация 1 находки, удаление 1 задачи, **без Mapper-ошибок**), export (5 архивных находок → JSON).
- На изолированном стенде Celery-воркер не запущен (особенность `docker-compose.test.yml`), поэтому Celery проверен на основном стенде.
- **Celery Beat работает** (проверено временным изменением `crontab(minute='*')` + пересборка образа).

**Найдено в мастер-сессии (20.10.2026) — передано в 53.4g (v3.14.5):**
- BUG-NEW-4 (критичный) — dashboard RBAC: `checkAuditAccess()` не блокирует запросы к `/api/audit/*` под viewer (403-спам, тосты).
- BUG-NEW-5 — Settings: редирект на `/login` при неверном пароле (вместо тоста).
- BUG-NEW-6 — Settings: не отображается `last_run`.
- BUG-NEW-7 — Settings: CSS-баг (слипшийся текст счётчиков).
- BUG-273 (критичный) — Dashboard (393px): KPI-карточки вылезают за экран.
- BUG-272 (опц.) — Dashboard: пустые графики при 0 находок (нет плашки «Нет данных»).

**Факт E2E (2026-10-20, стенд `:18000/:18001`, предусловия не выполнены):**
- `51 passed, 16 skipped, 2 failed, 0 error` (собрано 69).
- 2 failed — `test_webui_block5_v31322::test_proxy_forwards_total_count` и
  `::test_findings_filters_csv_and_empty` (seed-findings, BUG-262 этап B).
- 16 skipped: 4× сканер `:9101`, 3× `auditor/auditor123`, 3× MinIO, 5× seed-findings, 1× `test_webui_block5_v31322` (image_region).
- Эталон `53/7` — при предусловиях (сканер `:9101`, MinIO `:9000`, seed, auditor).

**Grafana (решения 17.10.2026):**
- **RBAC:** подтверждён BACKLOG-307, реализация — **v3.1.0** (Auth Proxy, `X-WEBAUTH-USER`). Маппинг: admin→Admin, auditor→Editor, scanner/viewer→Viewer.
- **Тестирование:** TEST-NOTE-8.1…8.6 — **✅**.
- **BUG-236:** вариант A (webhook убран). Вариант B (полный эндпоинт) — BACKLOG-315 (v3.1.0).
- **BUG-239:** вариант A (панели удалены). Вариант B (метрики per-file/OCR) — v3.1.0.

---

## 📌 Рекомендации архитектору

1. **Следующий шаг — 53.4g (v3.14.5)** (хотфикс новых багов).
2. **Затем — 55** (GitHub-пакет) → **56** (BUG-117 hotfix) → **57** (релиз v3.0.0).
3. **`STATE_TEST_SESSION.md`** — обновлён до v3.14.4 (Блок 18 закрыт), новые баги переданы в 53.4g.
4. **`ARCHITECTURE.md`** — v3.14.4 (ролевая модель + UI hotfix: RBAC-фронт дашборда, responsive).
5. **BUG-248/249** — 🟢 low, в бэклог v3.1.0.
6. **BACKLOG-307** — v3.1.0.
7. **E2E-артефакты** — ✅ очищены (53.4e).
8. **13 направлений v3.1.0** — зафиксированы (BACKLOG-156…314 + 315).
9. **BUG-263** — ✅ закрыт (v3.14.3, 53.4f): тест проверяет `/static/js/audit.js` + `loadFilterOptions` в JS; UI корректен.
10. **BUG-262** — этап A ✅; этап B (seed + маркеры `requires_minio`/`requires_seed`) — до 55; этап C (CI) — BACKLOG-046 (день 55).
11. **BACKLOG-317** — ✅ `name: dcap-test`; перед `down` стенда убеждаться, что project name отличается от основного.
12. **UI hotfix v3.14.4** — ✅ BUG-265/266/267/270/271, BACKLOG-320/321/324 (BACKLOG-325 — закрыт ранее); карточки users на 393px (BACKLOG-326) — v3.1.0.
13. **Блок 18 (Retention)** — ✅ закрыт (все 5 шагов + Celery Beat).
14. **53.4g (v3.14.5)** — активное ТЗ: `prompts/tz/day_53_4g_ui_hotfix.md`.

---

**Актуально на:** 20.10.2026
**Версия:** v3.14.4 (v3.14.5 в работе)
**Следующий шаг:** 53.4g (v3.14.5) → 55 → 56 → 57