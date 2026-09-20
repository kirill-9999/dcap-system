> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 20.09.2026
**Текущая версия:** v3.13.10
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Fix-спринт №1 (Auth/RBAC) завершён (BUG-039…059 + BUG-048b); следующий этап — ТЗ №2 (ENV-ключи)

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 46 — BUG-048b (middleware JWT для machine-API) |
| Статус дня | ✅ Выполнен (v3.13.10) |
| Последний принятый отчёт | `day_45_fix_sprint_report.md` (закрыт), далее BUG-048b — см. CHANGELOG v3.13.10 |
| Следующий шаг | Выполнить ТЗ №2 (ENV-ключи, `TZ_FIX_SPRINT_2.md`) → повторный RBAC-прогон |
| Открытые вопросы к архитектору | — |

---

## ✅ Выполненные дни (v3.0.0)

| День | Задача | Версия | Отчёт |
|------|--------|--------|-------|
| 28-40.4 | WebUI, AD, безопасность, Findings Refactor | до v3.12.0 | *(см. предыдущие STATE)* |
| 42.1-42.4 | Админ-руководство | — | ✅ |
| 43 (блок 1) | BUG-034/035/027/022 + Deploy/Config | v3.13.3-4 | `day_43_*` |
| 44 (BUG-034) | Зависшие задачи сканера | v3.13.7 | `day_44_bug_034_report.md` |
| 44 (AD) | AD-контейнер: profile 'ad' | v3.13.8 | `day_44_ad_packaging_report.md` |
| 45 (тест) | Мастер-сессия: Блок 2 (Auth/RBAC) | v3.13.8 | `STATE_TEST_SESSION.md` |
| 45 (φix) | Fix-спринт №1: BUG-039…059 | v3.13.9 | `day_45_fix_sprint_report.md` |
| 45 (док) | `05-security.md`, SECURITY, checklist, deployment | v3.13.8 | — |
| 46 (BUG-048b) | Middleware: JWT для machine-API (RBAC на scanner) | v3.13.10 | CHANGELOG + тесты |

---

## 🔴 Открытые проблемы

### Fix-спринт №1 (Auth/RBAC) — ✅ закрыт (v3.13.9 + v3.13.10)

| ID | Проблема | Статус |
|----|----------|--------|
| BUG-039..044, BUG-046..055, BUG-057..059 | Fix-спринт №1 | ✅ v3.13.9 |
| BUG-048b | Middleware не извлекал JWT на `/api/scanner/*` (401 вместо 403/404) | ✅ v3.13.10 |

### Fix-спринт №2 (ENV-ключи) — подготовлено

| ID | Задача | Приоритет |
|----|--------|-----------|
| TASK-016 | `scripts/reencrypt_findings.py` | 🔴 |
| TASK-017 | Fail-fast сканера (BUG-057) | 🔴 |
| TASK-018 | Убрать Docker Secrets (Findings) | 🟡 |
| TASK-019 | Обновить документацию | 🟡 |
| TASK-020 | E2E-тест ротации ключей | 🟡 |
| TASK-021 | Закрыть ТЗ №1 | 🟢 |

### Прочее

| ID | Проблема | Статус | Приоритет |
|----|----------|--------|-----------|
| BACKLOG-039 | Аудит NOT NULL полей | 📋 | 🟡 |
| BACKLOG-044 | Защита `/metrics` | 📋 production | 🟡 |
| BACKLOG-045 | Параметризация портов | 📋 | 🟢 |
| BACKLOG-063 | Presidio производительность | 📋 v3.1.0 | 🟡 |
| BACKLOG-064 | Бенчмарк сканирования | 📋 v3.1.0 | 🟢 |
| BACKLOG-065 | Удалить `findings_old` | 📋 v3.0.0 | 🟢 |
| **BACKLOG-068** | **Per-scanner keys** | **📋 v3.1.0** | **🟡** |

*(Закрытые в v3.7.0: BACKLOG-021, 037, 038, 041, 042)*
*(Закрытые в v3.8.0: alembic 002, rate-limit через env, гонка `/api/tasks/create`, tmpfs)*
*(Закрытые в v3.9.0-v3.12.0: BACKLOG-050…067 — Findings Refactor полностью)*
*(Закрытые в v3.13.5-8: BUG-022/022.9, BUG-027, BUG-034, BUG-035, AD-упаковка)*
*(Закрытые в v3.13.9: BUG-039…044, BUG-046…055, BUG-057…059 — fix-спринт №1)*
*(Закрытые в v3.13.10: BUG-048b — middleware machine-API с извлечением JWT)*

---

## 🎯 Ключевые решения

**Findings Refactor (v3.9.0-v3.13.8):**
- Findings = строка/фрагмент, гибрид masked + AES-256-GCM
- HMAC-SHA256 fingerprint
- **NEW: Ключи Findings — только через ENV** (не Docker Secrets)
- **NEW: Scanner fail-fast без ключей** (BUG-057 fix)
- **NEW: Ротация ключей — с downtime** (перешифровка + обновление ENV)
- **NEW: Единый ключ для v3.0.0**, per-scanner keys — v3.1.0 (BACKLOG-068)
- **Обоснование:** mTLS защищает канал, ключи — данные в состоянии покоя

**Аутентификация (Блок 2):**
- `verify_token(token, expected_type)` — access ≠ refresh (BUG-039)
- RBAC системно — `Depends(require_role(...))` во все write-эндпоинты (BUG-046…055)
- Cookie `Secure` — авто по HTTPS или env (BUG-042)
- `jti` + `iat` в JWT — v3.1.0 (BUG-041 + TEST-NOTE-2.6a)

**Общие:**
- Scanner — на хосте, не в Docker
- Heartbeat-thread — выделенный daemon
- spaCy-модели `sm`

---

## 📁 Последние использованные файлы

- `manager/src/auth/middleware.py` — BUG-048b: `/api/scanner/*` извлечение JWT + сессия до ответа
- `tests/unit/test_scanner_middleware_rbac.py` — 9 регрессионных тестов
- `TZ_FIX_SPRINT_2.md` — ТЗ №2 (ENV-ключи) — следующий этап
- `docs/admin-guide/{06-scanner.md,05-security.md}` — модель доступа scanner-API / Machine-API и JWT
- `CHANGELOG.md` — v3.13.10 (2026-09-20)
- `docker-compose.yml`, `.env.example`, `.env`, `webui/config.py` — версия 3.13.10
- `STATE_TEST_SESSION.md` — протокол Блока 2
- `backups/dcap_20260919_172037.sql` + `dcap_before_fixes_*.sql`

---

**Актуально на:** 20.09.2026
**Версия:** v3.13.10
**Следующий шаг:** выполнить ТЗ №2 (ENV-ключи)