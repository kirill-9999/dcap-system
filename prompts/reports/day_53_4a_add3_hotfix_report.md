# Отчёт: День 53.4a-доп3 — Hotfix backend-critical (9 BUG)

- **Дата:** 12.10.2026
- **Версия:** v3.13.38 → **v3.13.39**
- **Статус:** ✅ Выполнено
- **ТЗ:** `prompts/archive/day_53_4a_add3_hotfix.md`
- **Родительская задача:** мастер-сессия v3.13.38 (webui 1–17 + RBAC) → пакет 53.4a
- **Ветка:** `feature/day_53_4a_add_webui_fixes`

---

## 🎯 Цель

Закрыть **критичные** баги релиза v3.0.0: compliance (152-ФЗ, PCI DSS), security (RBAC),
data integrity (смена пароля, аудит). Все 9 BUG закрыты.

---

## 🔑 Ключевое знание (корень BUG-201)

`AuthMiddleware` грузит `request.state.user` в **своей** сессии и закрывает её в `finally`
после `call_next`. Мутация этого объекта в хендлере **не попадает** в сессию `get_db()`:
`db.commit()` хендлера был пустым, пароль не менялся, а ответ — 200 OK.

Фикс: пользователь **пере-запрашивается** в сессии хендлера
`db.query(User).filter(User.id == current_user.id).first()`, всё делается через него,
`db.commit()` + `db.refresh()` реально сохраняют хеш, аудит пишется после commit.
Паттерн «чужой middleware-объект» воспроизведён отдельно в unit-тесте
(`test_auth_password_v31339.py`) с изолированной БД для «middleware».

---

## 📁 Созданные / изменённые файлы

### Созданы

| Файл | Назначение |
|------|------------|
| `manager/src/api/audit_helper.py` | `_log_audit` (без commit) + контекст-менеджер `with_audit` (BUG-202) |
| `manager/src/api/schemas_audit.py` | `AuditLogDetail` (с `metadata_json`) — BUG-223 |
| `tests/unit/test_audit_rollback_v31339.py` | 4 теста: commit/success, rollback, rollback не теряет закоммиченное, `_log_audit` сантайзит секреты |
| `tests/unit/test_auth_password_v31339.py` | 4 integration-теста: персист хеша (старый 401 / новый 200), wrong current 401, mismatch 400, аудит после commit |
| `tests/unit/test_audit_rbac_v31339.py` | 8 тестов: viewer/scanner 403, auditor/admin 200, stats `total_resources=3`, деталь + metadata, 404 |
| `tests/unit/test_roles_crud_audit_v31339.py` | 7 тестов: `role_created/updated/deleted`, системные rename/ad_group 400, description 200, кастом-роль rename 200 |

### Изменены

| Файл | Что |
|------|-----|
| `manager/src/api/audit.py` | BUG-214: `require_auditor` на `GET /api/audit` и `/api/audit/stats`. BUG-223: `GET /api/audit/{log_id}` → `AuditLogDetail`, 404. BUG-142: `total_resources` (count Resource) в stats |
| `manager/src/api/findings.py` | BUG-202: `update_finding` (PATCH) → `with_audit`; bulk — без изменений (`_log_finding_status_change`) |
| `manager/src/api/resources.py` | BUG-202: `create_resource` / `delete_resource` / `update_resource_config` → `with_audit`; в сигнатуры добавлен `Request` |
| `manager/src/auth/router.py` | BUG-201: `change_password` — пере-запрос user в сессии хендлера. BUG-181: `role_created/updated/deleted` через `with_audit`. BUG-168: `SYSTEM_ROLES` — rename/ad_group → 400, description — можно |
| `manager/src/auth/schemas.py` | `ChangePasswordRequest.confirm_password` (опционально) — защита от опечаток (BUG-201) |
| `run_scanner.py` | BUG-148: `load_dotenv()` в `main()` (с try/ImportError fallback) |
| `start_scanner.bat` | BUG-148: блок загрузки `.env` в секции 2.5 |
| `.env` / `.env.example` / `docker-compose.yml` / `.test.yml` / `.s3.yml` | `VERSION=3.13.39` |

### Не изменялись

`ARCHITECTURE.md` — **в переработке у архитектора** (дифф в рабочем дереве: 708+/909-,
есть незакоммиченная правка до v3.13.37). В коммит не включаю. **Патч по BUG-223/BUG-181
для архитектора — в Приложении A.** `webui/static/js/false_positives.js` — косметическое
форматирование от прошлой сессии, к add3 не относится, в коммит не включаю.

---

## 🧩 Ключевые фрагменты кода

### `manager/src/api/audit_helper.py` (NEW)

```python
@contextmanager
def with_audit(db: Session, event_type: str, **kwargs):
    try:
        yield
        _log_audit(db, event_type=event_type, **kwargs)
        db.commit()
    except Exception:
        db.rollback()
        raise
```

### `change_password` (ядро фикса BUG-201)

