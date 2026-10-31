# Отчёт — День 53.4e-rbac-hotfix (v3.14.3)

**Дата:** 17.10.2026
**ТЗ:** `prompts/tz/day_53_4e_rbac_hotfix.md` — RBAC Hotfix & Security (блоки 12–13: Users, Roles).
**Версия:** v3.14.2 → **v3.14.3**
**Статус:** ✅ Выполнено (unit 6 passed, e2e 4 passed, живой API-смок 403/400/400)

---

## Кратко

Закрыты 7 задач, найденных при верификации WebUI (Блок 12 — Users, Блок 13 —
Roles):

| ID | Название | Статус |
|----|----------|--------|
| **BUG-253** | Можно снять `admin` с себя → лок-аут | ✅ v3.14.3 |
| **BUG-257** | Системные роли: `name` / `ad_group` можно менять | ✅ v3.14.3 |
| **BUG-258** | Кастомные роли без `permissions` → отключено | 📋 до v3.1.0 |
| **BUG-254** | Нет валидации «хотя бы одна роль» | ✅ v3.14.3 |
| **BUG-255** | Кнопка «Войти» не в стиле Dovetail | ✅ v3.14.3 |
| **BUG-256** | Редирект (viewer, 403) — без toast | ✅ v3.14.3 |
| **BACKLOG-316** | Роль `scanner` (машинная) в `/users` | ✅ v3.14.3 |

Ключевое: защита от лок-аута (нельзя снять `admin` с себя), иммутабельность
системных ролей по `name`/`ad_group`, отключение кастомных ролей до появления
RBAC-`permissions` (v3.1.0), UX-полировка (кнопка, toast).

---

## Изменённые / созданные файлы

| Файл | Изменение | Баг |
|------|-----------|-----|
| `manager/src/auth/router.py` | `create_user`: 400 без ролей; `update_user`: 400 при снятии `admin` с себя и при пустом списке ролей; `create_role`: 403 (отключено) | 253/254/258 |
| `webui/static/js/users.js` | `renderRolesCheckboxes(..., {isSelf})`: `admin` disabled при self; фильтр машинной роли `scanner`; `saveUser`: валидация «хотя бы одна роль» | 253/254/316 |
| `webui/static/js/roles.js` | `editRole`: `title` + disabled для системных `name`/`ad_group`; `showCreateRoleModal`: сброс `title` | 257 |
| `webui/static/js/api.js` | 403 → toast «Недостаточно прав» + отложенный редирект | 256 |
| `webui/templates/roles.html` | кнопка «Создать роль» → `disabled` + `title` (BACKLOG-258) | 258 |
| `webui/static/css/components.css` | `.btn-primary`: 8px, padding 10×16, weight 500, size 14px, transition; `:disabled` cursor | 255 |
| `tests/unit/test_auth_rbac_v3143.py` | **новый**, 6 тестов | — |
| `tests/e2e/test_rbac_v3143.py` | **новый**, 4 теста | — |
| `tests/unit/test_roles_crud_audit_v31339.py` | 3 теста адаптированы под BUG-258 | — |
| `docker-compose.yml` | все `${VERSION:-3.14.2}` → `3.14.3` (12 вхождений) | — |
| `CHANGELOG.md` | секция `## [v3.14.3]` | — |
| `ARCHITECTURE.md` | версия; ролевая модель; API `/roles`; таблица ограничений | — |
| `ROADMAP.md` | 53.4e-rbac-hotfix → ✅ v3.14.3 | — |
| `STATE.md` | версия/статус/day/закрытия/футер → v3.14.3 | — |
| `STATE_TEST_SESSION.md` | блоки 12–13 → ✅, v3.14.3 | — |

---

## Реализация по задачам

### 🔴 BUG-253 — нельзя снять `admin` с себя

`webui/static/js/users.js` → `renderRolesCheckboxes`:

