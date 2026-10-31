# 4. Аутентификация (local / hybrid / windows_integrated) + Active Directory

> Админ-руководство, раздел 04. Администратор DCAP.
> Версия документа: актуально для v3.13.8.

---

## 4.1 Режимы аутентификации

DCAP поддерживает три режима аутентификации (конфиг `manager/config/config.json`,
секция `auth`, env `AUTH_MODE`):

| Режим | Описание | Когда использовать |
|-------|----------|--------------------|
| `local` | JWT + Bcrypt, встроенные пользователи | Разработка, изолированные инсталляции |
| `hybrid` | Сначала SPNEGO → затем явный AD (пароль) → затем local JWT | Тестовый/промежуточный контур с AD, fallback на локальных пользователей |
| `windows_integrated` | Только SPNEGO / AD-учётные записи | Production с Active Directory |

Роли (модель RBAC): `admin`, `viewer`, `auditor`, `scanner`. Дефолтный `admin`
создаётся при старте (`db/init_roles.py`, пароль по умолчанию `admin/admin123` —
**смените**).

## 4.2 Запуск AD-контроллера домена (Samba AD DC)

С **v3.13.8** AD-сервис встроен в основной `docker-compose.yml` как profile `ad`.
Отдельный файл `docker-compose.ad.yml` удалён (справочная копия — `docker-compose.ad.yml.example`).

### Запуск

```bash
# Обычный стек (без AD)
docker compose up -d

# С AD-контроллером — включается только сервис dcap-ad-dc
docker compose --profile ad up -d

# Оба варианта агентов (S3/MinIO) — отдельный profile agents
docker compose --profile agents up -d
# Всё вместе:
docker compose --profile agents --profile ad up -d
```

Параметры домена (по умолчанию, можно переопределить в сервисе):

| Параметр | Значение |
|----------|----------|
| Realm | `SAMDOM.EXAMPLE.COM` |
| NetBIOS domain | `SAMDOM` |
| Админ домена | `administrator` / `Passw0rd` |
| DNS forwarder | `8.8.8.8` |
| Host-порты | LDAP `389`, LDAPS `636`, DNS `1353(53)`, SMB `1445(445)`, Kerberos `88/464`, GC `3268/3269` |

> **Порт 53 на host может быть занят** (DNS Windows) — наружу DNS проброшен на
> `1353`, внутри docker-сети доступен стандартный `53`.

### DNS внутри docker-сети

Сервис `samba-ad-dc` имеет **network aliases** `dcap.local` и `dc1.dcap.local`
на сети `dcap-network`. Поэтому Manager получает AD-контроллер по имени
`dcap.local` без настройки extra_hosts:

```bash
docker exec dcap-manager getent hosts dcap.local
# 172.19.0.x  dcap.local
```

LDAP URI для интеграции: `ldap://dcap.local:389` (LDAPS `ldap://dcap.local:636`).

### Остаточные контейнеры от старой схемы

Если раньше использовался `docker compose -f docker-compose.ad.yml up -d`
(до v3.13.8), контейнер `dcap-ad-dc` и тома `samba_data` уже созданы. Перед
обновлением:

```bash
docker compose -f docker-compose.ad.yml down        # удалить старый проект
# или точечно:
docker rm -f dcap-ad-dc
docker compose --profile ad up -d                    # пересоздать по-новому (тома samba_data сохраняются)
```

### Тестовые данные AD

```bash
python scripts/init_ad_test_data.py
```

Создаёт группы/пользователей для проверки маппинга AD-группы → роли:

| Группа | Роль |
|--------|------|
| `DCAP_Admins` | `admin` |
| `DCAP_Auditors` | `auditor` |
| `DCAP_Scanners` | `scanner` |

## 4.3 Подключение Manager к AD

Секция конфига `manager/config/config.json`:

```json
{
  "auth": {
    "mode": "hybrid",
    "ad": {
      "server": "dcap.local",
      "port": 389,
      "use_ssl": false,
      "domain": "SAMDOM.EXAMPLE.COM",
      "base_dn": "DC=SAMDOM,DC=EXAMPLE,DC=COM",
      "service_account": "CN=administrator,CN=Users,DC=SAMDOM,DC=EXAMPLE,DC=COM",
      "service_password": "Passw0rd",
      "group_mapping": {
        "DCAP_Admins": "admin",
        "DCAP_Auditors": "auditor",
        "DCAP_Scanners": "scanner"
      }
    }
  }
}
```

