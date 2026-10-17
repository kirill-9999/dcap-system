# ТЗ 53.4e — RBAC Hotfix & Security (v3.14.3)

**Файл:** `prompts/tz/day_53_4e_rbac_hotfix.md`
**Дата:** 17.10.2026
**Версия:** v3.14.2 → **v3.14.3**
**Приоритет:** 🔴 Блокер v3.0.0 (безопасность / UX / RBAC)
**Длительность:** 1–2 дня
**Источник:** Мастер-сессия (Блок 12 Users, Блок 13 Roles)
**Отчёт:** `prompts/reports/day_53_4e_rbac_hotfix_report.md`

---

## 🎯 Цель

Закрыть **7 задач**, найденных при верификации WebUI (блоки 12–13):

| ID | Название | Severity |
|----|----------|----------|
| **BUG-253** | Можно снять `admin` с себя → лок-аут | 🔴 high |
| **BUG-257** | Системные роли: `name` / `ad_group` можно менять | 🔴 high |
| **BUG-258** | Кастомные роли бесполезны (нет `permissions`) → отключить | 🟡 medium |
| **BUG-254** | Нет валидации «хотя бы одна роль» при создании | 🟡 medium |
| **BUG-255** | Кнопка «Войти» не в стиле Dovetail | 🟢 low |
| **BUG-256** | Редирект с `/users` (viewer) — без toast | 🟢 low |
| **BACKLOG-316** | Роль `scanner` (машинная) в `/users` | 🟢 low |

---

## 📋 Задачи

### 🔴 BUG-253 — Снятие `admin` с себя

**Проблема:** В `/users` → редактирование **своей** учётки → чекбокс `admin` активен. Если снять — сохраняется, пользователь теряет доступ к `/users` (лок-аут).

**Файлы:**
- `webui/static/js/users.js`
- `manager/src/auth/router.py`

**Frontend (`users.js`):**

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
        return `<div class="form-check">
            <input class="form-check-input" type="checkbox" id="${id}"
                   data-role="${escapeHtml(r.name)}" ${checked} ${disabled} title="${title}">
            <label class="form-check-label" for="${id}">${escapeHtml(r.name)}</label>
        </div>`;
    }).join('');
}
В openEditUser:

javascript
const isSelf = user.id === currentUser.id;
renderRolesCheckboxes(user.roles || [], { isSelf });
Backend (auth/router.py):

python
@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    # BUG-253: нельзя снять admin с себя
    if user_id == current_user.id and "admin" not in (payload.roles or []):
        raise HTTPException(400, "Нельзя снять роль admin с себя")

    # BUG-254: хотя бы одна роль
    if payload.roles is not None and len(payload.roles) == 0:
        raise HTTPException(400, "Выберите хотя бы одну роль")

    # ... остальное (обновление полей, аудит)
🔴 BUG-257 — Системные роли: name / ad_group нельзя менять
Проблема: В /roles → редактирование admin → поля «Название» и «Связь с AD-группой» активны. Изменение admin → слом RBAC (код ищет admin).

Файлы:

manager/src/auth/router.py

webui/static/js/roles.js

Backend (auth/router.py):

python
SYSTEM_ROLES = {"admin", "auditor", "scanner", "viewer"}

