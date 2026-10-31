# Отчёт: День 30 — Гибридная аутентификация (JWT + Windows Integrated Auth)

**Дата:** 30.08.2026
**ТЗ:** `prompts/tz/day_30_authentication.md`
**Роль:** Кодер
**Версия:** v3.1.0

---

## Резюме

Внедрена гибридная аутентификация для Manager и WebUI: режимы `local` / `hybrid` / `windows_integrated`, JWT (HS256) + Bcrypt для локальных пользователей, SPNEGO-stub без Active Directory, роли `admin`/`viewer`/`auditor`/`scanner`. Manager защищает `/api/*` в middleware (AuthMiddleware), публичные и machine-эндпоинты (агенты/сканер) пропускаются без JWT. WebUI получил страницу `/login`, хранение JWT в localStorage и отправку через заголовок `Authorization: Bearer` (прокси форвардит в Manager). Исправлен выявленный при тестировании баг: страницы WebUI использовали голые `fetch` без `Authorization` → Manager возвращал 401 → пустые таблицы и «Authentication required» при добавлении ресурса; все страницы переведены на `api.get/api.post` с подстановкой токена.

---

## Выполненная работа

### 1. Auth-модуль Manager (`manager/src/auth/`)

- **`modes.py`** — перечисление режимов `local`/`hybrid`/`windows_integrated`.
- **`models.py`** — SQLAlchemy-модели `User` (bcrypt-хэш пароля, `auth_source`, `is_active`) и `Role` + связь `user_roles` (many-to-many).
- **`jwt.py`** — `JWTManager` (HS256): создание/валидация access- и refresh-токенов, `sub`=id пользователя, `roles`.
- **`local_auth.py`** — `LocalAuthenticator`: проверка логина/пароля через Bcrypt, работа с JWT.
- **`windows_auth.py`** — `WindowsAuthenticator`: SPNEGO-stub с mock без Active Directory (AD отсутствует — заглушка).
- **`manager.py`** — `AuthManager`: выбор активного режима, делегирование аутентификации, CRUD пользователей и ролей.
- **`schemas.py`** — Pydantic-схемы запросов/ответов (примечание: `EmailStr` в ответах фактически не используется — пакет `email-validator` не требуется).
- **`dependencies.py`** — зависимости `require_auth`/`require_admin`/`require_viewer`/`require_auditor`/`require_scanner` (проверка JWT + ролей).
- **`rate_limit.py`** — `RateLimiter` (5 попыток входа в минуту).
- **`middleware.py`** — `AuthMiddleware`: защита `/api/*`, публичный `/api/auth/mode` и machine-список (`/api/scanner*`, `/api/audit/agents/*`, `/api/audit/events`) пропускаются без JWT.
- **`router.py`** — эндпоинты `POST /api/auth/login`, `/refresh`, `/logout`, `/me`, `/change-password`, `GET /api/auth/mode`, `GET /api/auth/check`, админ-роуты `/api/auth/users`, `/api/auth/users/{id}`.

### 2. Установочные/ДБ-файлы

- **`manager/src/db/init_roles.py`** — при старте создаёт роли (`admin`/`auditor`/`scanner`/`viewer`) и дефолтного пользователя `admin/admin123` (обязательно сменить!).
- **`manager/src/db/session.py`** — `init_db()` импортирует auth-модели → таблицы `users`/`roles`/`user_roles` создаются автоматически.
- **`manager/src/config.py`** — загрузчик конфига + env-приоритет (`_resolve_env`: подстановки `AUTH_MODE`, `JWT_SECRET_KEY`, `AD_*`).
- **`manager/config/config.json`** — добавлена секция `auth` (mode, secret, AD-поля).

### 3. Интеграция в Manager (`manager/src/main.py`)

- `AuthManager` инициализируется из конфига, `set_auth_manager` в app.state.
- `app.add_middleware(AuthMiddleware)` — защита `/api/*`.
- Подключён `auth_router`, в startup-event — `init_db` + `init_roles_and_admin`.
- Версия поднята до 3.0.0.

### 4. WebUI login-флоу

- **`webui/static/js/auth.js`** — `Auth`: JWT в localStorage (`dcap_access_token`), `authHeaders()` → `Authorization: Bearer`, методы `login`/`logout`/`me`/`check`.
- **`webui/static/js/api.js`** — `get`/`post`/`delete` инжектят `Auth.authHeaders()` во все запросы.
- **`webui/templates/login.html`** — страница входа (не наследует base.html — нет сайдбара и петли редиректа).
- **`webui/templates/base.html`** — подключение `auth.js`/`api.js` (в этом порядке), кнопка выхода, `Auth.check()` на `DOMContentLoaded` (редирект на /login при 401), футер v3.0.0.
- **`webui/main.py`** — маршрут `/login`.
- **`webui/api/routes.py`** — прокси форвардит заголовок `Authorization` и куки `access_token`/`refresh_token` в Manager.

### 5. Исправление бага «пусто везде / Authentication required» (найдено при тестировании)

Страницы `scanners.html`, `audit.html`, `catalog.html`, `findings.html`, `resources.html` вызывали API голым `fetch()` **без** заголовка `Authorization` → Manager (теперь защищён) возвращал `401` → пустые таблицы и «Authentication required» при добавлении ресурса. Переведены на `api.get`/`api.post` (подставляют токен):

