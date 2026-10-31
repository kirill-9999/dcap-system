📄 4. TZ_FIX_SPRINT.md — Задание на доработку
markdown
# 🔧 ТЗ: Fix-спринт по итогам тестирования Блока 2 (Auth/RBAC)

**Дата:** 19.09.2026
**Приоритет:** Блокер v3.0.0
**Источник:** `STATE_TEST_SESSION.md` (Блок 2)
**Цель:** закрыть 4 критичных + 10 важных + 5 средних багов, найденных при тестировании RBAC

---

## 🎯 Общие требования

1. **После каждого фикса** — прогон соответствующего сценария из `STATE_TEST_SESSION.md`.
2. **Юнит-тесты обязательны** для каждого RBAC-фикса (см. ниже).
3. **Обратная совместимость** — не ломать существующие тесты (кроме тех, что проверяют багованное поведение).
4. **Коммиты** — по одному на баг (или логически связанную группу).
5. **Обновить `CHANGELOG.md`** — по завершении.

---

## 🔴🔴 КРИТИЧНО — блокеры v3.0.0

### TASK-001 — BUG-039: refresh как access

**Файл:** `manager/src/auth/jwt.py`

**Проблема:** `verify_token` не проверяет `payload["type"]`. Refresh-токен принимается в `/me`, `/check`, всех access-эндпоинтах.

**Fix:**

