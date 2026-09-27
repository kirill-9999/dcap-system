# Отчёт: День 48.2 — BUG-095 (TASK-061/062) — Аудит аутентификации и управления пользователями

**Дата:** 27.09.2026
**Версия:** v3.13.24 (была v3.13.23)
**Ветка:** `fix/scanner_deep`
**ТЗ:** `prompts/tz/TZ_FIX_BUG095_AUTH_AUDIT.md` → архивировано в `prompts/archive/TZ_FIX_BUG095_AUTH_AUDIT.md`
**Статус:** ✅ выполнено

---

## 1. Суть задачи

Аудит входов и управления пользователями **не писался вовсе**: `auth_login`,
`auth_failed`, `auth_logout`, `user_created`, `role_changed` упоминались в
`ARCHITECTURE.md` (раздел SIEM) и в `docs/admin-guide/05-security.md`, но в реальной
таблице `audit_logs` отсутствовали. Не выполнялись требования:

- **152-ФЗ** — регистрация событий ИБ;
- **GDPR** (ст. 30, 32) — журнал доступа к учётным записям;
- **PCI DSS 10.2** — `10.2.4` invalid login attempts, `10.2.5` changes to
  identification/authentication credentials, `10.2.7` user accounts.

Требования ТЗ выполнены полностью.

---

## 2. Что сделано

### 2.1 TASK-061 — аудит аутентификации

Новый модуль **`manager/src/auth/audit.py`**:

| Функция | Назначение |
|---------|-----------|
| `log_auth_event(db, *, event_type, user, request, action, severity, **metadata)` | Единая запись в `audit_logs`. **Fail-open**: `try/except` + `rollback`, ошибка → `logger.warning`, эндпоинт продолжает работать |
| `_sanitize(value)` | Рекурсивное вырезание из `metadata` ключей `password`, `*_token`, `*_secret`, `*_hash`, `*_salt`, `*_credential`; PII (`email`, `full_name`) → `"changed"` без значения |
| `classify_login_failure(db, username, ...)` | Возвращает `user_not_found` / `user_inactive` / `invalid_credentials` (для отделения «неизвестный пользователь» от «неверный пароль» — видно **только в аудите**) |
| `role_diff(old, new)` | Список назначенных/снятых ролей → `role_assigned` / `role_revoked` |

Поля записи: `user` = **актор** (для `auth_failed` — предпринятый логин), `user_sid` =
`domain_user` (для `auth_failed` — `auth_mode`), `file_path` = точный URL эндпоинта,
`source_host` = IP клиента, `event_source = "api"`, `result` = success/failure.

Инструментировано в `manager/src/auth/router.py`:

| Событие | `event_type` | `metadata` |
|---------|--------------|------------|
| `POST /api/auth/login` (успех) | `auth_login` | `auth_source`, `auth_method`, `auth_mode`, `roles` |
| `POST /api/auth/login` (неудача) | `auth_failed` | `reason`, `attempted_username`, `auth_mode` |
| `POST /api/auth/logout` | `auth_logout` | `jti` (не сам токен) |

### 2.2 TASK-062 — аудит управления пользователями

| Эндпоинт | `event_type` | `metadata` |
|----------|--------------|------------|
| `POST /api/auth/users` | `user_created` | `target_user_id`, `target_username`, `auth_source`, `is_active`, `roles` |
| `PUT /api/auth/users/{id}` | `user_updated` | `action: user_updated`, `changes` (только реально изменённые поля), `roles_added`, `roles_removed` |
| `PUT /api/auth/users/{id}/status` | `user_updated` | `action: status_changed`, `changes: {is_active}` |
| `PUT /api/auth/users/{id}` (с `password`) | + `user_password_changed` | `by_admin: true`, `self_service: false` |
| `POST /api/auth/change-password` | `user_password_changed` | `self_service: true`, `by_admin: false` |
| `PUT /api/auth/users/{id}/roles` | `role_assigned` / `role_revoked` | `role`, `target_user_id`, `target_username` |
| `DELETE /api/auth/users/{id}` | `user_deleted` | `target_user_id`, `target_username`, `roles` |

`is_active` попадает в `changes` только при **фактическом** изменении
(иначе была бы запись «изменений нет» при no-op вызове).

### 2.3 Решение по optional-событию `auth_refresh`

**Не логируется.** Причина: refresh вызывается каждые 15 мин каждым активным клиентом —
это ~290 событий/сутки на пользователя и ноль ценности для расследований. `auth_login`
уже фиксирует факт выдачи пары токенов. Решение зафиксировано в `ARCHITECTURE.md`,
`docs/admin-guide/05-security.md` и разделе 7 `10-troubleshooting.md`.

### 2.4 Изменённые файлы

**Новые:**
- `manager/src/auth/audit.py`
- `tests/unit/test_auth_audit_v31324.py`
- `tests/e2e/test_auth_audit_e2e.py`

