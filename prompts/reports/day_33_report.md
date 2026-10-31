# Отчёт: День 33 — Active Directory интеграция + RBAC WebUI

**Дата:** 01.09.2026
**ТЗ:** `prompts/tz/day_33_ad_integration.md`
**Роль:** Кодер
**Версия:** v3.1.0

---

## Резюме

Реализована **интеграция с Active Directory** и **RBAC WebUI** для DCAP: явный логин через AD (пароль, `ad_auth.py`), SPNEGO + реальный сбор групп/атрибутов пользователя через LDAP (`windows_auth.py`), гибридный `AuthManager`, полный **CRUD-управление пользователями и ролями** (`router.py`, `schemas.py`, `models.py`) и **данные-маппинг AD-групп → роли** (через новое поле `Role.ad_group`, заполняемое в `init_roles.py`). Добавлены **WebUI-страницы** пользователей/ролей/настроек (`users.html`, `roles.html`, `settings.html`, `users.js`, `roles.js`) с обновлением навигации и текущего пользователя в `base.html`. Реализован **сбор прав через агентов**: `collect_permissions()`/`send_permissions()` для Windows (NTFS через win32security, fallback icacls) и Linux (POSIX через getfacl, fallback stat), периодическая отправка в **`POST /api/audit/permissions`**. Инфраструктура — `docker-compose.ad.yml` с **Samba AD DC + Redis** и `scripts/init_ad_test_data.py`.

> Архитектурное решение (согласовано с пользователем): интерфейс `PermissionCollector` (dict-формат) **сохранён** — новый провайдер `PermissionProvider`/`AccessEntry` **не вводился** (это прямо предписывает AGENTS.md). `ad_auth.py` создан (в обновлённом ТЗ он явно указан). Кэш AD-запросов — `ADCache` (Redis + memory-fallback).

---

## Выполненная работа

### 1. Backend аутентификации (AD)

- **`manager/src/auth/ad_auth.py` (NEW)** — `ADAuthenticator`: явный логин через LDAP (bind по паролю, `ldap3.SIMPLE` — NTLM/проверочный механизм на Samba AD DC рвёт сессию для UPN-учёток), `_upn`, `_fetch_user_info` (sAMAccountName, mail, displayName, memberOf), `get_user_groups`. Принимает обе конвенции ключей конфига (`ad_service_account`/`service_account`).
- **`manager/src/auth/windows_auth.py`** — `get_user_info`/`get_user_groups` используют реальный LDAP через `_ad_connector()` (ADPermissionCollector с service account), fallback на мок (`DCAP_Viewer`/`example.com`).
- **`manager/src/auth/manager.py`** — порядок аутентификации: SPNEGO → **явный AD (пароль)** → локальный JWT → cached AD. `_authenticate_ad_password`: LDAP-проверка, поиск/автосоздание AD-пользователя, маппинг групп → роли. `_map_groups_to_roles` теперь принимает `db` — маппинг из конфига `group_mapping` **или** поля `Role.ad_group`.
- **`manager/src/auth/models.py`** — добавлено `Role.ad_group` (Column String(100)), `Role.to_dict(with_count)`.
- **`manager/src/auth/schemas.py`** — добавлены `UserCreate` (auth_source/is_active), `UserUpdate`, `UserStatusUpdate`, `UserRoleUpdate`, `UserListResponse`, `RoleCreate/Update/Response/ListResponse`, `ChangePasswordRequest`.
- **`manager/src/auth/router.py`** — полный CRUD Admin: `GET/POST /api/auth/users` (поиск/источник/роль + limit/offset), `GET/PUT/DELETE /api/auth/users/{id}`, `PUT .../status`, `PUT .../roles`, CRUD `GET/POST/PUT/DELETE /api/auth/roles`. Системные роли нельзя удалять; нельзя отключить/удалить себя.
- **`manager/src/db/init_roles.py`** — идемпотентная миграция колонки `ad_group` (`_ensure_role_columns`, ALTER для существующих БД) + маппинг `DCAP_Admins→admin`, `DCAP_Auditors→auditor`, `DCAP_Scanners→scanner`.