Альтернативно через env: `AUTH_MODE=hybrid`, `AD_SERVER`, `AD_PORT`, `AD_DOMAIN`,
`AD_BASE_DN`, `AD_SERVICE_ACCOUNT`, `AD_SERVICE_PASSWORD`.

Порядок проверки в `hybrid`-режиме (`manager/src/auth/manager.py`):
1. SPNEGO (Kerberos/NTLM, Windows Integrated Auth)
2. Явный логин по паролю через LDAP (`ad_auth.py`, bind `ldap3.SIMPLE`)
3. Локальный пользователь/пароль (JWT + Bcrypt)
4. Кэшированный AD-пользователь (`ADCache`, Redis + memory-fallback)

### 4.3.1 JWT TTL и cookie (BUG-038 / BUG-042)

TTL токенов задаётся env и не захардкожен в config.json:

```
JWT_ACCESS_TTL_MINUTES=1440   # 24 часа
JWT_REFRESH_TTL_DAYS=7
```

HttpOnly-cookie (`access_token`/`refresh_token`) шлются с `Secure`-флагом
только при `AUTH_COOKIE_SECURE=true` (обязательно за HTTPS). Локальная
разработка на `http://127.0.0.1` — флаг `false` (по умолчанию), иначе
браузер не пришлёт cookie обратно.

Refresh-токен используется только в `/api/auth/refresh` (BUG-039) и
отзывается (blacklist jti) при каждой ротации и при `/logout` (BUG-041;
черный список — Redis `jwt-blacklist:*`, fail-open без Redis).

## 4.4 Управление пользователями и ролями (RBAC WebUI)

После входа под `admin` доступны страницы:

- **Пользователи** (`/users`) — CRUD: создание, `PUT /status` (активен),
  `PUT /roles` (привязка ролей), удаление (кроме себя).
- **Роли** (`/roles`) — CRUD, системные роли удалять нельзя; поле `ad_group`
  задаёт маппинг AD-группы на роль.
- **Настройки** (`/settings`) — смена пароля, просмотр режима auth.

API: `GET/POST /api/auth/users`, `GET/PUT/DELETE /api/auth/users/{id}`,
`PUT /api/auth/users/{id}/status`, `PUT /api/auth/users/{id}/roles`,
`GET/POST/PUT/DELETE /api/auth/roles`.

## 4.5 Проверка работоспособности

```bash
# 1. Стек здоров
docker compose ps | Select-String "manager|ad-dc"   # оба healthy

# 2. DNS до AD
docker exec dcap-manager getent hosts dcap.local    # 172.19.0.x

# 3. Режим auth
curl -s http://localhost:8000/api/auth/mode | ConvertFrom-Json

# 4. Логин AD-пользователем (hybrid)
$body = '{"username":"administrator","password":"Passw0rd"}'
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/auth/login -Body $body -ContentType "application/json"
```

## 4.6 Troubleshooting

| Симптом | Причина | Решение |
|---------|---------|---------|
| `dcap.ad.login_error` / bind fail | service account неверен / LDAP недоступен | проверить `AD_SERVER`, порт `389`, имя контейнера `dcap-ad-dc`, `getent hosts dcap.local` |
| Samba слушает только loopback | баг `samba-domain-provision` (eth0@ifN) | уже исправлен в compose `command` (`sed` на `eth0`) |
| `docker compose up -d` перезапускает redis | старый `docker-compose.ad.yml` имел свой `redis` | обновиться на v3.13.8; `docker rm -f dcap-ad-dc`; redis живёт только в основном compose |
| SPNEGO не работает в браузере | Режим `windows_integrated` требует Kerberos на клиенте | использовать `hybrid` или прямой credentials |
| Контейнер `dcap-ad-dc` не появляется | Запущен `docker compose up -d` без `--profile ad` | `docker compose --profile ad up -d` |