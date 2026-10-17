> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 17.10.2026
**Текущая версия:** v3.14.3
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блоки 1–9 закрыты. BACKLOG-097 (S3-коннектор) закрыт. WebUI-редизайн этапы 1–5 закрыты — **REDESIGN COMPLETE (v3.14.1)**. Grafana протестирована (TEST-NOTE-8.1…8.6), 6 багов закрыто в hotfix v3.14.2, RBAC подтверждён (BACKLOG-307 → v3.1.0). RBAC hotfix (блоки 12–13: Users, Roles) — 7 задач (BUG-253/254/255/256/257/258, BACKLOG-316) закрыто в v3.14.3. Unit **472 passed** (466 + 6 metrics), e2e **+4 (v3.14.3, таргетно PASSED)**. **Следующий шаг — верификация WebUI-блока 14 (Settings) → 55 (GitHub).**

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 53.4e-rbac-hotfix (Users, Roles — блоки 12–13) — **завершён** |
| Статус дня | ✅ Выполнено (hotfix v3.14.3) |
| Последний принятый отчёт | `day_53_4e_rbac_hotfix_report.md` (v3.14.3) |
| Следующий шаг | **Верификация WebUI-блока 14 (Settings)** (ручной прогон) → **55 (GitHub) → 56 (BUG-117) → 57 (релиз)** |
| Открытых BUG | ~12 (в основном 🟢 low / v3.1.0) |
| Открытых BACKLOG | ~50 (BACKLOG-156…315 — v3.1.0/бэклог) |
| ТЗ собраны | 2 файла в `prompts/tz/` (53.4c/d/e — архив, Grafana — архив) |
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

---

## 🔴 Открытые проблемы (накопительно, топ-30)

### 🔴🔴 Критичные (блокеры v3.0.0)

| ID | Проблема | Статус | ТЗ |
|----|----------|--------|-----|
| **BUG-117** | Manager не маскирует контексты сам | 📋 | день 56 (hotfix) |
| **BUG-172** | Нет `permissions` в RBAC | 📋 | архитектура v3.1.0 |
| **BUG-118** | Auth middleware держит 2 соединения | 📋 | v3.1.0 |
| **BUG-135** | S3-агент: BOM | 📋 | v3.1.0 |
| **BACKLOG-044** | `/metrics` публичный | 📋 | production |
| **BACKLOG-307** | Grafana RBAC + DCAP RBAC (Auth Proxy) | 📋 | v3.1.0 |

### 🟡 Важные (не блокеры v3.0.0)

| ID | Проблема | ТЗ |
|----|----------|-----|
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

**Grafana (решения 17.10.2026):**
- **RBAC:** подтверждён BACKLOG-307, реализация — **v3.1.0** (Auth Proxy, `X-WEBAUTH-USER`). Маппинг: admin→Admin, auditor→Editor, scanner/viewer→Viewer.
- **Тестирование:** TEST-NOTE-8.1…8.6 — **✅**.
- **BUG-236:** вариант A (webhook убран). Вариант B (полный эндпоинт) — BACKLOG-315 (v3.1.0).
- **BUG-239:** вариант A (панели удалены). Вариант B (метрики per-file/OCR) — v3.1.0.

---

## 📌 Рекомендации архитектору

1. **Следующий шаг — верификация WebUI-блока 14 (Settings)** (ручной прогон). После редизайна v3.14.1 они закрыты кодом, но не проверены вручную.
2. **Затем — 55** (GitHub-пакет) → **56** (BUG-117 hotfix) → **57** (релиз).
3. **`STATE_TEST_SESSION.md`** — обновлён до v3.14.3, блоки 12–13 — ✅ (после прогона), 14–17 — ⏳.
4. **`ARCHITECTURE.md`** — v3.14.3 (ролевая модель: BUG-253/257/258, BACKLOG-316).
5. **BUG-248/249** — 🟢 low, в бэклог v3.1.0.
6. **BACKLOG-307** — v3.1.0.
7. **E2E-артефакты** — ✅ очищены (53.4e).
8. **13 направлений v3.1.0** — зафиксированы (BACKLOG-156…314 + 315).

---

**Актуально на:** 17.10.2026
**Версия:** v3.14.3
**Следующий шаг:** верификация WebUI 14 → 55 → 56 → 57