```javascript
function renderRolesCheckboxes(selectedRoles, opts = {}) {
    const cont = document.getElementById('rolesCheckboxes');
    if (!rolesCache.length) { cont.innerHTML = '<span class="text-muted">Нет ролей</span>'; return; }

    const isSelf = opts.isSelf || false;
    // BACKLOG-316: скрыть машинную роль scanner
    const humanRoles = rolesCache.filter(r => r.name !== 'scanner');

    cont.innerHTML = humanRoles.map(r => {
        const id = 'rolechk_' + r.name.replace(/[^A-Za-z0-9_]/g, '_');
        const checked = selectedRoles.includes(r.name) ? 'checked' : '';
        // BUG-253: admin нельзя снять с себя
        const disabled = (isSelf && r.name === 'admin') ? 'disabled' : '';
        const title = (isSelf && r.name === 'admin')
            ? 'Нельзя снять роль admin с себя' : '';
        return `<div class="form-check"><input class="form-check-input" type="checkbox"
            id="${id}" data-role="${escapeHtml(r.name)}" ${checked} ${disabled}
            title="${title}"><label class="form-check-label" for="${id}">${escapeHtml(r.name)}</label></div>`;
    }).join('');
}
```

`editUser` передаёт `{ isSelf }`:

```javascript
renderRolesCheckboxes(
    (u.roles || []).map(r => typeof r === 'string' ? r : r.name),
    { isSelf }
);
```

`manager/src/auth/router.py` → `update_user` (защита на backend):

```python
    # BUG-253 (v3.14.3): нельзя снять роль admin с себя — иначе лок-аут.
    # BUG-254 (v3.14.3): хотя бы одна роль (пустой список ролей запрещён).
    if user_data.roles is not None:
        if user_id == admin.id and "admin" not in user_data.roles:
            raise HTTPException(status_code=400, detail="Нельзя снять роль admin с себя")
        if len(user_data.roles) == 0:
            raise HTTPException(status_code=400, detail="Выберите хотя бы одну роль")
```

### 🔴 BUG-257 — иммутабельность системных ролей

`SYSTEM_ROLES = {"admin", "auditor", "scanner", "viewer"}` уже был реализован
ранее (BUG-168, v3.13.39) — backend корректно отклоняет смену `name`/`ad_group`
системной роли. В этом фиксе добавлено **frontend-пояснение** —
`webui/static/js/roles.js` → `editRole`:

```javascript
document.getElementById('roleName').disabled = sys;
document.getElementById('roleName').title = sys ? 'Системные роли нельзя переименовать' : '';
document.getElementById('roleAdGroup').disabled = sys;
document.getElementById('roleAdGroup').title = sys ? 'Системные роли: AD-группа неизменна' : '';
```

Сброс в `showCreateRoleModal`:

```javascript
document.getElementById('roleName').title = '';
document.getElementById('roleAdGroup').title = '';
```

### 🟡 BUG-258 — кастомные роли отключены до v3.1.0

`manager/src/auth/router.py` → `create_role` (первой строкой):

```python
    raise HTTPException(
        status_code=403,
        detail="Кастомные роли отключены до v3.1.0 (BACKLOG-258). Используйте системные роли.",
    )
```

`webui/templates/roles.html`:

```html
<button class="btn btn-primary mb-3" disabled
        title="Доступно в v3.1.0 (BACKLOG-258)"><i class="fas fa-plus"></i> Создать роль</button>
```

### 🟡 BUG-254 — валидация «хотя бы одна роль»

Backend (`create_user`):

```python
    # BUG-254 (v3.14.3): хотя бы одна роль.
    if not user_data.roles:
        raise HTTPException(status_code=400, detail="Выберите хотя бы одну роль")
```

Frontend (`users.js` → `saveUser`):

```javascript
    // BUG-254 (v3.14.3): пользователь без ролей бесполезен.
    const roles = getSelectedRoles();
    if (roles.length === 0) {
        showToast('Выберите хотя бы одну роль', 'warning');
        return;
    }
```

### 🟡 BACKLOG-316 — скрыть машинную роль `scanner` из `/users`