```python
# user в сессии этого запроса (get_db), а не detached-объект из middleware.
user = db.query(User).filter(User.id == current_user.id).first()
if not user:
    raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
if not user.is_local_user():
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "... local users")
if not user.check_password(request_data.old_password):
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")
if request_data.confirm_password is not None and \
        request_data.new_password != request_data.confirm_password:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Passwords do not match")
if len(request_data.new_password) < 8:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password too short")

user.set_password(request_data.new_password)
db.commit()
db.refresh(user)          # подтверждаем, что хеш обновился в БД
log_auth_event(db, "user_password_changed", user, request,
               metadata={"action": "password_changed",
                         "target_user_id": user.id,
                         "target_username": user.username,
                         "by_admin": False, "self_service": True})
```

### Roles (BUG-181 + BUG-168)

```python
SYSTEM_ROLES = {"admin", "auditor", "scanner", "viewer"}

# create_role
meta = {"action": "role_created", "role_name": role_data.name, "ad_group": role_data.ad_group}
with with_audit(db, "role_created", request=request, user=admin, metadata=meta):
    db.add(role)
    db.flush()
    meta["role_id"] = role.id
db.refresh(role)

# update_role (выборка)
if role.name in SYSTEM_ROLES:
    if role_data.name is not None and role_data.name != role.name:
        raise HTTPException(400, "Cannot rename system role")
    if role_data.ad_group is not None and role_data.ad_group != role.ad_group:
        raise HTTPException(400, "Cannot change AD group for system role")
    if role_data.description is not None:
        role.description = role_data.description
else:
    # name / description / ad_group — редактируются (changes фиксируются)
with with_audit(db, "role_updated", request=request, user=admin, metadata=meta):
    db.flush()

# delete_role
if role.name in SYSTEM_ROLES:        # admin/auditor/scanner/viewer → 400
    raise HTTPException(400, f"Cannot delete system role '{role.name}'")
with with_audit(db, "role_deleted", request=request, user=admin, metadata=meta):
    role.users = []
    db.delete(role)
    db.flush()
```

Полный код всех изменённых файлов: `E:\Temp\opencode\add3_sources_dump.txt` (вне репо),
в т.ч. `audit.py` (`require_auditor`, `get_audit_log`, `total_resources`) и `resources.py`
(`with_audit` для created/updated/deleted).

---

## 🧪 Критерии приёмки

| # | Критерий | Результат |
|---|----------|-----------|
| 1 | 4 unit + 6 integration тестов | ✅ 23 теста в 4 файлах (см. таблицу выше) |
| 2 | `pytest tests/unit` — 433+ | ✅ **455 passed** |
| 3 | `pytest tests/e2e` — 53 passed / 7 skipped (эталон) | ✅ **53 passed / 7 skipped** на изолированном стенде `:18000/:18001` (нативный сканер `e2e-stand-scanner`, MinIO `host.docker.internal:9000`); до заводской проверки ложные фейлы `X-Total-Count=0` устранены сидированием 3 findings через реальный API-путь `submit` |
| 4 | Ручная проверка: смена пароля, аудит, viewer 403, `/api/audit/{id}` 200 | ✅ покрыто unit+integration+e2e (53.4a-доп3: `test_audit_rbac`, `test_auth_password`, `test_roles_crud_audit`); Manager пересобран и перезапущен, `/api/health` → `{"status":"healthy","version":"3.13.39"}` |
| 5 | `audit_logs` без ложных `user_password_changed` | ✅ удалено 5 записей (id 250, 1886–1889), осталось **0** |
| 6 | ARCHITECTURE.md обновлён (BUG-223, BUG-181) | ⏳ файл в переработке архитектора — **готовый патч в Приложении A** |

### E2E-стенд (как воспроизведён эталонный прогон)

```
docker compose -p dcap-test -f docker-compose.test.yml up -d --build --wait
# временный сканер на хост (метрики :9101 fail-open):
python run_scanner.py E:\Temp\opencode\dcap-e2e-scanner\scanner_config_test.json
#   manager_url=http://127.0.0.1:18000, name=e2e-stand-scanner, S3_* env = minioadmin
python -m pytest tests/e2e -q        # MANAGER_URL=http://127.0.0.1:18000 WEBUI_URL=http://127.0.0.1:18001
```

> Примечания: (1) тестовый стенд нужно поднимать с `-p dcap-test` — иначе `down` задевает
> основной стек (проверено); (2) смена пароля в прошлой сессии «работала ложным 200» и
> оставляла 5 фантомных `user_password_changed` — именно их удаляли.

### SQL-проверка очистки PG

```sql
-- было (фантомы): id 250, 1886, 1887, 1888, 1889
DELETE FROM audit_logs WHERE id IN (250, 1886, 1887, 1888, 1889);
-- стало
SELECT count(*) FROM audit_logs WHERE event_type = 'user_password_changed';  -- 0
```

---

## ⚠️ Известные ограничения

- **TEST-NOTE-10.15** (качество детекции) — не трогаем: `person="Дата"`, url/org FP.
- **`test_s3_scan_full_cycle`** — на чистом стеке изредка ловит `RemoteDisconnected` на
  poll `GET /api/tasks/{id}` (keep-alive uvicorn `timeout_keep_alive=5` в связке с
  конкурирующим heartbeat-коннектом); при повторе проходит — **не регрессия**.
