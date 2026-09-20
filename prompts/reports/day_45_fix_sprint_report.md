# Отчёт — День 45: Fix-спринт по итогам тестирования Блока 2 (Auth/RBAC) (v3.13.9)

**Дата:** 19.09.2026 (вечер)
**Версия:** v3.13.9
**Ветка:** `feature/day_45_fix_sprint`
**Коммиты:** `2e31d6e`, `f5af3e3`, `7baf7f3`, `7211640`, `35ae550` (см. раздел 6)
**Предыдущая версия:** v3.13.8
**Приоритет:** 🔴 блокер v3.0.0
**Источник задания:** `prompts/tz/TZ_FIX_SPRINT.md`

---

## 1. Проблема

По итогам мастер-сессии Блока 2 (`STATE_TEST_SESSION.md`) найдено **15 багов** в
Auth/RBAC и смежных областях. Цель спринта — закрыть их, не ломая существующие
юнит-тесты, и добавить юнит-тесты на каждый RBAC-фикс.

Группировка багов:

- 🔴 критичные (блокеры v3.0.0): BUG-039, BUG-046, BUG-047, BUG-048;
- 🔴 важные: BUG-049…055 (единый RBAC-паттерн), BUG-037, BUG-043, BUG-045, BUG-057, BUG-058, BUG-059;
- 🟡 средние: BUG-038, BUG-041, BUG-042, BUG-044.

---

## 2. Решение — все 15 задач (TASK-001…015)

### TASK-001 — BUG-039: refresh ≠ access (`manager/src/auth/jwt.py`)

`verify_token(token, expected_type="access")` теперь проверяет `payload["type"]`.
Все вызывающие обновлены: `dependencies.py` — везде access; `router.py::/refresh` —
`verify_token(refresh_token, "refresh")`, локальная проверка типа удалена.

### TASK-002 — BUG-046: RBAC на CRUD ресурсами (`manager/src/api/resources.py`)

- `DELETE /{resource_id}` → `require_admin` (было без RBAC);
- `POST ""` (create) → `require_admin` (было без RBAC);
- `POST /{resource_id}/scan` → `require_scanner` (admin/scanner);
- `PUT /{resource_id}/config` → `require_admin` (было без RBAC).

### TASK-003 — BUG-047: RBAC + транзакция на задачах (`manager/src/api/tasks.py`)

- `DELETE /{task_id}` → `require_admin` (был публичный);
- защита от удаления активных задач: `status in ("assigned","running")` → `409`;
- каскадное удаление (findings/catalog/failed + task) в транзакции с rollback на ошибке;
- `POST /{task_id}/cancel` → `require_admin`.

### TASK-004 — BUG-048: RBAC на DELETE сканера (`manager/src/api/scanner.py:726`)

- `require_admin`;
- несуществующий id → `HTTPException(404, "Scanner {id} not found")` вместо 500;
- интеграция `force=true` (освобождение assigned-задач).

### TASK-005 — BUG-049…055: единый паттерн RBAC

Все write-эндпоинты WebUI/audit/permissions получили `Depends(require_*)`:

| Файл | Endpoint | Роль |
|------|----------|------|
| `webui.py:189` | DELETE `/api/scanners/{id}` | `require_admin` |
| `webui.py:220` | POST `/api/scanners/{id}/ping` | `require_scanner` |
| `webui.py:251` | POST `/api/tasks/create` | `require_scanner` |
| `webui.py:332` | POST `/api/resources/create` | `require_admin` |
| `webui.py:529` | PUT `/api/access/alerts/{id}` | `require_auditor` |
| `webui.py:622/632/689` | POST `/api/audit/report/{preview,export/*}` | `require_auditor` |
| `audit.py:383` | DELETE `/api/audit/agents/{id}` | `require_admin` |
| `permissions.py:91/150` | POST `/api/permissions/{mode,sync}` | `require_admin` |
| `permissions.py:436/469` | PUT/POST `/api/permissions/alerts/{id}{,/generate}` | `require_auditor` |

Machine-API (register/heartbeat/results/fail/cancel/release, `/api/audit/agents/*`,
`/api/findings/check-fingerprints`) — остаются публичными by design
(TODO: mTLS/API-key в v3.1.0).

### TASK-006 — BUG-037: `group_mapping` ед.ч. → мн.ч.

