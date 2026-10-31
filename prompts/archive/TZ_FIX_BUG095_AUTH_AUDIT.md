📄 ТЗ: BUG-095 — Аудит входов и управления пользователями не пишется в audit_logs
Файл: TZ_FIX_BUG095_AUTH_AUDIT.md
Версия: v3.13.23 → v3.13.24
Оценка: ~2 ч (реализация + тесты)
Дата: 27.09.2026
Приоритет: 🟡 важно (compliance 152-ФЗ / GDPR / PCI DSS)
Обнаружено: 27.09.2026, День 48.1, при диагностике BUG-094 (попутно)
Связано: ARCHITECTURE.md — раздел SIEM (auth_login / auth_failed, user_created, role_changed)

🎯 Цель
Добавить запись в audit_logs для событий:

auth_login — успешный вход (кто, когда, откуда).

auth_failed — неудачная попытка (кто, когда, откуда).

auth_logout — выход.

auth_refresh — обновление токена (опционально, для forensic).

user_created / user_updated / user_deleted — CRUD пользователей (Admin).

user_password_changed / user_password_reset — смена пароля.

role_assigned / role_revoked — назначение/снятие роли.

Обоснование (из ARCHITECTURE.md, раздел SIEM):

Источник	Событие	Severity
Audit	auth_login / auth_failed	info / medium
Audit	user_created / role_changed	medium
Сейчас эти события в audit_logs НЕ пишутся — подтверждено в отчёте Дня 48.1:

text
SELECT event_type, "user", event_source, COUNT(*) FROM audit_logs
GROUP BY event_type, "user", event_source ORDER BY event_type, COUNT(*) DESC;

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
auth_login, auth_failed, user_created, change_password, role_* — отсутствуют.

🚨 Влияние (compliance)
Требование	Как покрывается сейчас
152-ФЗ — кто и когда имел доступ к ПДн	❌ не отслеживается
GDPR — audit trail для доступа к данным	❌ не отслеживается
PCI DSS — 10.2.1–10.2.5 (логирование доступа)	❌ не отслеживается
SIEM-интеграция (BACKLOG-069/070)	❌ нечего отправлять
При расследовании инцидента невозможно установить:

Кто входил в систему.

Были ли попытки подбора пароля.

Кто создавал/удалял пользователей.

Кто менял роли.

🔧 Задача
TASK-061 — Аудит аутентификации (manager/src/auth/)
Файл: manager/src/auth/routes.py (или manager/src/api/auth.py — уточнить)

Добавить запись AuditLog для каждого события:

1. Успешный вход (auth_login)
Эндпоинт: POST /api/auth/login

python
from manager.src.db.models import AuditLog

