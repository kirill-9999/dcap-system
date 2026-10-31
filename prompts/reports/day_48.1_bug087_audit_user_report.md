# День 48.1 — BUG-087: «audit_logs.user = dcap» — диагностика и ложное срабатывание (v3.13.23)

**Дата:** 27.09.2026
**ТЗ:** `TZ_FIX_BUG087_AUDIT_USER.md` (TASK-060)
**Версия:** v3.13.22 → **v3.13.23**
**Итог:** 🔴 **баг НЕ подтвердился. Код приложения корректен, изменений не требует.**
**Тесты:** 7 unit + 3 E2E (новые), полный unit-набор **227 passed** (было 220)

---

## 1. Краткий вывод

Призрак в приложении нет. `audit_logs.user` содержит реального пользователя
(`auditor`, `admin`) во всех записях. Значение `dcap` — это **имя роли БД
(`CURRENT_USER`)**, которое возвращал диагностический SQL, потому что колонка
`user` была указана **без кавычек**, а в PostgreSQL `user` — зарезервированное
слово.

Правильный запрос: `SELECT "user" FROM audit_logs` → `auditor`.
Ошибочный запрос: `SELECT user FROM audit_logs` → `dcap` (= `current_user`).

---

## 2. Корень (точное место)

**Не в коде.** Ошибочна диагностика (команда из ТЗ и её доказательная база):

```sql
-- ТЗ, шаг «Доказательная база»:
SELECT id, created_at, user, metadata::text
FROM audit_logs WHERE event_type = 'finding_reveal' ...;
--                    ^^^ без кавычек -> CURRENT_USER -> "dcap"
```

PostgreSQL: `user` ≡ `current_user` ≡ `session_user` — не столбец.
Имя роли БД в этом стенде — `dcap` (совпадает с пользователем ОС/контейнера и
`POSTGRES_USER` в `.env`), поэтому подмена выглядела правдоподобно.

Корректно:

```sql
SELECT id, created_at, "user", metadata::text FROM audit_logs ...
```

---

## 3. Проверка гипотез ТЗ (H1–H7)

| # | Гипотеза | Результат |
|---|----------|-----------|
| H1 | SQLAlchemy `event.listens_for` / `before_insert` | ❌ не найдено (рекурсивный grep по `manager/**/*.py`) |
| H2 | PostgreSQL DEFAULT / TRIGGER | ❌ нет: `pg_attrdef` пусто (в т.ч. по партициям), `pg_trigger` пусто, `pg_rules` пусто |
| H3 | Middleware подменяет `request.state.user` | ❌ `manager/src/auth/middleware.py:212-215` — `request.state.user` = реальный `User` из БД по `user_id` из JWT |
| H4 | `require_auditor` возвращает service-user | ❌ `dependencies.py:8-16,24-40` — возвращает `request.state.user` без подмен |
| H5 | Дублирующее создание `AuditLog` | ❌ для `finding_reveal` единственный писатель — `_log_reveal` (`findings.py:753`) |
| H6 | `_log_reveal` вызывается с другим user | ❌ вызов один: `findings.py:740`, аргумент — тот же `user`, что и в `revealed_by` |
| H7 | Hook на `commit()` | ❌ listener'ов нет; `session.py` — чистый `create_engine`/`sessionmaker` |
| — | hardcoded `"dcap"` в Manager | ❌ рекурсивный grep: только `dcap.db`, `DCAP_*` (AD-группы), `dcap_http_*` (метрики) |

**Решающая проверка** — значения внутри `_log_reveal` (временный `logger.warning`,
потом удалён):

```
REVEAL-DEBUG    type(user)=User id=35 username='auditor'
LOGREVEAL-DEBUG user_arg=<manager.src.auth.models.User object ...> username_attr='auditor'
```

**Решающая проверка №2** — фактический SQL (`ALTER SYSTEM SET log_statement='all'`
на 1 запрос, затем сброшено):

```sql
INSERT INTO audit_logs (agent_id, event_type, event_source, "user", user_sid,
                        file_path, old_path, source_host, metadata, created_at)
VALUES (NULL, 'finding_reveal', 'api', 'auditor', NULL,
        'C:\test\scanner_clean\pii\emails_clean.txt', NULL, '172.19.0.1',
        '{"finding_id": 1517, "category": "email", "finding_type": "pii",
          "action": "finding_revealed"}'::JSON, '2026-09-27T08:01:35.838562'::timestamp)
RETURNING audit_logs.id
```

В INSERT стоит `'auditor'`. Подмены нет ни в Python, ни в SQL, ни в БД.

---

## 4. Live-доказательство (после live-reveal под auditor, v3.13.23)

```sql
-- с кавычками: значение колонки
SELECT id, created_at, "user" AS audit_user
FROM audit_logs WHERE event_type='finding_reveal' ORDER BY id DESC LIMIT 2;
```
```
 id |         created_at         | event_type     | audit_user
----+---------------------------+----------------+------------
 76 | 2026-09-27 08:12:12.830748 | finding_reveal | auditor
 75 | 2026-09-27 08:06:06.774955 | finding_reveal | auditor
```

```sql
-- без кавычек: ловушка ТЗ (= CURRENT_USER)
SELECT id, user AS audit_user_unquoted, current_user AS db_role
FROM audit_logs WHERE event_type='finding_reveal' ORDER BY id DESC LIMIT 1;
```
```
 id | audit_user_unquoted | db_role
----+---------------------+---------
 76 | dcap                | dcap
```