- `scanners.html` — `/api/scanners`, `/api/audit/agents`
- `audit.html` — `/api/audit`, `/api/audit/agents`
- `catalog.html` — `/api/catalog`, `/api/catalog/stats`
- `findings.html` — `/api/findings`
- `resources.html` — `/api/resources/create` (POST), `/api/resources/{id}/scan` (POST), `/api/resources`

### 6. Зависимости и документация

- **`requirements.txt`** — добавлены `bcrypt>=4.0.1`, `PyJWT>=2.8.0`, `spnego>=0.11.0`, `pyspnego>=0.10.0` (PyJWT вместо python-jose, pyspnego/spnego по ТЗ).
- **`.env.example`** — новый: `AUTH_MODE`, `JWT_SECRET_KEY`, `AD_*`, `PYTHONUTF8`.
- **`AGENTS.md`** — обновлён: статус v3.1.0, релизы, раздел `manager/src/auth/`, примечание о перезапуске Manager.

---

## Верификация

- **py_compile** всех файлов auth + `main.py` + `manager/src/config.py` — 0 ошибок.
- **`temp/test_auth.py`** — 9/9: health, mode, 401 без токена, login admin/admin123, me (Bearer + cookie), users (admin), check, 401 wrong password; роли `['admin']` подтверждены.
- **`temp/test_webui_auth.py`** — полный end-to-end через прокси WebUI на изолированном Manager :8010: `/login` 200, login через прокси 200 + token, `/api/auth/me` 200, `/api/auth/users` 200 (1), 401 без токена, `/api/auth/mode` 200 → `local`. ALL PASSED.
- **Проверка после фикса бага (прокси :8001, токен Bearer)**: login 200; `/api/scanners` → `scanner-1 [active]`; `/api/resources` → count=1; без токена → 401. БД: `users`: admin(local), `roles`: admin/auditor/scanner/viewer, `user_roles`: (1,1).
- **Итог:** сервер, прокси и все страницы WebUI отдают данные с токеном; защита без токена работает (401).

---

## Итоговый чеклист

- [x] Auth-модуль Manager (`manager/src/auth/`): modes, models, jwt, local_auth, windows_auth, manager, schemas, dependencies, rate_limit, middleware, router
- [x] БД: `init_roles.py`, `session.py` (создание users/roles/user_roles), `config.py`, секция `auth` в конфиге
- [x] Интеграция в `main.py` (middleware + router + startup)
- [x] WebUI: `login.html`, `auth.js`, `api.js` (инъекция Bearer), `base.html` (защита + логин/логаут), маршрут `/login`, прокси форвардит Authorization
- [x] Исправлен баг 401 на страницах WebUI (голые fetch → api.get/api.post)
- [x] `requirements.txt` + `.env.example` обновлены
- [x] AGENTS.md обновлён (v3.1.0)
- [x] Верификация end-to-end (9/9 + webui-auth + прокси :8001)
- [x] Отчёт сохранён
- [x] ТЗ перемещено в `prompts/archive/`

---

## Примечания / известные ограничения

1. **Дефолтный admin** — `admin/admin123`. **Обязательно сменить!** Пароль хранится Bcrypt-хэшем; user создаётся в `init_roles.py`.
2. **Windows Integrated Auth** — SPNEGO-stub с mock (Active Directory в проекте отсутствует). Режим `hybrid` включает `local` + SPNEGO, `windows_integrated` — только SPNEGO.
3. **HttpOnly-cookie через прокси не работают** — в WebUI используется Bearer-заголовок из localStorage (это зафиксировано в AGENTS.md).
4. **Устаревший запущенный Manager** без auth-роутера возвращает 404 на `/api/auth/login`. После обновления кода Manager **обязательно перезапустить**.
5. **Браузерный кэш** — после обновления шаблонов/JS необходимо жёсткое обновление (Ctrl+Shift+R), т.к. старые JS могли остаться в кэше вкладки.
6. **`/api/auth/mode`** — публичный (без JWT) — используется login.html для определения режима.

---

## Команда коммита

```powershell
git add -A
git commit -F temp\commit_msg.txt
```

Сообщение коммита (`temp/commit_msg.txt`):
```
feat: гибридная аутентификация JWT + Windows Auth в Manager и WebUI (день 30)

- manager/src/auth/: modes, models (User/Role), jwt (HS256), local_auth (Bcrypt),
  windows_auth (SPNEGO-stub), manager (режимы local/hybrid/windows_integrated),
  schemas, dependencies (require_*), rate_limit, middleware, router (/api/auth/*)
- БД: db/init_roles.py (роли + admin), session.py (create users/roles/user_roles),
  config.py (env-приоритет), секция auth в manager/config/config.json
- main.py: AuthMiddleware защищает /api/* (public+машины пропускаются), auth-router,
  init_roles_and_admin в startup; версия v3.0.0
- WebUI: login.html, static/js/auth.js (JWT в localStorage + Bearer),
  api.js (инъекция Authorization), base.html (защита стр. + логин/логаут),
  маршрут /login, прокси форвардит Authorization
- фикс: страницы WebUI переведены с голых fetch на api.get/api.post (иначе 401)
  — scanners/audit/catalog/findings/resources.html
- requirements.txt: bcrypt, PyJWT, spnego, pyspnego; .env.example; AGENTS.md v3.1.0
```