def _log_auth_event(db, event_type, user, request, metadata=None):
    """BUG-095 (TASK-061, v3.13.24): аудит аутентификации."""
    try:
        log = AuditLog(
            event_type=event_type,
            event_source="api",
            user=user if isinstance(user, str) else user.username if user else None,
            user_sid=getattr(user, "domain_user", None) if not isinstance(user, str) else None,
            file_path="/api/auth",  # или request.url.path
            source_host=request.client.host if request.client else None,
            metadata_json=metadata or {},
            created_at=datetime.utcnow(),
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("Failed to log auth event %s: %s", event_type, e)
        db.rollback()
В роуте login (успех):

python
_log_auth_event(db, "auth_login", user, request, metadata={
    "action": "login_success",
    "auth_source": user.auth_source,  # local / ad
})
В роуте login (неудача):

python
_log_auth_event(db, "auth_failed", username, request, metadata={
    "action": "login_failed",
    "reason": "invalid_credentials",  # или "user_inactive", "user_not_found"
    "attempted_username": username,
})
⚠️ Важно: для auth_failed нельзя писать пароль или хеш. Только username + reason.

2. Выход (auth_logout)
Эндпоинт: POST /api/auth/logout

python
_log_auth_event(db, "auth_logout", user, request, metadata={
    "action": "logout",
    "jti": jti,  # из токена, если доступно
})
3. Обновление токена (auth_refresh)
Эндпоинт: POST /api/auth/refresh

python
_log_auth_event(db, "auth_refresh", user, request, metadata={
    "action": "token_refresh",
})
Опционально — можно не писать (шумно). Уточнить у архитектора. Рекомендация: писать, но с severity=low / в отдельной метрике.

TASK-062 — Аудит управления пользователями (manager/src/api/auth.py)
Файлы: manager/src/api/auth.py (CRUD пользователей), manager/src/auth/ (роли)

4. Создание пользователя (user_created)
Эндпоинт: POST /api/auth/users

python
_log_auth_event(db, "user_created", current_user, request, metadata={
    "action": "user_created",
    "target_user_id": new_user.id,
    "target_username": new_user.username,
    "auth_source": new_user.auth_source,
    "roles": [r.name for r in new_user.roles] if hasattr(new_user, "roles") else [],
})
5. Обновление пользователя (user_updated)
Эндпоинт: PUT /api/auth/users/{id}

python
_log_auth_event(db, "user_updated", current_user, request, metadata={
    "action": "user_updated",
    "target_user_id": target.id,
    "changes": {"is_active": ..., "email": ...},  # только изменённые поля
})
6. Удаление пользователя (user_deleted)
Эндпоинт: DELETE /api/auth/users/{id}

python
_log_auth_event(db, "user_deleted", current_user, request, metadata={
    "action": "user_deleted",
    "target_user_id": target.id,
    "target_username": target.username,
})
7. Смена пароля (user_password_changed)
Эндпоинт: POST /api/auth/users/{id}/reset-password (Admin) или POST /api/auth/change-password (сам)

python
_log_auth_event(db, "user_password_changed", current_user, request, metadata={
    "action": "password_changed",
    "target_user_id": target.id,
    "by_admin": current_user.id != target.id,  # сам или админ
})
⚠️ Не писать новый пароль — только факт смены.

8. Назначение / снятие роли (role_assigned / role_revoked)
Эндпоинты: POST /api/auth/users/{id}/roles / DELETE /api/auth/users/{id}/roles/{role_id}

python
_log_auth_event(db, "role_assigned", current_user, request, metadata={
    "action": "role_assigned",
    "target_user_id": target.id,
    "role": role.name,
})

_log_auth_event(db, "role_revoked", current_user, request, metadata={
    "action": "role_revoked",
    "target_user_id": target.id,
    "role": role.name,
})
TASK-063 — Rate-limit логина (auth_failed count)
Опционально: при N неудачных попыток входа — автоматически создавать алерт / повышать severity.

Может быть в v3.1.0 (SIEM-интеграция). Сейчас — только запись фактов.

🧪 Тесты
Unit — tests/unit/test_auth_audit_v31324.py
python
"""BUG-095 (TASK-061..062, v3.13.24): аудит auth и управления пользователями."""

class TestAuthAudit:
    def test_login_success_writes_auth_login(self):
        """POST /api/auth/login (успех) → audit_logs: event_type=auth_login."""
        pass

    def test_login_failure_writes_auth_failed(self):
        """POST /api/auth/login (неверный пароль) → event_type=auth_failed."""
        pass

    def test_login_failure_no_password_in_metadata(self):
        """В metadata для auth_failed НЕТ пароля/хеша."""
        pass

    def test_logout_writes_auth_logout(self):
        """POST /api/auth/logout → event_type=auth_logout."""
        pass

    def test_auth_failed_invalid_user(self):
        """Несуществующий username → auth_failed, metadata.reason=user_not_found."""
        pass

    def test_auth_failed_inactive_user(self):
        """is_active=False → auth_failed, metadata.reason=user_inactive."""
        pass

class TestUserManagementAudit:
    def test_user_created_writes_event(self):
        """POST /api/auth/users → event_type=user_created, metadata.target_user_id."""
        pass

    def test_user_updated_writes_event(self):
        """PUT /api/auth/users/{id} → event_type=user_updated."""
        pass

    def test_user_deleted_writes_event(self):
        """DELETE /api/auth/users/{id} → event_type=user_deleted."""
        pass

    def test_password_change_writes_event(self):
        """POST reset-password → event_type=user_password_changed (пароль НЕ в metadata)."""
        pass

    def test_role_assigned_writes_event(self):
        """POST roles → event_type=role_assigned, metadata.role."""
        pass

    def test_role_revoked_writes_event(self):
        """DELETE roles → event_type=role_revoked."""
        pass
E2E — tests/e2e/test_auth_audit_e2e.py
python
def test_full_auth_flow_audited(manager_url):
    """Логин → logout → проверить audit_logs через /api/audit."""
    pass

def test_failed_login_audited(manager_url):
    """Неудачный логин → audit_failed в audit_logs."""
    pass
Ожидание: +14 unit, +2 E2E. Итого unit 241 passed (227 + 14).

📊 Live-проверка
powershell
# 1. Успешный логин
$login = Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
  -ContentType "application/json" -Body '{"username":"admin","password":"admin123"}'

# 2. Неудачный логин
try {
  Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
    -ContentType "application/json" -Body '{"username":"admin","password":"wrong"}'
} catch { }

# 3. Logout
Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/logout `
  -Headers @{ Authorization = "Bearer $($login.access_token)" }

# 4. Создать пользователя
$body = @{ username="test_audit"; password="test123"; email="t@test.local"; roles=@("viewer") } | ConvertTo-Json
Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/users `
  -Headers @{ Authorization = "Bearer $($login.access_token)" } `
  -ContentType "application/json" -Body $body

# 5. Проверить audit_logs
sql
SELECT id, created_at, event_type, "user", metadata::text
FROM audit_logs
WHERE event_type IN ('auth_login','auth_failed','auth_logout','user_created','user_updated','user_deleted','user_password_changed','role_assigned','role_revoked')
ORDER BY created_at DESC LIMIT 20;
Ожидание:

auth_login — admin (успех) ✅

auth_failed — admin (неудача) ✅

auth_logout — admin ✅

user_created — admin (target_user_id, target_username) ✅

✅ Критерии приёмки
□ auth_login пишется при успешном входе
□ auth_failed пишется при неудаче (без пароля/хеша в metadata)
□ auth_logout пишется при выходе
□ auth_refresh — опционально (решить с архитектором)
□ user_created / user_updated / user_deleted — CRUD пользователей
□ user_password_changed / user_password_reset — смена пароля (без пароля)
□ role_assigned / role_revoked — управление ролями
□ pytest tests/unit/test_auth_audit_v31324.py -v — passed
□ pytest tests/e2e/test_auth_audit_e2e.py -v — passed
□ Полный unit: 241 passed (227 + 14)
□ Live: SQL-запрос показывает новые event_type
□ Обновлены STATE.md, ROADMAP.md, CHANGELOG.md, ARCHITECTURE.md
📝 Сводка правок
#	Файл	Действие	Задача
1	manager/src/auth/routes.py (или api/auth.py)	Запись AuditLog для login/logout/refresh	TASK-061
2	manager/src/api/auth.py	Запись AuditLog для CRUD пользователей	TASK-062
3	manager/src/auth/routes.py (roles)	Запись AuditLog для ролей	TASK-062
4	manager/src/auth/utils.py (или новый)	Хелпер _log_auth_event	TASK-061
5	tests/unit/test_auth_audit_v31324.py	Создать (14 тестов)	TASK-061..062
6	tests/e2e/test_auth_audit_e2e.py	Создать (2 теста)	TASK-061
7	docker-compose.yml	VERSION → 3.13.24	релиз
8	STATE.md, ROADMAP.md, CHANGELOG.md, ARCHITECTURE.md	BUG-095 → ✅	док
⚠️ Безопасность
Не писать в metadata_json:

Пароли (ни в каком виде).

Хеши паролей.

Токены (полные).

JWT secrets.

Персональные данные сверх необходимого.

Писать только:

username (не пароль).

reason (invalid_credentials / user_inactive / user_not_found).

target_user_id / target_username.

changes — только названия полей (не значения, если PII).

🎯 После закрытия
BUG-095 → ✅ v3.13.24

SIEM-интеграция (BACKLOG-069/070) → теперь будет что экспортировать

Блок 5 → продолжить с п.5 (PATCH status)

📌 Открытые вопросы к архитектору
auth_refresh — писать или нет? (шумно — refresh каждые 15 мин)

auth_failed — писать в отдельную таблицу или в audit_logs? (высокий объём)

Ретенция — auth_failed может быть много → отдельная политика retention?

Интеграция с rate-limit — при N неудач → alert (в этом ТЗ или отдельно)?

file_path для auth-событий — /api/auth или пусто?

Рекомендация:

auth_refresh — не писать (шумно; только login/logout).

auth_failed — в audit_logs (единая точка).

Ретенция — по общим правилам.

Rate-limit alert — отдельная задача (v3.1.0, SIEM).

file_path — /api/auth/login и т.п. (точный URL).

Автор ТЗ: архитектор
Дата: 27.09.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.24, BUG-095 → ✅