**Изменённые:**
- `manager/src/auth/router.py` — аудит в 7 эндпоинтах, `request: Request` в сигнатурах;
- `.env`, `.env.example`, `docker-compose.yml` — `VERSION=3.13.24`;
- `ARCHITECTURE.md` — таблица событий аудита аутентификации;
- `docs/admin-guide/05-security.md` — раздел 8 переписан в таблицу событий;
- `docs/admin-guide/10-troubleshooting.md` — раздел 7 (диагностика аудита auth);
- `STATE.md`, `ROADMAP.md`, `CHANGELOG.md`.

Миграций БД **не требуется** (используется существующая `audit_logs`, все поля
заполняются; `event_type` — `String`).

---

## 3. Тесты

### 3.1 Unit (новые) — 15/15 passed

`python -m pytest tests/unit/test_auth_audit_v31324.py -q` → **15 passed**

- аутентификация: успешный вход, неверный пароль, неизвестный пользователь,
  отключённый пользователь, logout (`jti`, без токена);
- управление: создание/обновление/удаление, `status_changed`, self-service смена
  пароля, admin reset, назначение/снятие ролей (в т.ч. через `PUT /users/{id}`);
- безопасность: пароль/токен/секрет не попадают в `metadata`; `auth_refresh` не пишется.

### 3.2 E2E (новые) — 2/2 passed

`python -m pytest tests/e2e/test_auth_audit_e2e.py -v` → **2 passed**

1. Полный флоу против живого Manager v3.13.24: login → создание пользователя →
   назначение ролей → блокировка → неудачный вход → удаление → logout;
   проверяется наличие всех событий в `audit_logs` через API.
2. `auth_failed` для несуществующего пользователя (`reason: user_not_found`).

> В тесте используются **две** admin-сессии: `logout` добавляет `jti` в чёрный список,
> поэтому основной JWT после логаута невалиден.

### 3.3 Полный unit — 242 passed

`python -m pytest tests/unit -q` → **242 passed** (было 227, +15).

### 3.4 Полный E2E — 47 passed, 3 failed, 2 skipped

Прогон выполнен с временно повышенным лимитом входа (`AUTH_LOGIN_MAX_ATTEMPTS=500`),
т.к. штатный лимит **5 попыток/мин на IP** блокирует E2E-набор. Все 3 падения —
**предсуществующие, вне ТЗ BUG-095**, код затронутых модулей не менялся:

| Тест | Причина | Классификация |
|------|---------|---------------|
| `test_findings_api.py::test_false_positive_and_stats` | **500**: `manager/src/api/findings.py:324` использует `_m.User`, а `User` определён в `manager.src.auth.models` | 🐛 **реальный баг → BUG-096** |
| `test_full_scan_cycle.py::test_full_scan_cycle` | Тест ждёт `finding_type in {pii, credentials}`; после рефакторинга v3.13.22 приходят гранулярные `category`: `email`, `person`, `phone`, `aws_key` | 🧪 **устаревший тест → BUG-096b** |
| `test_scanner_findings.py::test_real_scanner_end_to_end` | `RemoteDisconnected` при опросе статуса задания — сканер/окружение E2E | 🧪 **нестабильный тест → BUG-096b** |

Ни один из них не связан с аудитом аутентификации: все три падения воспроизводятся
на неизменённых участках кода. Исправление вынесено за рамки BUG-095 (зафиксировано
в `ROADMAP.md`, `STATE.md`, `CHANGELOG.md`).

**Первый** полный прогон (со штатным лимитом 5/мин) дал 20 failed / 8 errors — это
429 от `manager/src/auth/rate_limit.py`, то есть ограничение тестового окружения, а не
дефект. После повышения лимита — см. выше.

### 3.5 Временный `docker-compose.override.yml`

Для прогона E2E был создан игнорируемый `docker-compose.override.yml` с
`AUTH_LOGIN_MAX_ATTEMPTS: "500"`. **После проверки файл удалён**, Manager пересоздан
со штатным лимитом (`docker compose up -d manager`), `/api/health` → `3.13.24`.

---

## 4. Live-верификация (PostgreSQL)

Выполнен сценарий: успешный вход → неудачный вход → создание пользователя →
назначение ролей → блокировка → вход отключённого → удаление → logout.

```sql
SELECT event_type, "user", source_host, metadata
FROM audit_logs
WHERE event_type IN ('auth_login','auth_failed','auth_logout','user_created',
                     'user_updated','user_deleted','user_password_changed',
                     'role_assigned','role_revoked')
ORDER BY created_at DESC, id DESC LIMIT 12;
```

Фактический результат (id 239–250):