### 2. Сбор прав (агенты + API)

- **`manager/src/connectors/permissions/`** — `cache.py` (NEW, ADCache Redis+memory), `ad.py` (ADPermissionCollector: bind по паролю `ldap3.SIMPLE`, resolve_principal, get_principal_groups, SID→binary), `factory.py` (режимы local/remote/ad/mixed), `__init__.py`.
- **`manager/src/services/access_config.py`** — `ADConfig` (server/domain/base_dn/.../redis_url), `mode` + поле `ad`. **`access_service.py` / `api/permissions.py`** — разрешены режимы ad/mixed, `GET /api/permissions/resolve/{sid}`.
- **`manager/src/api/audit.py`** — добавлен **`POST /api/audit/permissions`** (приём прав от агента): ищет/создаёт `Resource` по пути, сохраняет `AccessEntry`, возвращает saved/skipped.
- **`manager/src/auth/middleware.py`** — `/api/audit/permissions` добавлен в machine-эндпоинты (без JWT), как прочие эндпоинты агентов.
- **`audit-agent-windows/collector.py`** — `collect_permissions(path)` (NTFS, win32security, fallback icacls), **`sender.py`** — `send_permissions()`, **`main.py`** — `permission_paths`/`permissions_interval` (дефолт 3600с), периодический вызов `collect_and_send_permissions()`.
- **`audit-agent-linux/collector.py`** — `collect_permissions(path)` (getfacl, fallback stat), **`sender.py`** — `send_permissions()`, **`main.py`** — периодический сбор прав (watch_paths/permission_paths).
- Конфиги агентов `config.json` — добавлен `permissions_interval`.

### 3. WebUI RBAC

- **`webui/templates/users.html`, `roles.html`, `settings.html` (NEW)** — страницы управления пользователями/ролями и настройки (режим auth, смена пароля).
- **`webui/static/js/users.js`, `roles.js` (NEW)** — CRUD через `api.get/post/put/delete`, фильтры, пагинация, роли чекбоксами.
- **`webui/static/js/api.js`** — добавлен `api.put`. **`webui/static/js/main.js`** — глобальные `openModal`/`closeModal`/`showToast`.
- **`webui/templates/base.html`** — навигация (Пользователи/Роли/Настройки — только для admin), текущий пользователь/роли подставляются из `GET /api/auth/me` (JS).
- **`webui/main.py`** — маршруты `/users`, `/roles`, `/settings`.

### 4. Инфраструктура

- **`docker-compose.ad.yml` (NEW)** — Samba AD DC `diegogslomp/samba-ad-dc` + **Redis :6379** (именованные volumes `samba_data`/`samba_logs`/`redis_data`).
- **`scripts/init_ad_test_data.py` (NEW)** — пользователи/группы `DCAP_Admins`/`DCAP_Auditors`/`DCAP_Scanners`. **`scripts/create_test_share.ps1` (NEW)**.
- **`requirements.txt`** — `ldap3>=2.9.1`, `redis>=5.0.0`.

---

## Тестирование

```
python -m pytest manager/tests/test_ad_permissions.py -v   # 16 passed
python -m pytest manager/tests/test_auth_ad.py -v          # 4 passed (NEW)
python -m pytest manager/tests/test_ad_permissions.py manager/tests/test_auth_ad.py -q   # 20 passed
```

- **`manager/tests/test_auth_ad.py` (NEW)** — автосоздание AD-пользователя + маппинг `DCAP_Admins→admin` (через `Role.ad_group`); существующий AD-пользователь (обновление `last_login`); неверные учётные данные → None; маппинг через конфиг `group_mapping`.
- HTTP-смоук через TestClient (admin): `login 200`, `me 200`, `users` (1), `roles` (4), create/update/status/delete user — все 200. Сгенерированная `manager/dcap.db` удалена (артефакт первого запуска).
- `python -m black --line-length 100` — применён к изменённым файлам.
- Оба приложения (`manager.src.main`, `webui.main`) импортируются и поднимаются.