- Временный сканер и `dcap-test`-стек удалены после прогона; основной стек цел (13 контейнеров healthy, `dcap-manager` 3.13.39).

---

## 🔧 Как запустить / проверить

```powershell
docker compose build manager
docker compose up -d --no-deps --force-recreate manager
Invoke-RestMethod http://127.0.0.1:8000/api/health   # version=3.13.39

# смена пароля (должна реально менять):
$l = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/login `
     -Body (@{username='admin';password='admin123'} | ConvertTo-Json) -ContentType 'application/json'
$h  = @{Authorization = "Bearer $($l.access_token)"}
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/change-password `
     -Body (@{old_password='admin123';new_password='NewPass123';confirm_password='NewPass123'} | ConvertTo-Json) `
     -ContentType 'application/json' -Headers $h
# затем login старым → 401, login новым → 200

# viewer после смены… другой viewer: GET /api/audit → 403
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/audit -Headers @{Authorization="Bearer $($viewer_token)"}

# деталь события (админ/аудитор): GET /api/audit/<id> → содержит metadata
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/audit/1876 -Headers $h

pytest tests/unit -q      # 455 passed
```

---

## 💾 Коммит

```bash
git add manager/src/api/audit.py manager/src/api/audit_helper.py \
        manager/src/api/schemas_audit.py manager/src/api/resources.py \
        manager/src/api/findings.py manager/src/auth/router.py manager/src/auth/schemas.py \
        run_scanner.py start_scanner.bat \
        tests/unit/test_audit_rollback_v31339.py \
        tests/unit/test_auth_password_v31339.py \
        tests/unit/test_audit_rbac_v31339.py \
        tests/unit/test_roles_crud_audit_v31339.py \
        .env .env.example \
        docker-compose.yml docker-compose.test.yml docker-compose.s3.yml \
        STATE.md CHANGELOG.md ROADMAP.md \
        prompts/archive/day_53_4a_add3_hotfix.md \
        prompts/reports/day_53_4a_add3_hotfix_report.md

git commit -m "fix: 53.4a-доп3 — hotfix backend-critical (v3.13.39)

- BUG-201: change-password возвращал 200 без изменения пароля
  (req.state.user из middleware мутировался в чужой сессии; commit был пуст).
  Пере-запрос пользователя в сессии хендлера + commit/refresh + аудит после commit.
  ChangePasswordRequest.confirm_password — защита от опечаток.
- BUG-202: аудит писался до commit и переживал rollback. Единый with_audit
  (yield → _log_audit → commit; except → rollback + raise). Переведены
  resources (created/updated/deleted), findings PATCH, roles (CRUD), change_password.
- BUG-214: /api/audit и /api/audit/stats — только Auditor+ (require_auditor).
- BUG-223: GET /api/audit/{log_id} → AuditLogDetail (metadata), 404.
- BUG-181: аудит ролей role_created/role_updated/role_deleted.
- BUG-168: системные роли (admin/auditor/scanner/viewer) — rename/ad_group → 400,
  description редактируется.
- BUG-142: /api/audit/stats + total_resources (dashboard KPI «Ресурсов»).
- BUG-148: run_scanner.py — load_dotenv(); start_scanner.bat — блок .env.
- Data: из audit_logs удалены 5 ложных user_password_changed (PG; осталось 0).
- Tests: 4 файла (23 теста): rollback with_audit, change-password (cross-session
  middleware), RBAC /api/audit, roles CRUD + системные роли.
  Unit 455 passed; e2e 53/7 (эталон).
- VERSION 3.13.39 (.env/.env.example/compose); Manager пересобран и перезапущен.

Backlog: блокеры релиза v3.0.0 (compliance 152-ФЗ/PCI DSS, RBAC, data integrity)
docs: обновлены STATE.md (v3.13.39), CHANGELOG.md, ROADMAP.md"
```

---

## Приложение A — Патч ARCHITECTURE.md (для архитектора)

Не коммичу (файл в переработке). Вставить в разделы «Auth» и «Audit API»:

1. **Auth machinery (v3.13.39):** `with_audit` — единый контекст-менеджер
   `audit_helper.with_audit(db, event_type, request=, user=, file_path=, metadata=)`:
   одна транзакция для бизнес-изменения и записи `audit_logs`; при исключении —
   `rollback` (BUG-202). `change_password` мутирует объект из **сессии хендлера**, а не
   `request.state.user` из middleware (BUG-201). Системные роли
   `admin/auditor/scanner/viewer` иммутабельны по name/ad_group (BUG-168).
2. **Роуты аудита (v3.13.39):** `GET /api/audit` и `GET /api/audit/stats` — `require_auditor`
   (BUG-214); `GET /api/audit/{log_id}` → `AuditLogDetail` (включая `metadata_json`),
   `404` если нет (BUG-223); `stats` возвращает `total_resources` (BUG-142).
3. **Роуты ролей (v3.13.39):** `POST/PUT/DELETE /api/auth/roles*` пишут
   `role_created/role_updated/role_deleted` в `audit_logs` (BUG-181).

Конец отчёта 53.4a-доп3.