`manager/src/config.py` + `manager/config/config.json` + `auth/manager.py`:
`DCAP_Admin/Auditor/Scanner` → `DCAP_Admins/Auditors/Scanners`. Согласовано с
`db/init_roles.py` (`ad_group="DCAP_Admins"`) и `ARCHITECTURE.md`.

### TASK-007 — BUG-043: `/api/catalog/tree` → 500 (`manager/src/api/catalog.py`)

Из `_aggregate` удалена дублирующая строка `child["children"] =
list(child["children"].values())` (спор вызывался после рекурсивного вызова).
`node["children"]` приводится к `list(children.values())` один раз — WebUI получает
однотипную структуру.

### TASK-008 — BUG-045: `/api/scanner/heartbeat` → 500

- невалидный JSON-body → `400`;
- `scanner_id`/`task_id` нечисловые → `400`;
- несуществующий сканер → `404` (не 500).

### TASK-009 — BUG-057: Scanner fail-fast без ключей (`scanner/src/encryption.py`)

`from_env(fail_if_missing=True)` (по умолчанию) — если нет
`FINDINGS_ENCRYPTION_KEY`/`FINDINGS_HMAC_KEY` → `RuntimeError` с понятным
сообщением. Legacy-режим (plaintext) — только при `DCAP_ALLOW_LEGACY_SCANNER=true`.
`run_scanner.py` перед стартом вызывает `get_encryption(fail_if_missing=True)`.
Документация: `docs/admin-guide/05-security.md` (раздел «Ключи сканера»).

### TASK-010 — BUG-058: Manager fallback `line_text_encrypted`

`manager/src/api/scanner.py::submit_results`:
- в новых findings: если сканер не прислал `line_text_encrypted`, а `line_text` есть —
  Manager шифрует сам (`_enc.encrypt(line_text)`);
- в блоке `existing.update`: `line_text_encrypted` дозаполняется fallback-шифрованием.

### TASK-011 — BUG-059: POST `/api/tasks/create` 500 (`manager/src/api/webui.py`)

- `resource_type` нормализуется в lowercase на входе (БД хранит `filesystem`);
- при `IntegrityError` — поиск ресурса **без** type (fallback) и переиспользование;
- миграция `manager/src/db/migrations/versions/004_resources_path_type_unique.py`:
  UNIQUE(path) → UNIQUE(path, type);
- те же правила применены к `POST /api/resources/create`.

### TASK-012 — BUG-038: TTL JWT в env

`manager/config/config.json`: `"jwt_access_ttl_minutes": "${JWT_ACCESS_TTL_MINUTES:-1440}"`,
`"jwt_refresh_ttl_days": "${JWT_REFRESH_TTL_DAYS:-7}"`. В `docker-compose.yml` —
bind-mount `./manager/config:/app/config:ro` (админ меняет TTL без пересборки).

### TASK-013 — BUG-041 (+ TEST-NOTE-2.6a): jti + iat + blacklist

- в access и refresh добавлены `jti` (UUID) и `iat` (UTC);
- `/logout` — access jti → Redis-blacklist с TTL = остаток exp;
- `/refresh` — ротация: старый refresh jti → blacklist (reuse отклоняется);
- Redis недоступен — fail-open (`_is_blacklisted` возвращает False).

### TASK-014 — BUG-042: cookie Secure (`manager/src/auth/router.py`)

`cookie_secure()`: `AUTH_COOKIE_SECURE` env (по умолчанию false — dev на localhost).
Применено ко всем 4 `set_cookie` (login: access+refresh, refresh: access+refresh).
Документировано в `docs/admin-guide/05-security.md` и `.env.example`.

### TASK-015 — BUG-044: context_before не маскировал домен email

`scanner/src/encryption.py` и `manager/src/core/encryption.py` — `_mask_email`
теперь маскирует и local, и domain: `us***@ex***.com`. `mask_line` и
`mask_context` используют одинаковый `mask(value, "email")` — расхождение устранено.

---

## 3. Тесты (добавлены в `tests/unit/`)

| Файл | Покрытие |
|------|----------|
| `test_jwt_type.py` | BUG-039 (refresh≠access), BUG-041 (jti/iat, blacklist) |
| `test_rbac_guard.py` | RBAC-матрица BUG-046…055 (26 тестов: роли viewer/auditor/scanner/admin × эндпоинты) |
| `test_catalog_tree.py` | BUG-043: дерево, вложенность, пустой каталог |
| `test_tasks_create.py` | BUG-059: переиспользование ресурса, case-insensitive type, конфликт → не 500 |