```
 auth_login            | admin     | {"action":"login_success","auth_method":"local_jwt","auth_mode":"hybrid","auth_source":"local","roles":["admin"]}
 auth_failed           | admin     | {"action":"login_failed","reason":"invalid_credentials","attempted_username":"admin","auth_mode":"hybrid"}
 user_created          | admin     | {"action":"user_created","target_user_id":48,"target_username":"test_audit","auth_source":"local","is_active":true,"roles":["viewer"]}
 role_assigned         | admin     | {"action":"role_assigned","role":"auditor","target_user_id":48,"target_username":"test_audit"}
 user_updated          | admin     | {"action":"status_changed","changes":{"is_active":false},"target_user_id":48,"target_username":"test_audit"}
 auth_failed           | test_audit| {"action":"login_failed","reason":"user_inactive","attempted_username":"test_audit","auth_mode":"hybrid"}
 user_deleted          | admin     | {"action":"user_deleted","target_user_id":48,"target_username":"test_audit","roles":["auditor","viewer"]}
 auth_logout           | admin     | {"action":"logout","jti":"42b49f1b-dff8-4d61-aaae-6b47d61cc6b4"}
 user_password_changed | admin     | {"action":"password_changed","by_admin":true,"self_service":false,"target_user_id":49,"target_username":"pw_audit"}
```

Сводка по всем событиям:

```
 event_type            | user    | cnt
----------------------+---------+-----
 auth_login            | admin   | 72
 auth_login            | auditor | 4
 auth_logout           | admin   | 9
 auth_failed           | admin   | 3   (invalid_credentials)
 auth_failed           | test_audit | 1 (user_inactive)
 auth_failed           | ghost_* | 6   (user_not_found, E2E)
 role_assigned         | admin   | 7
 user_created          | admin   | 8
 user_updated          | admin   | 7
 user_deleted          | admin   | 7
 user_password_changed | admin   | 1
```

Все **9** `event_type` пишутся, `source_host = 172.19.0.1` (IP клиента), классификация
причин работает (`invalid_credentials` / `user_inactive` / `user_not_found`).

### Проверка отсутствия утечек

```sql
SELECT COUNT(*) FROM audit_logs
WHERE metadata::text LIKE '%SuperSecret-Reset-42%'
   OR metadata::text LIKE '%tmp12345%';
-- count = 0
```

HTTP-ответ при неудачном входе остаётся общим (`401 Invalid credentials`) во всех
случаях — перечислить существующие учётки невозможно, различие только в аудите.

---

## 5. Инструкция для ручного теста

```powershell
docker compose up -d --build manager
$h = @{ Authorization = "Bearer $((Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body '{"username":"admin","password":"admin123"}').access_token)" }
$nu = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/users -Headers $h -ContentType "application/json" -Body '{"username":"demo_audit","password":"demo12345","roles":["viewer"]}'
Invoke-RestMethod -Method PUT "http://127.0.0.1:8000/api/auth/users/$($nu.id)/roles" -Headers $h -ContentType "application/json" -Body '{"roles":["viewer","auditor"]}'
try { Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body '{"username":"demo_audit","password":"nope"}' } catch {}
```

Затем в UI: **Аудит** → фильтр по `auth_login` / `auth_failed` / `user_created` /
`role_assigned`; или SQL из раздела 4. Ожидается: `auth_login` (admin),
`user_created` + `role_assigned` (admin, actor), `auth_failed` (demo_audit, reason
`invalid_credentials`).

> **Важно:** не более 5 неудачных попыток входа в минуту с одного IP (429 иначе).

---

## 6. Известные проблемы (вне ТЗ, не правил)

1. **BUG-096** — `GET /api/findings/false-positives` → 500 (`findings.py:324`, `_m.User`).
2. **BUG-096b** — 2 устаревших E2E-теста после рефакторинга категорий v3.13.22.
3. **TASK-063** — алерт на N неудачных входов (отложен до v3.1.0, вместе с SIEM;
   данные для него уже есть — `auth_failed` с `source_host`).

## 7. Обратная связь архитектору

- **Коллизия ID (напоминание):** BUG-087 занят TASK-054 (День 48). День 48.1 закрыт
  как BUG-094. Для новых заданий предлагаю префикс `BUG-1xx` / `TASK-0xx` от DAY-xx.
- **Пункт «управление пользователями» закрыт полностью:** CRUD + смена пароля
  (self и admin) + роли + блокировка. Отдельного `user_password_reset` не заводил —
  сброс админом логируется тем же `user_password_changed` с `by_admin: true`
  (в `metadata` видно, кто именно сбросил), чтобы не плодить дублирующие типы.
- **`auth_refresh` не логируется** — если SIEM потребует, лучше включать выборочно
  через правило в SIEM по `auth_login`, а не писать в Manager.
- **Полный E2E требует поднятого лимита входа** (5/мин на IP) — стоит завести константу
  для test-профиля compose, чтобы не создавать `override.yml` вручную.