```python
def verify_token(self, token: str, expected_type: str = "access") -> Optional[Dict]:
    try:
        payload = jwt.decode(token, self.secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload
Обновить вызывающих:

dependencies.py — все verify_token(token) → verify_token(token, "access") (по умолчанию).

router.py::/refresh — verify_token(refresh_token, "refresh"); удалить локальную проверку payload.get("type") != "refresh".

Тесты (новые, tests/unit/test_jwt_type.py):

test_refresh_rejected_as_access — /me с refresh → 401.

test_access_rejected_as_refresh — /refresh с access → 401.

test_access_accepted_as_access — /me с access → 200.

test_refresh_accepted_as_refresh — /refresh с refresh → 200.

Verify (вручную):

powershell
# refresh в /me → 401
$r = Post-Api -Url "http://localhost:8000/api/auth/login" -Json '{"username":"admin","password":"admin123"}'
$o = $r.Body | ConvertFrom-Json
$h = @{ Authorization = "Bearer $($o.refresh_token)" }
(Get-Api -Url "http://localhost:8000/api/auth/me" -Headers $h).Status  # 401
TASK-002 — BUG-046: RBAC на DELETE /api/resources/{id}
Файл: manager/src/api/resources.py:104

Проблема: viewer удалил ресурс id=1 (200). auditor/scanner получили 404 вместо 403. RBAC отсутствует.

Fix:

python
from manager.src.auth.dependencies import require_admin

@router.delete("/{resource_id}")
def delete_resource(
    resource_id: int,
    db: Session = Depends(session.get_db),
    user: User = Depends(require_admin),   # ← ДОБАВИТЬ
):
    ...
Также проверить и защитить (если не защищены):

resources.py:71 — POST "" → require_admin

resources.py:121 — POST /{resource_id}/scan → require_scanner

resources.py:166 — PUT /{resource_id}/config → require_admin

Тесты (tests/unit/test_rbac_resources.py):

test_viewer_cannot_delete_resource → 403

test_auditor_cannot_delete_resource → 403

test_scanner_cannot_delete_resource → 403

test_admin_can_delete_resource → 200 (или 404)

test_viewer_cannot_create_resource → 403

TASK-003 — BUG-047: RBAC + транзакция на DELETE /api/tasks/{id}
Файл: manager/src/api/tasks.py:91

Проблема: эндпоинт без аутентификации. Публично. Удаляет task + каскад (findings/catalog/failed) без транзакции.

Fix:

python
from manager.src.auth.dependencies import require_admin

@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(session.get_db),
    user: User = Depends(require_admin),   # ← ДОБАВИТЬ
):
    """Удалить задание (каскадно)."""
    task = db.query(models.ScanTask).filter(models.ScanTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")

    if task.status in ("assigned", "running"):   # ← НОВОЕ: защита от удаления активной
        raise HTTPException(409, "Cannot delete task in status assigned/running")

    try:
        db.query(models.Finding).filter(models.Finding.task_id == task_id).delete()
        db.query(models.CatalogEntry).filter(models.CatalogEntry.task_id == task_id).delete()
        db.query(models.FailedFile).filter(models.FailedFile.task_id == task_id).delete()
        db.delete(task)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "Failed to delete task (rolled back)")

    return {"status": "deleted", "id": task_id}
Также:

tasks.py:74 — POST /{task_id}/cancel → require_scanner или require_admin.

Тесты (tests/unit/test_rbac_tasks.py):

test_delete_task_requires_auth → 401 (без токена)

test_viewer_cannot_delete_task → 403

test_admin_can_delete_completed_task → 200

test_admin_cannot_delete_running_task → 409

test_cascade_is_transactional → при ошибке всё откатывается

TASK-004 — BUG-048: RBAC на DELETE /api/scanner/{id} + обработка 500
Файл: manager/src/api/scanner.py:706

Проблема: без RBAC. Плюс 500 при несуществующем id (BUG-045).

Fix:

python
from manager.src.auth.dependencies import require_admin

@router.delete("/{scanner_id}")
def delete_scanner(
    scanner_id: int,
    db: Session = Depends(session.get_db),
    user: User = Depends(require_admin),   # ← ДОБАВИТЬ
):
    scanner = db.query(models.Scanner).filter(models.Scanner.id == scanner_id).first()
    if not scanner:
        raise HTTPException(404, "Scanner not found")   # ← вместо 500
    ...
🔴 ВАЖНЫЕ — унификация RBAC
TASK-005 — BUG-049…055: единый паттерн RBAC
Файлы:

Файл	Endpoint	Роль
webui.py:187	DELETE /api/scanners/{id}	require_admin
webui.py:213	POST /api/scanners/{id}/ping	require_scanner
webui.py:240	POST /api/tasks/create	require_scanner
webui.py:319	POST /api/resources/create	require_admin
webui.py:514	PUT /api/access/alerts/{id}	require_auditor
webui.py:602,608,661	POST /api/audit/report/*	require_auditor
audit.py:383	DELETE /api/audit/agents/{id}	require_admin
permissions.py:91	POST /api/permissions/mode	require_admin
permissions.py:150	POST /api/permissions/sync	require_admin
permissions.py:436	PUT /api/permissions/alerts/{id}	require_auditor
permissions.py:469	POST /api/permissions/alerts/{id}/generate	require_auditor
Fix (шаблон):

python
from manager.src.auth.dependencies import require_admin  # или require_scanner, require_auditor

@router.delete("/api/scanners/{scanner_id}")
def delete_scanner(
    scanner_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),   # ← ЕДИНЫЙ ПАТТЕРН
):
    ...
Тесты (tests/unit/test_rbac_webui_permissions.py): матрица ролей × эндпоинты.

Machine-API (by design — не защищать JWT):

scanner.py: /register, /heartbeat, /tasks/{id}/results, /fail, /cancel, /release — оставить публичными, но задокументировать (TODO: mTLS/API-key в v3.1.0).

audit.py: /agents/register, /agents/heartbeat, /events, /permissions — то же.

findings.py: /check-fingerprints — публичный (by design).

TASK-006 — BUG-037: group_mapping ед.ч. → мн.ч.
Файл: manager/src/config.py, в _defaults:

python
# Было:
"group_mapping": {
    "DCAP_Admin": "admin",
    "DCAP_Auditor": "auditor",
    "DCAP_Scanner": "scanner",
}
# Стало:
"group_mapping": {
    "DCAP_Admins": "admin",
    "DCAP_Auditors": "auditor",
    "DCAP_Scanners": "scanner",
}
Сверить с manager/config/config.json и ARCHITECTURE.md.

TASK-007 — BUG-043: /api/catalog/tree → 500
Файл: manager/src/api/catalog.py:149

Причина: _aggregate делает child["children"] = list(child["children"].values()) внутри цикла, а рекурсивный вызов _aggregate(child) уже сделал это. Второй вызов — AttributeError: 'list' object has no attribute 'values'.

Fix (минимальный — удалить дублирующую строку):

python
def _aggregate(node):
    if not node["children"]:
        return node
    for child in node["children"].values():
        _aggregate(child)                       # ← уже конвертирует в list
        node["total_findings"] += child["total_findings"] or 0
        ...
        # УДАЛИТЬ эту строку:
        # child["children"] = list(child["children"].values())
    node["children"] = list(node["children"].values())
    return node
Тесты (tests/unit/test_catalog_tree.py):

test_tree_with_nested_dirs — глубина ≥ 2.

test_tree_empty — пустой каталог.

Verify:

powershell
(Get-Api -Url "http://localhost:8000/api/catalog/tree" -Headers $ah).Status  # 200
TASK-008 — BUG-045: /api/scanner/* → 500
Файл: manager/src/api/scanner.py

Проблемы:

POST /api/scanner/heartbeat с невалидным scanner_id → 500.

DELETE /api/scanner/{id} с несуществующим id → 500 (BUG-048).

Fix:

Валидация Pydantic-схемы (если нет — добавить).

scanner = db.query(...).first() → если None — HTTPException(404) (не 500).

Wrap try/except для неожиданных ошибок → HTTPException(500, "Internal error, see logs") (не «голый» 500).

TASK-009 — BUG-057: Scanner fail-fast без ключей
Файл: scanner/src/encryption.py::from_env

Fix:

python
@classmethod
def from_env(cls, fail_if_missing: bool = True) -> "ScannerEncryption":
    enc_key = _read_optional_secret("findings_encryption_key", "FINDINGS_ENCRYPTION_KEY")
    hmac_key = _read_optional_secret("findings_hmac_key", "FINDINGS_HMAC_KEY")

    if not enc_key or not hmac_key:
        allow_legacy = os.getenv("DCAP_ALLOW_LEGACY_SCANNER", "false").lower() == "true"
        msg = (
            "FINDINGS_ENCRYPTION_KEY/FINDINGS_HMAC_KEY not set. "
            "Scanner cannot start without encryption keys. "
            "Set them via env or Docker Secrets. "
            "See docs/admin-guide/05-security.md."
        )
        if fail_if_missing and not allow_legacy:
            raise RuntimeError(msg)
        logger.warning(
            "⚠️ SCANNER IN LEGACY MODE — plaintext leaves host! DEV ONLY! "
            "Set DCAP_ALLOW_LEGACY_SCANNER=false in prod."
        )
        return None
    ...
Обновить run_scanner.py — вызывать get_encryption(fail_if_missing=True) до старта.

Обновить docs/admin-guide/05-security.md — раздел «Ключи сканера», fail-fast по умолчанию.

TASK-010 — BUG-058: Manager fallback line_text_encrypted
Файл: manager/src/api/scanner.py (submit_results, ~445-470)

Fix:

python
# После формирования line_text_masked:
line_enc = finding_data.get("line_text_encrypted")
if not line_enc and line_text:
    line_enc = _enc.encrypt(line_text)   # ← fallback, если сканер в legacy

# В конструкторе Finding:
finding = models.Finding(
    ...
    line_text_encrypted=line_enc,        # ← было: finding_data.get("line_text_encrypted")
    ...
)
Аналогично — в блоке existing.update (425-431):

python
if finding_data.get("line_text_encrypted"):
    existing.line_text_encrypted = finding_data.get("line_text_encrypted")
elif line_text and not existing.line_text_encrypted:
    existing.line_text_encrypted = _enc.encrypt(line_text)   # ← NEW
TASK-011 — BUG-059: POST /api/tasks/create 500
Файл: manager/src/api/webui.py::create_task

Причина: type в БД = filesystem (lowercase), в запросе = FILESYSTEM. Query не находит → INSERT → UniqueViolation на resources_path_key (индекс только на path, без type).

Fix (один из вариантов):

A) Нормализовать type на входе:

python
resource_type = str(payload.get("resource_type") or "FILESYSTEM").lower()
B) В except IntegrityError — искать без type:

python
except IntegrityError:
    db.rollback()
    resource = (
        db.query(models.Resource)
        .filter(models.Resource.path == resource_path)   # без type
        .first()
    )
    if resource is None:
        raise HTTPException(500, f"Resource creation conflict for {resource_path}")
    resource_id = resource.id
C) Правильно — нормализовать + применять A и B.

Плюс — миграция БД: изменить UNIQUE(path) → UNIQUE(path, type) (или LOWER(path)).

Тесты (tests/unit/test_create_task.py):

test_create_task_with_existing_resource → 200 (переиспользует)

test_create_task_case_insensitive_type → 200

test_create_task_new_path → 200 (создаёт)

🟡 СРЕДНИЕ
TASK-012 — BUG-038: TTL в env
Файл: manager/config/config.json

Fix: заменить числа на плейсхолдеры:

json
"jwt_access_ttl_minutes": "${JWT_ACCESS_TTL_MINUTES:-1440}",
"jwt_refresh_ttl_days":   "${JWT_REFRESH_TTL_DAYS:-7}"
Плюс — bind-mount manager/config/config.json в docker-compose.yml (чтобы админ менял без пересборки).

TASK-013 — BUG-041 + TEST-NOTE-2.6a: jti + iat + blacklist
Файл: manager/src/auth/jwt.py

Fix:

Добавить jti (UUID) + iat (UTC) в payload access и refresh.

Redis-blacklist: при /logout — jti access → blacklist с TTL = остаток exp.

При /refresh — jti старого refresh → blacklist.

Тесты:

test_refresh_rotation_blacklists_old — старый refresh отклоняется.

test_logout_blacklists_access — access после logout отклоняется.

TASK-014 — BUG-042: cookie Secure
Файл: manager/src/auth/router.py (4 места set_cookie)

Fix:

python
import os

secure = (
    os.getenv("COOKIE_SECURE", "").lower() == "true"
    or request.url.scheme == "https"
)

response.set_cookie(
    key="access_token",
    value=access_token,
    httponly=True,
    secure=secure,                # ← было False
    samesite="lax",
    max_age=60 * 60 * 24,
)
Документировать COOKIE_SECURE в 05-security.md.

TASK-015 — BUG-044: context_before не маскирует домен
Файл: scanner/src/encryption.py::mask_context

Fix: согласовать с mask_line. Email в контексте должен маскироваться так же:

python
# Сейчас:  mask(value, "email")  →  "us***@example.com"
# Нужно:   "us***@***"           (как в line_text)
Проверить: используется ли тот же mask в mask_line и mask_context — почему расхождение?

📋 Тестирование после фиксов
Обязательно прогнать заново:

RBAC-матрица (viewer / auditor / scanner / admin) — все write-эндпоинты → 403 для не-admin.

JWT flow: /me с refresh → 401; /refresh с access → 401.

BUG-046 verify: viewer → 403; admin → 404 (несуществующий id).

BUG-047 verify: без токена → 401; viewer → 403; admin → 200/409/404.

BUG-057 verify: запуск сканера без ключей → падает с понятной ошибкой.

BUG-059 verify: tasks/create с существующим ресурсом → 200 (не 500).

📊 Приёмка
Критерии:

□ Все тесты из tests/unit/test_rbac_*.py, test_jwt_type.py, test_catalog_tree.py, test_create_task.py — зелёные.
□ STATE_TEST_SESSION.md Блок 2 — повторный прогон, все ✅.
□ CHANGELOG.md — обновлён.
□ docs/admin-guide/05-security.md — обновлён (env сканера, COOKIE_SECURE).
□ 2 бэкапа БД сохранены (до/после).
□ Все критические баги (BUG-039/046/047/048) закрыты.
Конец ТЗ. Приступай по порядку — от TASK-001 к TASK-015. По каждому — коммит + verify.