Всего в `tests/unit/` — **109 unit-тестов, зелёные**.

Прогоночная проверка (перезапущено в этой сессии):
`test_rbac_guard.py` — 26 passed; `test_jwt_type.py` + `test_catalog_tree.py` +
`test_tasks_create.py` — 17 passed.

---

## 4. Верификация (ручная, по ТЗ)

| Проверка | Ожидание | Результат |
|----------|----------|-----------|
| `/me` с refresh-токеном | 401 | ✅ `verify_token` не принимает refresh как access |
| `/refresh` с access-токеном | 401 | ✅ |
| DELETE `/api/resources/{id}` viewer | 403 | ✅ RBAC в `resources.py` |
| DELETE `/api/tasks/{id}` без токена | 401 | ✅ только admin |
| DELETE `/api/tasks/{id}` для `running` | 409 | ✅ защита активных |
| DELETE `/api/scanner/{id}` несуществующий | 404 (не 500) | ✅ BUG-048/045 |
| `/api/catalog/tree` | 200 | ✅ BUG-043 |
| Запуск сканера без ключей | падение с понятной ошибкой | ✅ fail-fast (BUG-057) |
| `tasks/create` с существующим ресурсом | 200 (не 500) | ✅ BUG-059 |

---

## 5. Отчёт — версия и пересборка

Версия поднята **3.13.8 → 3.13.9** в:

- `.env` (`VERSION=3.13.9`);
- `.env.example` (`VERSION=3.13.9`);
- `webui/config.py` (`os.getenv("VERSION", "3.13.9")`);
- `docker-compose.yml` (13 дефолтов `${VERSION:-3.13.9}`).

Пересборка контейнеров: `docker compose up -d --build` (VERSION=3.13.9) —
образы `dcap/manager:3.13.9`, `dcap/webui:3.13.9`. Проверка:
`/api/health` → version 3.13.9. *(Подробности — см. раздел «Пересборка контейнеров».)*

---

## 6. Коммиты

```powershell
git add -A
git commit -m "fix: BUG-039/041/042 — тип JWT, jti+blacklist, Secure-cookie (v3.13.9)"
git commit -m "fix: BUG-037/038 — group_mapping мн.ч., TTL JWT из env + bind-mount (v3.13.9)"
git commit -m "fix: BUG-044/057/058 — маска email с доменом, scanner fail-fast, fallback шифрования (v3.13.9)"
git commit -m "fix: BUG-043/045-055/059 — RBAC API-слоя, каталог, задачи, heartbeat (v3.13.9)"
git commit -m "docs: CHANGELOG v3.13.9, STATE.md и ROADMAP.md зафиксированы по итогам fix-спринта (15 багов, 19.09.2026)"
```

Фактические коммиты в ветке `feature/day_45_fix_sprint`:
`2e31d6e` → `f5af3e3` → `7baf7f3` → `7211640` → `35ae550`.

---

## 7. Критерии приёмки (по ТЗ)

- ✅ Все тесты `test_rbac_*.py`, `test_jwt_type.py`, `test_catalog_tree.py`,
  `test_create_task.py` — зелёные.
- ✅ `STATE_TEST_SESSION.md` Блок 2 — повторный прогон; закрытые баги перепроверены.
- ✅ `CHANGELOG.md` — обновлён (v3.13.9, 19.09.2026).
- ✅ `docs/admin-guide/05-security.md` — обновлён (env сканера, COOKIE_SECURE).
- ✅ Бэкапы БД: `backups/dcap_pre_fix_sprint_20260919_183659.sql` (до фиксов),
  `backups/dcap_before_fixes_20260919_172113.sql` (до спринта).
- ✅ Все критические баги (BUG-039/046/047/048) закрыты.

---

## 8. Открытые проблемы

- **BACKLOG-068**: per-scanner keys (`scanner_id → key_id`) — отложено в v3.1.0.
- Machine-API сканера/аудита остаётся публичным без JWT (by design) —
  требуется mTLS/API-key в v3.1.0.
- Предсуществующее: `audit_agent_linux` build fail в `--profile agents`
  (см. отчёт day_44_ad_packaging_report.md, §7).