Реализовано фильтром `humanRoles` (см. BUG-253). В `/roles` роль `scanner`
остаётся (нужна сканеру).

### 🟢 BUG-255 — кнопка «Войти» в стиле Dovetail

`webui/static/css/components.css` → `.btn-primary`:

```css
    border: none;
    /* BUG-255 (v3.14.3): явный Dovetail-профиль кнопки (login и модалки). */
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: 500;
    font-size: 14px;
    transition: background-color 0.15s ease;
}
/* ... */
.btn-primary:focus, .btn-primary:active {
    background-color: var(--color-snow); color: var(--color-page-ink);
    border: none; box-shadow: none; outline: none;
}
.btn-primary:disabled, .btn-primary.disabled {
    background-color: var(--color-fog); color: var(--color-page-ink);
    border: none; cursor: not-allowed;
}
```

Проверено headless Chrome (computed style): `radius=8px`, `padding=10px 16px`,
`weight=500`, `size=14px`, `bg=rgb(255,255,255)`.

### 🟢 BUG-256 — toast при 403

`webui/static/js/api.js` → `_handleErrors`:

```javascript
        if (r.status === 403) {
            if (typeof showToast === 'function') {
                showToast('Недостаточно прав', 'error');
            }
            setTimeout(() => {
                if (window.location.pathname !== '/') {
                    window.location.href = '/';
                }
            }, 1000);
        }
```

---

## Отклонения от ТЗ (осознанные)

1. **BUG-253 backend** — guard `if user_data.roles is not None:` вместо
   буквального `payload.roles or []`. Иначе правка собственного профиля без
   поля `roles` в теле давала бы ложный 400 «снимите admin с себя».
2. **Тип toast** — `warning` (BUG-254) и `error` (BUG-256) вместо `danger` из
   ТЗ: в `showToast` нет ключа `danger` (валидные типы — `success/info/warning/error`).
3. **`manager/src/auth/schemas.py` не менялся** — `UserCreate.roles=["viewer"]`
   и `UserUpdate.roles=None` уже корректны; добавление ограничений в схему
   увело бы валидацию в 422 вместо требуемого ТЗ 400.
4. **`auth.js` не менялся** — `errorToRussian` уже корректно обрабатывает
   сообщения; тексты ошибок backend на русском.
4. **`docker-compose.test.yml` не менялся** — там версия тест-стека (`3.13.41`)
   намеренно отличается от релизной.

---

## Тесты

```
python -m pytest tests/unit -q            → 466 passed
python -m pytest manager/tests/test_metrics_v3142.py -q
                                          → 6 passed
# Итого unit: 466 + 6 = 472 passed

$env:MANAGER_URL="http://localhost:8000"; $env:WEBUI_URL="http://localhost:8001"
python -m pytest tests/e2e/test_rbac_v3143.py -v
4 passed
```

`tests/unit/test_auth_rbac_v3143.py` (6):
- `POST /api/auth/roles` → 403;
- `PUT /api/auth/roles/{system}` (name) → 400, (description) → 200;
- `POST /api/auth/users` (без ролей) → 400;
- `PUT /api/auth/users/{self}` (без `admin`) → 400, (с `admin`) → 200.

`tests/e2e/test_rbac_v3143.py` (4, против живого стека):
- `users.js` содержит фильтр `r.name !== 'scanner'` (BACKLOG-316);
- `users.js` содержит `isSelf && r.name === 'admin'` (BUG-253);
- `users.js` содержит `roles.length === 0` (BUG-254);
- `/roles` содержит disabled-кнопку с `BACKLOG-258` (BUG-258).

Живой API-смок (`admin/admin123`, стек v3.14.3):

```
POST /api/auth/roles            -> 403
PUT  /api/auth/users/1 (no admin) -> 400
POST /api/auth/users (no roles) -> 400
```

`tests/unit/test_roles_crud_audit_v31339.py` — 3 теста переведены на BUG-258
(создание ролей → 403; кастомные роли для delete/rename вставляются в БД напрямую).