@router.put("/roles/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "Роль не найдена")

    is_system = role.name in SYSTEM_ROLES

    # BUG-257: name/ad_group иммутабельны для системных ролей
    if is_system:
        if payload.name is not None and payload.name != role.name:
            raise HTTPException(400, "Нельзя изменить название системной роли")
        if payload.ad_group is not None and payload.ad_group != role.ad_group:
            raise HTTPException(400, "Нельзя изменить AD-группу системной роли")

    if payload.description is not None:
        role.description = payload.description
    if not is_system:
        if payload.name is not None:
            role.name = payload.name
        if payload.ad_group is not None:
            role.ad_group = payload.ad_group

    db.commit()
    db.refresh(role)
    # аудит role_updated (BUG-181)
    return role
Frontend (roles.js):

javascript
function openEditRole(role) {
    const SYSTEM = ['admin','auditor','scanner','viewer'];
    const isSystem = role.is_system || SYSTEM.includes(role.name);

    const nameEl = document.getElementById('roleName');
    nameEl.value = role.name;
    nameEl.disabled = isSystem;
    nameEl.title = isSystem ? 'Системные роли нельзя переименовать' : '';

    const adEl = document.getElementById('roleAdGroup');
    adEl.value = role.ad_group || '';
    adEl.disabled = isSystem;
    adEl.title = isSystem ? 'Системные роли: AD-группа неизменна' : '';

    document.getElementById('roleDescription').value = role.description || '';
    // description всегда активен

    document.getElementById('roleId').value = role.id;
    document.getElementById('roleModal').classList.add('show');
}
🟡 BUG-258 — Кастомные роли отключить (до v3.1.0)
Проблема: Кастомные роли без permissions не дают прав — ложное чувство безопасности.

Файлы:

manager/src/auth/router.py

webui/templates/roles.html

Backend:

python
@router.post("/roles")
async def create_role(...):
    raise HTTPException(
        status_code=403,
        detail="Кастомные роли отключены до v3.1.0 (BACKLOG-258). Используйте системные роли."
    )
Frontend (roles.html):

html
<button class="btn btn-primary" disabled
        title="Доступно в v3.1.0 (BACKLOG-258)">
    + Создать роль
</button>
🟡 BUG-254 — Валидация «хотя бы одна роль» при создании
Проблема: Создаётся пользователь без ролей — бесполезен.

Файлы:

manager/src/auth/router.py

webui/static/js/users.js

Backend:

python
@router.post("/users", response_model=UserOut)
async def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not payload.roles:
        raise HTTPException(400, "Выберите хотя бы одну роль")
    # ... остальное
Frontend (users.js):

javascript
async function saveUser() {
    const roles = getSelectedRoles();
    if (roles.length === 0) {
        showToast('Выберите хотя бы одну роль', 'danger');
        return;
    }
    // ... fetch
}
🟢 BACKLOG-316 — Скрыть scanner из /users
Проблема: Роль scanner — машинная (для POST /api/scanner/register). Человеку не назначается.

Файл: webui/static/js/users.js (уже учтено в BUG-253 через humanRoles).

Дополнительно: в /roles оставить scanner (он в БД, нужен для сканера). В UI /users — только admin, auditor, viewer.

🟢 BUG-255 — Кнопка «Войти» в стиле Dovetail
Проблема: /login → кнопка «Войти» — белая плашка без padding/radius (дефолт Bootstrap).

Файл: webui/static/css/components.css — .btn-primary.

Фикс:

css
.btn-primary {
    background-color: var(--color-snow);
    color: var(--color-page-ink);
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: 500;
    font-size: 14px;
    transition: background-color 0.15s ease;
}
.btn-primary:hover {
    background-color: var(--color-ash);
    color: var(--color-page-ink);
}
.btn-primary:focus,
.btn-primary:active {
    background-color: var(--color-snow);
    color: var(--color-page-ink);
    box-shadow: none;
    outline: none;
}
.btn-primary:disabled,
.btn-primary.disabled {
    background-color: var(--color-fog);
    color: var(--color-page-ink);
    cursor: not-allowed;
}
Проверить: /login, /users (модалки), /roles, /settings.

🟢 BUG-256 — Toast при редиректе с /users (viewer)
Проблема: Viewer → /users → молчаливый редирект на /. Непонятно, почему.

Файлы:

webui/static/js/api.js — обработка 403.

webui/static/js/auth.js — errorToRussian.

Фикс (api.js):

javascript
// В request(), при response.status === 403
if (response.status === 403) {
    if (typeof showToast === 'function') {
        showToast('Недостаточно прав', 'danger');
    }
    setTimeout(() => {
        if (window.location.pathname !== '/') {
            window.location.href = '/';
        }
    }, 1000);
    return null;
}
Проверить: viewer → /users → toast + редирект.

📋 Синхронизация документации
ARCHITECTURE.md
Раздел «Ролевая модель» — добавить примечание:

Кастомные роли отключены до v3.1.0 (BACKLOG-258). Системные роли (admin, auditor, viewer) иммутабельны по name и ad_group. Роль scanner — машинная, не отображается в /users (BACKLOG-316). Нельзя снять admin с себя (BUG-253).

Известные ограничения:

BUG-253 → ✅ v3.14.3.

BUG-254 → ✅ v3.14.3.

BUG-255 → ✅ v3.14.3.

BUG-256 → ✅ v3.14.3.

BUG-257 → ✅ v3.14.3.

BUG-258 → 📋 отключено (v3.1.0 — вернуть с permissions).

BACKLOG-316 → ✅ v3.14.3.

Версия — v3.14.3.

STATE.md
Версия → v3.14.3.

Закрыто: BUG-253/254/255/256/257/258, BACKLOG-316.

Unit-счётчик: 466 + 6 = 472 passed.

Следующий шаг → Блок 14 (Settings).

ROADMAP.md
День 53.4e-rbac-hotfix → ✅ v3.14.3.

BUG-253/254/255/256/257/258 → ✅.

BACKLOG-316 → ✅.

BUG-258 → 📋 v3.1.0 (кастомные роли).

STATE_TEST_SESSION.md
Блок 12 (Users) — ✅ (BUG-253, 254, 255, 256, BACKLOG-316).

Блок 13 (Roles) — ✅ (BUG-257, 258).

Новые баги: BUG-253…258, BACKLOG-316.

CHANGELOG.md
Запись о v3.14.3.

✅ Definition of Done
BUG-253: /users → редактирование admin (себя) → чекбокс admin disabled. Backend PUT /users/{self} (без admin) → 400.

BUG-257: /roles → редактирование admin → name, ad_group disabled. Backend PUT /roles/{system} (изменить name) → 400. Изменить description → 200.

BUG-258: /roles → кнопка «+ Создать роль» disabled. Backend POST /roles → 403.

BUG-254: /users → создание без ролей → ошибка «Выберите хотя бы одну роль». Backend POST /users (без ролей) → 400.

BACKLOG-316: /users → модалка создания → нет чекбокса scanner.

BUG-255: /login → кнопка «Войти» — Dovetail (8px радиус, padding, font-weight 500).

BUG-256: Viewer → /users → toast «Недостаточно прав» + редирект.

Тесты (обязательно):

Unit: tests/unit/test_auth_rbac_v3143.py (6 тестов):

POST /api/auth/roles → 403.

PUT /api/auth/roles/{system} (name) → 400.

PUT /api/auth/roles/{system} (description) → 200.

POST /api/auth/users (без ролей) → 400.

PUT /api/auth/users/{self} (без admin) → 400.

PUT /api/auth/users/{self} (с admin) → 200.

E2E: tests/e2e/test_rbac_v3143.py (4 теста):

/users → модалка создания → нет scanner.

/users → редактирование admin (себя) → admin disabled.

/users → создание без ролей → ошибка.

/roles → кнопка «+ Создать роль» disabled.

Регресс: unit 466 + 6 = 472 passed; E2E 53/7 (эталон).

Скриншоты:

/login (кнопка «Войти») — до/после.

/users (модалка создания — без scanner, с валидацией).

/users (редактирование admin — чекбокс disabled).

/roles (кнопка «+ Создать роль» disabled).

/roles (редактирование admin — name/ad_group disabled).

💾 Коммит
bash
git add manager/src/auth/router.py \
        manager/src/auth/schemas.py \
        webui/static/js/users.js \
        webui/static/js/roles.js \
        webui/static/js/api.js \
        webui/templates/roles.html \
        webui/static/css/components.css \
        tests/unit/test_auth_rbac_v3143.py \
        tests/e2e/test_rbac_v3143.py \
        ARCHITECTURE.md \
        docker-compose.yml docker-compose.test.yml \
        STATE.md ROADMAP.md STATE_TEST_SESSION.md CHANGELOG.md \
        prompts/tz/day_53_4e_rbac_hotfix.md \
        prompts/reports/day_53_4e_rbac_hotfix_report.md

git commit -m "fix: 53.4e RBAC hotfix — защита admin + иммутабельность системных ролей (v3.14.3)

- BUG-253: нельзя снять admin с себя (frontend disabled + backend 400).
- BUG-257: системные роли (admin/auditor/viewer) — name/ad_group иммутабельны.
- BUG-258: кастомные роли отключены (403, кнопка disabled до v3.1.0).
- BUG-254: валидация «хотя бы одна роль» при создании (frontend + backend 400).
- BACKLOG-316: скрыть scanner (машинная роль) из /users.
- BUG-255: кнопка «Войти» приведена к Dovetail (8px радиус, padding).
- BUG-256: toast при редиректе с /users (viewer).

Tests: test_auth_rbac_v3143.py (6 unit), test_rbac_v3143.py (4 e2e).
VERSION 3.14.3.
Backlog: BUG-253/254/255/256/257/258, BACKLOG-316 закрыты."
📊 После фикса
Блок 12 (Users) — ✅ закрыт.

Блок 13 (Roles) — ✅ закрыт.

Переход к Блоку 14 (Settings) — чек-лист я дам после фикса.

Конец ТЗ 53.4e — RBAC Hotfix & Security (v3.14.3)