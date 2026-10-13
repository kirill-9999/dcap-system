# ТЗ 53.4a-доп3 — Hotfix: Backend-critical

**Дата:** 12.10.2026
**Версия:** v3.13.39
**Приоритет:** 🔴🔴 блокер релиза v3.0.0
**Длительность:** 3–5 дней
**Источник:** мастер-сессия v3.13.38

---

## 🎯 Цель

Закрыть **критичные** баги: compliance (152-ФЗ, PCI DSS), security (RBAC),
data integrity (смена пароля, аудит).

---

## 📋 Задачи (9 BUG)

### 🔴 BUG-201 — Смена пароля не работает

**Симптомы:**
- `POST /api/auth/change-password` → **200** + `{"status":"ok"}`.
- **Пароль в БД НЕ меняется.**
- Логин **старым** паролем — работает.

**Причина:** отсутствует `db.commit()` после `user.password_hash = hash_password(...)`.

**Файл:** `manager/src/auth/router.py::change_password`

**Фикс:**
```python
@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(404, "User not found")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(401, "Current password is incorrect")

    if payload.new_password != payload.confirm_password:
        raise HTTPException(400, "Passwords do not match")

    if len(payload.new_password) < 8:
        raise HTTPException(400, "Password too short")

    user.password_hash = hash_password(payload.new_password)
    db.commit()  # ← КРИТИЧНО
    db.refresh(user)

    _log_audit(db, "user_password_changed",
               user_id=user.id,
               metadata={"by_admin": False, "self_service": True})
    db.commit()

    return {"status": "ok", "message": "Password changed"}
Тесты:

test_change_password_updates_hash — login → change → logout → login новым ✅

test_change_password_wrong_current → 401

test_change_password_mismatch_confirm → 400

test_change_password_writes_audit_after_commit

Очистка: удалить ложные user_password_changed (4+ записей) из audit_logs.

🔴🔴 BUG-202 — Audit-log пишется при провале транзакции
Симптомы: _log_audit пишется до db.commit(). При откате — аудит остаётся,
изменения — нет.

Файл: manager/src/api/audit_helper.py (или _log_audit в разных модулях)

Фикс: единый контекст-менеджер.

python
@contextmanager
def with_audit(db: Session, event_type: str, **kwargs):
    try:
        yield
        _log_audit(db, event_type=event_type, **kwargs)
        db.commit()
    except Exception:
        db.rollback()
        raise
Проверить во всех местах: auth/router.py, api/findings.py (BUG-101),
api/resources.py.

Тест: test_audit_not_written_on_rollback.

🔴🔴 BUG-214 — /api/audit доступен viewer/scanner
Симптомы: GET /api/audit, /api/audit/stats → 200 для viewer / scanner.

Файл: manager/src/api/audit.py

Фикс:

python
from ..auth.dependencies import require_auditor

@router.get("", dependencies=[Depends(require_auditor)])
async def list_audit(...): ...

@router.get("/stats", dependencies=[Depends(require_auditor)])
async def audit_stats(...): ...
Проверить require_auditor (TEST-NOTE-9.17 — require_viewer = require_auth).

Тесты:

test_audit_requires_auditor_viewer → 403

test_audit_requires_auditor_scanner → 403

test_audit_allows_auditor → 200

test_audit_allows_admin → 200

🔴🔴 BUG-223 — GET /api/audit/{id} — не существует
Симптомы: GET /api/audit/1 → 404. metadata_json недоступен.

Файл: manager/src/api/audit.py

Фикс:

python
@router.get("/{log_id}", response_model=AuditLogDetail,
            dependencies=[Depends(require_auditor)])
async def get_audit_log(log_id: int, db: Session = Depends(get_db)):
    entry = db.query(AuditLog).filter(AuditLog.id == log_id).first()
    if not entry:
        raise HTTPException(404, "Audit log not found")
    return entry
Схема: manager/src/api/schemas_audit.py::AuditLogDetail — с metadata_json.

Тесты: test_get_audit_log_by_id, test_get_audit_log_not_found.

🔴 BUG-181 — Нет аудита ролей
Симптомы: POST/PUT/DELETE /api/auth/roles/{id} не логируются.

Файл: manager/src/auth/router.py

Фикс:

python
@router.post("/roles")
async def create_role(...):
    role = Role(...)
    db.add(role)
    with with_audit(db, "role_created",
                    role_id=role.id, role_name=role.name, ad_group=role.ad_group):
        db.flush()
        db.commit()
    return role

@router.put("/roles/{role_id}")
async def update_role(...):
    with with_audit(db, "role_updated",
                    role_id=role_id, changes=changes):
        db.commit()

@router.delete("/roles/{role_id}")
async def delete_role(...):
    with with_audit(db, "role_deleted",
                    role_id=role_id, role_name=role.name):
        db.delete(role)
        db.commit()
Тест: test_role_crud_writes_audit.

🔴 BUG-168 — Системные роли редактируются
Симптомы: PUT /api/auth/roles/{id} позволяет менять name и ad_group
у admin / auditor / scanner / viewer → RBAC ломается.

Файл: manager/src/auth/router.py

Фикс:

python
SYSTEM_ROLES = {"admin", "auditor", "scanner", "viewer"}

@router.put("/roles/{role_id}")
async def update_role(role_id: int, payload: RoleUpdate, ...):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404)

    if role.name in SYSTEM_ROLES:
        if payload.name and payload.name != role.name:
            raise HTTPException(400, "Cannot rename system role")
        if payload.ad_group and payload.ad_group != role.ad_group:
            raise HTTPException(400, "Cannot change AD group for system role")
        if payload.description is not None:
            role.description = payload.description
    else:
        role.name = payload.name or role.name
        role.description = payload.description or role.description
        role.ad_group = payload.ad_group or role.ad_group

    db.commit()
    return role
Тесты:

test_system_role_name_immutable

test_system_role_ad_group_immutable

test_custom_role_editable

🔴 BUG-142 — Dashboard KPI «Ресурсов» = 0
Симптомы: dashboard.js ждёт s.total_resources, но /api/audit/stats
его не возвращает.

Файл: manager/src/api/audit.py::audit_stats

Фикс:

python
from ..db.models import Resource
from sqlalchemy import func

@router.get("/stats")
async def audit_stats(db: Session = Depends(get_db)):
    total_resources = db.query(func.count(Resource.id)).scalar()
    return {..., "total_resources": total_resources}
Тест: test_audit_stats_includes_resources.

🔴 BUG-148 — Scanner не читает .env
Симптомы: start_scanner.bat загружает только FINDINGS_* из secrets/,
не читает .env → S3_ACCESS_KEY / S3_SECRET_KEY не загружаются.

Файл: start_scanner.bat

Фикс:

bat
REM Загрузка .env
if exist "%~dp0.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0.env") do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b"
    )
)
Или — python-dotenv в run_scanner.py:

python
from dotenv import load_dotenv
load_dotenv()
Тест: запустить start_scanner.bat, S3_ACCESS_KEY не пустой в логах.

✅ Definition of Done
Все 4 unit-теста + 6 integration-тестов проходят.

pytest tests/unit — 433+ passed (не меньше).

pytest tests/e2e — 53 passed, 7 skipped (эталон).

Ручная проверка: смена пароля, аудит, viewer 403, /api/audit/{id} 200.

audit_logs — без ложных user_password_changed.

ARCHITECTURE.md — обновлён (BUG-223, BUG-181).

Конец ТЗ 53.4a-доп3