---

## Файлы

- NEW: `docker-compose.ad.yml`, `manager/src/auth/ad_auth.py`, `manager/src/connectors/permissions/cache.py`, `scripts/init_ad_test_data.py`, `scripts/create_test_share.ps1`, `webui/templates/users.html`, `webui/templates/roles.html`, `webui/templates/settings.html`, `webui/static/js/users.js`, `webui/static/js/roles.js`, `manager/tests/test_ad_permissions.py`, `manager/tests/test_auth_ad.py`.
- Modified: `manager/src/auth/{manager,windows_auth,router,schemas,models,middleware}.py`, `manager/src/api/{audit,permissions}.py`, `manager/src/db/init_roles.py`, `manager/src/connectors/permissions/{ad,factory,__init__,test_collector}.py`, `manager/src/services/{access_config,access_service}.py`, `manager/src/connectors/permissions/` (ad/cache/factory), `audit-agent-windows/{collector,sender,main,config}.py`, `audit-agent-linux/{collector,sender,main,config}.py`, `webui/main.py`, `webui/static/js/{api,main}.js`, `webui/templates/base.html`, `requirements.txt`.

---

## Запуск (ручное тестирование)

```powershell
# 1. Рабочая БД (первый раз)
python init_db.py

# 2. Manager + WebUI
python run_all.py
# или по отдельности:
python run_manager.py
python run_webui.py

# 3. WebUI RBAC: http://127.0.0.1:8001/login (admin/admin123)
#    → Пользователи, Роли, Настройки (видны только admin)

# 4. AD-авторизация (явный логин): в конфиге manager/config/config.json
#    секция auth { mode: "hybrid", ad: { server, domain, base_dn, service_account, password } }
#    перезапустить Manager; логин через WebUI/WIAG с учёткой DCAP-группы

# 5. Тест приёма прав (POST /api/audit/permissions) — через агент аутдit или curl

# 6. Samba AD DC + Redis (если нужен реальный тестовый DC)
docker-compose -f docker-compose.ad.yml up -d
python scripts/init_ad_test_data.py
```

---

## Дополнение: результаты ручного end-to-end тестирования (02.09.2026)

Прогон выполнен на Windows (Docker Desktop + PowerShell, `PYTHONUTF8=1`). Подняты контейнеры `dcap-ad-dc` (Samba AD DC, healthy) и `dcap-redis`.

### Инфраструктура AD DC: что пришлось чинить

- **Порт-маппинг:** системные службы Windows заняты 53/135/139/445 (PID 4, SMB/NetBIOS) и UDP 53 — в `docker-compose.ad.yml` порты перевешены в 1353/1135/1139/1445; LDAP 389, Kerberos 88/464, LDAPS 636, GC 3268/3269 оставлены.
- **smb.conf (`interfaces = lo eth0@if7`):** провижининг `samba-domain-provision` пишет в smb.conf имя интерфейса из `ip a` в docker-нотации `eth0@ifN`, поэтому samba слушал только `127.0.0.1` и внешний LDAP отваливался. Фикс в живом контейнере: `interfaces = lo eth0` + рестарт. Для воспроизводимости в compose добавлена обёртка `command:` (sed-нормализация перед `samba -F`).
- **NTLM vs SIMPLE (ldap3):** NTLM-аутентификация с UPN-учёткой на Samba AD DC ломала сессию. Переведено на `ldap3.SIMPLE` в трёх местах: `ad_auth.py`, `ad.py::_connect`, `scripts/init_ad_test_data.py`.
- **Пароли тестовых пользователей:** `ldap3.extend.microsoft.modify_password` на Samba пароль не применяет (ошибки нет, но пароль не меняется). В `init_ad_test_data.py` добавлена `set_password_samba_tool()` — через `docker exec dcap-ad-dc samba-tool user setpassword` (фолбэк — `modify_password`).

