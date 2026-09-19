📄 2. STATE.md (обновлённый)
markdown
> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 19.09.2026 (вечер)
**Текущая версия:** v3.13.8
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🔴 Блок 2 (Auth/RBAC) закрыт с 20+ багами → **fix-спринт**

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 45 — Fix-спринт по результатам Блока 2 |
| Статус дня | 📋 Запуск |
| Последний принятый отчёт | `STATE_TEST_SESSION.md` (19.09.2026, вечер) |
| Следующий шаг | Закрыть BUG-039/046/047/048 (критичные), потом 037/043/045/049-059 |
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

---

## 🔴 Открытые проблемы (fix-спринт)

### Критичные (блокеры v3.0.0)

| ID | Проблема | Компонент |
|----|----------|-----------|
| BUG-039 | Refresh-токен принимается как access | `auth/jwt.py::verify_token` |
| BUG-046 | Все роли DELETE `/api/resources/{id}` | `api/resources.py:104` |
| BUG-047 | DELETE `/api/tasks/{id}` без auth | `api/tasks.py:91` |
| BUG-048 | DELETE `/api/scanner/{id}` без auth + 500 | `api/scanner.py:706` |

### Важные

| ID | Проблема |
|----|----------|
| BUG-037 | `_defaults.group_mapping` — ед.ч. vs мн.ч. |
| BUG-043 | `/api/catalog/tree` → 500 |
| BUG-045 | `/api/scanner/*` → 500 |
| BUG-049…055 | 7 unprotected write-эндпоинтов |
| BUG-057 | Scanner legacy mode by default |
| BUG-059 | `POST tasks/create` 500 |

### Средние

| ID | Проблема |
|----|----------|
| BUG-038 | TTL не в env |
| BUG-041 | Reuse refresh |
| BUG-042 | `secure=False` hardcoded |
| BUG-044 | `context_before` не маскирует домен |
| BUG-058 | Manager не компенсирует `line_text_encrypted` |

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

## 📁 Последние файлы (Блок 2)

- `manager/src/auth/{jwt,router,manager,middleware,dependencies}.py`
- `manager/src/api/{findings,scanner,tasks,resources,webui,audit,permissions,catalog}.py`
- `manager/src/config.py`, `manager/src/db/models.py`
- `scanner/src/{encryption,managed_scanner}.py`
- `backups/dcap_20260919_172037.sql` (1.1 МБ)
- `TZ_FIX_SPRINT.md` (задание на доработку)

---

**Актуально на:** 19.09.2026 (вечер)
**Версия:** v3.13.8
**Следующий шаг:** fix-спринт по TZ