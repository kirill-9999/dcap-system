📄 2. STATE.md (обновлённый)
markdown
> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 20.09.2026 (отчёт + архивация ТЗ + пересборка контейнеров v3.13.9)
**Текущая версия:** v3.13.9
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Fix-спринт завершён — все 15 багов закрыты (BUG-037…059), 109 тестов ✅; отчёт и архив ТЗ оформлены; контейнеры пересобраны на v3.13.9

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 45 — Fix-спринт по результатам Блока 2 |
| Статус дня | ✅ Выполнен (все 15 багов закрыты) |
| Последний принятый отчёт | `day_45_fix_sprint_report.md` (20.09.2026, сформирован) |
| Следующий шаг | Мастер-сессия: регресс Блока 2 на собранном стеке (STATE_TEST_SESSION.md) + релиз v3.0.0 |
| Открытые вопросы к архитектору | — |

---

## ✅ Выполненные дни (v3.0.0)

| День | Задача | Версия | Отчёт |
|------|--------|--------|-------|
| 28-40.4 | WebUI, AD, безопасность, Findings Refactor, фрагменты | до v3.12.0 | *(см. предыдущие STATE)* |
| 42.1 | Админ-руководство: установка + конфигурация | — | ✅ |
| 42.2 | Админ-руководство: аутентификация + безопасность | — | ✅ |
| 43 (блок 1) | BUG-034/035/027/022 + Deploy/Config + WebUI | v3.13.3-4 | `day_43_*` |
| 44 (BUG-034) | Зависшие задачи сканера при прерывании | v3.13.7 | `day_44_bug_034_report.md` |
| 44 (AD) | AD-контейнер: профиль 'ad' | v3.13.8 | `day_44_ad_packaging_report.md` |
| **45 (тест)** | **Мастер-сессия: Блок 2 (Auth/RBAC)** | **v3.13.8** | **`STATE_TEST_SESSION.md`** |
| **45 (fix-спринт)** | **BUG-037…059 (15 багов) + RBAC API-слоя + тесты + пересборка контейнеров v3.13.9** | **v3.13.9** | **`day_45_fix_sprint_report.md`** |

---

## 🔴 Открытые проблемы (fix-спринт)

### Критичные (блокеры v3.0.0)

| ID | Проблема | Компонент | Статус |
|----|----------|-----------|--------|
| BUG-039 | Refresh-токен принимается как access | `auth/jwt.py::verify_token` | ✅ |
| BUG-046 | Все роли DELETE `/api/resources/{id}` | `api/resources.py:104` | ✅ |
| BUG-047 | DELETE `/api/tasks/{id}` без auth | `api/tasks.py:91` | ✅ |
| BUG-048 | DELETE `/api/scanner/{id}` без auth + 500 | `api/scanner.py:706` | ✅ |

### Важные

| ID | Проблема | Статус |
|----|----------|--------|
| BUG-037 | `_defaults.group_mapping` — ед.ч. vs мн.ч. | ✅ |
| BUG-043 | `/api/catalog/tree` → 500 | ✅ |
| BUG-045 | `/api/scanner/*` → 500 | ✅ |
| BUG-049…055 | 7 unprotected write-эндпоинтов | ✅ |
| BUG-057 | Scanner legacy mode by default | ✅ |
| BUG-059 | `POST tasks/create` 500 | ✅ |

### Средние

| ID | Проблема | Статус |
|----|----------|--------|
| BUG-038 | TTL не в env | ✅ |
| BUG-041 | Reuse refresh | ✅ |
| BUG-042 | `secure=False` hardcoded | ✅ |
| BUG-044 | `context_before` не маскирует домен | ✅ |
| BUG-058 | Manager не компенсирует `line_text_encrypted` | ✅ |
| BACKLOG-068 | Per-scanner keys (`scanner_id → key_id`) | 📋 v3.1.0 | 🟡 |

> Все 15 багов fix-спринта закрыты в v3.13.9. Непокрытый остаток тестов уровня E2E/мanual —
> регресс Блока 2 на собранном стеке (см. след. шаг).

---

## 🎯 Ключевые решения (обновлённые)

**Findings Refactor (v3.9.0-v3.12.0):**
- Findings = строка/фрагмент, гибрид masked + AES-256-GCM
- HMAC-SHA256 fingerprint
- **NEW: Scanner должен работать fail-fast без ключей** (BUG-057 fix)
- **NEW: Manager компенсирует `line_text_encrypted`** (BUG-058 fix)

**Аутентификация (Блок 2):**
- **NEW: `verify_token(token, expected_type)`** — access ≠ refresh (BUG-039)
- **NEW: RBAC системно** — `Depends(require_role(...))` во все write-эндпоинты (BUG-046…055)
- **NEW: Cookie `Secure`** — авто по HTTPS или env (BUG-042)
- **NEW: `jti` + `iat`** в JWT для blacklist'а (BUG-041 + TEST-NOTE-2.6a)

**Общие:**
- Scanner — на хосте, не в Docker
- Heartbeat-thread — выделенный daemon
- spaCy-модели `sm`

---

## 📁 Последние файлы (fix-спринт v3.13.9)

- `manager/src/auth/{jwt,router,middleware}.py` — BUG-039/041/042, JWT-резолв для RBAC
- `manager/src/api/{scanner,tasks,resources,webui,audit,permissions,catalog}.py` — BUG-043/045-055/058/059
- `manager/src/core/encryption.py`, `scanner/src/encryption.py`, `run_scanner.py` — BUG-044/057/058
- `manager/src/config.py`, `manager/config/config.json`, `docker-compose.yml`, `.env.example` — BUG-037/038/042
- `manager/src/db/models.py`, `manager/src/db/migrations/versions/004_resources_path_type_unique.py` — BUG-059
- `tests/unit/{test_rbac_guard,test_jwt_type,test_catalog_tree,test_tasks_create,test_encryption,test_scanner_findings}.py`
- `backups/dcap_pre_fix_sprint_20260919_183659.sql` (1.1 МБ)
- `prompts/reports/day_45_fix_sprint_report.md` (сформирован 20.09.2026)
- `prompts/archive/TZ_FIX_SPRINT.md` (ТЗ заархивировано)
- `.env`, `.env.example`, `webui/config.py`, `docker-compose.yml` — версия 3.13.9

---

**Актуально на:** 19.09.2026 (вечер)
**Версия:** v3.13.9
**Следующий шаг:** регресс Блока 2 на собранном стеке → релиз v3.0.0