Полный прогон `tests/e2e` включает давно известные флаки/ошибки окружения
(TEST-NOTE-10.8/10.10 — требуют наполненных findings и живого сканера), поэтому
подсветка — целенаправленный прогон 4 новых E2E-проверок.

---

## Ручная проверка (для пользователя)

1. Ребилд образов (менялись Manager и WebUI):
   ```
   docker compose build manager webui
   docker compose up -d manager webui celery_worker celery_beat
   ```
2. `/login` → кнопка «Войти» — 8px радиус, отступы (Dovetail).
3. `/users` (admin):
   - модалка создания → **нет** чекбокса `scanner`;
   - сохранение без ролей → toast «Выберите хотя бы одну роль»;
   - редактирование **своей** учётки → чекбокс `admin` disabled (tooltip).
4. `/roles` (admin):
   - кнопка «Создать роль» — disabled (tooltip «Доступно в v3.1.0»);
   - редактирование системной роли → `name`/`ad_group` disabled (tooltip),
     `description` доступно.
5. Viewer → `/users` → toast «Недостаточно прав» + редирект на главную.

---

## Коммит

Коммиты — точечно по стадиям (pathspec), без посторонних файлов.

```bash
# 1) Код RBAC + тесты
git add manager/src/auth/router.py \
        webui/static/js/users.js webui/static/js/roles.js webui/static/js/api.js \
        webui/templates/roles.html webui/static/css/components.css \
        tests/unit/test_auth_rbac_v3143.py tests/unit/test_roles_crud_audit_v31339.py \
        tests/e2e/test_rbac_v3143.py
git commit -m "fix: 53.4e RBAC hotfix — защита admin + иммутабельность системных ролей (v3.14.3)

- BUG-253: нельзя снять admin с себя (frontend disabled + backend 400).
- BUG-257: системные роли (admin/auditor/viewer) — name/ad_group иммутабельны (UI).
- BUG-258: кастомные роли отключены (403, кнопка disabled до v3.1.0).
- BUG-254: валидация «хотя бы одна роль» при создании (frontend + backend 400).
- BACKLOG-316: скрыть scanner (машинная роль) из /users.
- BUG-255: кнопка «Войти» приведена к Dovetail (8px радиус, padding).
- BUG-256: toast при редиректе с /users (viewer).

Tests: test_auth_rbac_v3143.py (6 unit), test_rbac_v3143.py (4 e2e)."

# 2) Версия
git add docker-compose.yml
git commit -m "chore: VERSION 3.14.2 → 3.14.3 (docker-образы)"

# 3) Документация
git add ARCHITECTURE.md ROADMAP.md STATE.md STATE_TEST_SESSION.md CHANGELOG.md \
        .gitignore \
        prompts/archive/day_53_4e_rbac_hotfix.md \
        prompts/reports/day_53_4e_rbac_hotfix_report.md
git commit -m "docs: 53.4e-rbac-hotfix (v3.14.3) — ARCHITECTURE/ROADMAP/STATE/CHANGELOG + ТЗ/отчёт"
```

# 4) BUG-252 follow-up (чекбоксы)
git add webui/static/css/base.css
git commit -m "fix: BUG-252 follow-up — исключить checkbox/radio из глобального input-фона (v3.14.3)"
```

Примечание: **BUG-252** добит follow-up-коммитом `eb7ee30`
(`webui/static/css/base.css`: `input:not([type="checkbox"]):not([type="radio"])`).
Первая часть (`:checked`-галочка + `:focus`) — в `ae40933` (`components.css`,
+8 строк). Проверено headless Chrome: checkbox bg `rgb(103,152,255)` +
svg-галочка; text input / select — `--color-deep-coal` (регресса нет).
BUG-252 в ТЗ 53.4e не входил — зафиксирован как follow-up в той же версии.

---

## После фикса

- Блок 12 (Users) — ✅ закрыт.
- Блок 13 (Roles) — ✅ закрыт.
- Следующий — Блок 14 (Settings).

**Конец отчёта 53.4e-rbac-hotfix (v3.14.3)**