API (регрессия не сломалась): `revealed_by = auditor`, `POST .../reveal` → 200.

---

## 5. Проверка других эндпоинтов (п. «Проверка других эндпоинтов» ТЗ)

```sql
SELECT event_type, "user", event_source, COUNT(*) FROM audit_logs
GROUP BY event_type, "user", event_source ORDER BY event_type, COUNT(*) DESC;
```
```
     event_type     |    "user"    | event_source | count
-------------------+--------------+--------------+-------
 finding_reveal    | auditor      | api          |    18
 finding_reveal    | admin        | api          |    13
 findings_exported | admin        | api          |    11
 findings_exported | auditor      | api          |     4
 fragment_accessed | admin        | api          |    11
 fragment_accessed | auditor      | api          |     9
 raw_test          | RAW_USER_X   | test         |     1
 test_event        | TEST_USER_ADMIN | test      |     1
 test_event_3      | TEST_USER_3  | test         |     1
 test_event_4      | TEST_USER_4  | test         |     1
```

- `finding_reveal`, `findings_exported`, `fragment_accessed` — **реальные пользователи**, проблемы нет.
- `auth_login` и `user_created` в `audit_logs` **не пишутся вообще** (в таблице
  нет ни одного `AuditLog` от `manager/src/auth/*` — единственные писатели:
  `api/findings.py` (3 шт.) и `api/audit.py::ingest_audit_events` для агентов).
  Это отдельный пробел покрытия аудита входа, **не входил в ТЗ** → кандидат
  в бэклог (см. §7).

---

## 6. Что изменено в репозитории

Фикс кода **не требуется** (баг ложный). Изменения — регрессионная защита,
тесты и документация:

| Файл | Изменение |
|------|-----------|
| `tests/unit/test_audit_reveal_user_v31323.py` | **новый, 7 тестов**: reveal → `audit_logs.user` == `revealed_by`; `!= "dcap"`; admin vs auditor дают разные значения; `findings_exported`; `fragment_accessed` (встроенный фрагмент); имя колонки `user`; отсутствие Python-side `default` |
| `tests/e2e/test_audit_reveal_user_e2e.py` | **новый, 3 теста**: live-reveal → `/api/audit` отдаёт `user == "auditor"`; стабильность при 3 вызовах; прямая SQL-проверка `SELECT "user", user` — колонка ≠ `CURRENT_USER` |
| `docs/admin-guide/10-troubleshooting.md` | новый раздел 6: ловушка `user`/`CURRENT_USER`, правильный SQL |
| `docker-compose.yml`, `.env.example` | версия 3.13.22 → 3.13.23 |
| `STATE.md`, `ROADMAP.md`, `CHANGELOG.md` | состояние, бэклог, релиз |

Код `manager/src/api/findings.py` — **без изменений** (временная отладка
удалена, `git diff` чист).

---

## 7. Обратная связь архитектору

1. **Коллизия ID.** ТЗ называет это «BUG-087», но BUG-087 уже занят в День 48
   (TASK-054, прокси-заголовки WebUI). В ROADMAP записано как **BUG-094**
   (диагностика, ложное срабатывание), чтобы не плодить два BUG-087.
2. **Типовой источник ложных багов:** ручные SQL-запросы по `audit_logs`
   без кавычек вокруг `user`. Стоит закрепить в гайде (сделано, §6
   troubleshooting) и использовать `SELECT "user"` во всех будущих ТЗ.
3. **Пробел аудита (вне ТЗ):** `auth_login`, `user_created`, `change_password`
   не пишутся в `audit_logs` — для 152-ФЗ/GDPR (кто и когда входил) это
   существенно. Кандидат в бэклог: `BUG-095 (TASK-061)`.
4. **Партиционирование + `ORDER BY id`:** `audit_logs` разбита по месяцам
   (`RANGE (created_at)`), PK — `(created_at, id)`. Диагностические запросы
   вида `ORDER BY id DESC` работают, но «последняя запись» корректнее брать
   как `ORDER BY created_at DESC, id DESC`.

---

## 8. Критерии приёмки

- [x] Диагностика завершена — корень найден и задокументирован
- [x] Фикс: код корректен, правки не требуются; ловушка описана в документации
- [x] `pytest tests/unit/test_audit_reveal_user_v31323.py -v` → **7 passed**
- [x] `pytest tests/e2e/test_audit_reveal_user_e2e.py -v` → **3 passed**
- [x] Полный unit-набор: **227 passed**
- [x] Live: `revealed_by = auditor`, `SELECT "user"` → `auditor` (id 75, 76)
- [x] `revealed_by` в API по-прежнему `auditor` (регрессия не сломалась)
- [x] Обновлены `STATE.md`, `ROADMAP.md`, `CHANGELOG.md`
- [x] Версия 3.13.23 в `docker-compose.yml` / `.env.example` / `.env`,
      контейнеры пересобраны: manager/webui/celery — `3.13.23`, healthy

---

## 9. Команда для коммита

```powershell
git add tests/unit/test_audit_reveal_user_v31323.py tests/e2e/test_audit_reveal_user_e2e.py `
        docs/admin-guide/10-troubleshooting.md docker-compose.yml .env.example
git commit -m "test: День 48.1 — BUG-087 (аудит reveal): баг ложный, регрессия закрыта (v3.13.23)"
```