### Исправления кода по результатам прогона

- **`manager/src/connectors/permissions/ad.py`** — добавлен `MixedPermissionCollector.resolve_principal()` (делегирует в AD-коллектор). Без него `GET /api/permissions/resolve/{sid}` в режиме `mixed` возвращал 400 «Resolve SID is only available for AD/mixed collector».
- **`manager/config/config.json`** — секция `auth`: `mode: "hybrid"`, `windows_auth`: `enabled`, `ad_domain: "SAMDOM"`, `ad_server: "127.0.0.1"`, `ad_base_dn: "DC=samdom,DC=example,DC=com"`, `service_account: "administrator"`, `service_password: "Passw0rd"`, `group_mapping: {DCAP_Admins→admin, DCAP_Auditors→auditor, DCAP_Scanners→scanner}`.
- **`config/access_config.json` (NEW, корень репо)** — режим прав `mode: "mixed"` + AD-параметры (127.0.0.1/SAMDOM/DC=samdom,DC=example,DC=com/administrator/Passw0rd, ldap_port 389). Тестовый конфиг, содержит dev-пароль (аналог `docker-compose.ad.yml`).

### Что проверено (реальный HTTP, JWT Bearer)

| Проверка | Результат |
|---|---|
| `GET /api/auth/mode` | `{"mode":"hybrid"}` |
| Логин `v.petrov/Passw0rd` | JWT, `auth_source=ad`, roles `["admin"]` |
| Логин `a.smirnov/Passw0rd` | `["auditor"]`; его `GET /api/auth/users` → 403 (RBAC работает) |
| Логин `admin/admin123` | гибридный фолбэк, `source=local` |
| `GET /api/permissions/mode` (Bearer) | `current_mode=mixed`, `ad available=true` |
| `POST /api/audit/agents/register` | `agent_id=1` (`dcap-ad-e2e-test`) |
| `POST /api/audit/permissions` (machine) | `{"status":"accepted","saved":1}` |
| `GET /api/audit/stats` (Bearer) | `agents_total=1`, `agents_online=1` |
| `GET /api/permissions/resolve/<SID v.petrov>` | `{"name":"SAMDOM\\v.petrov","mode":"mixed","resolved":true}` |
| WebUI :8001 `GET /`, `/login` | 200 (дашборд, страница входа) |
| WebUI :8001 `/users`, `/roles`, `/settings` (admin-JWT) | 200 |
| WebUI-прокси `POST /api/auth/login`, `GET /api/auth/me` | работают, роли/имя отдаются |

Создана рабочая БД `manager/dcap.db` (init_db.py). SID получен из SDDL `objectSid` тестового пользователя (Samba отдаёт строкой): `S-1-5-21-2752844453-1061204920-2611213393-1106`.

### Не проверено / ограничения

- **SPNEGO (Windows Integrated Auth):** python-модуль `spnego` не установлен (в логе: «spnego not installed, Windows Auth disabled»), поэтому эта ветка не тестировалась; парольный AD-поток покрыт полностью.
- **Живой цикл аудит-агента:** права переданы напрямую через `POST /api/audit/permissions`, реальный запуск агентов (Windows/Linux) в этот прогон не входил.
- `config/access_config.json` содержит тестовый пароль — предназначен только для локальной тестовой инфраструктуры (как и `docker-compose.ad.yml`).

---

## Команда коммита

На ветке `feature/day_33_ad_integration`:

```powershell
git add -A
git commit -m "feat: день 33 — Active Directory интеграция + RBAC WebUI"
```

(Замечание: удалённый `dump.md` — служебный scratch-файл, не относится к фиче; включён в коммит для чистоты дерева.)
