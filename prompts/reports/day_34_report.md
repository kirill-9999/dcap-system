# Отчёт: День 34 — Безопасность (mTLS, шифрование, секреты)

**Дата:** 02.09.2026
**ТЗ:** `prompts/tz/day_34_security.md`
**Роль:** Кодер
**Версия:** v3.0.0

---

## Резюме

Реализована **безопасность на всех уровнях DCAP**: взаимная аутентификация через **mTLS** (Manager ↔ WebUI ↔ агенты ↔ сканер), **CertificateManager** (генерация/ротация/CRL-отзыв сертификатов), **SecretsManager** (Docker Secrets → env → default), общие утилиты и константы безопасности в `shared/`, единый `docker-compose.yml` с Docker Secrets и томами для сертификатов, а также документация по безопасности (`SECURITY.md`, `docs/security_checklist.md`).

> **Архитектурное решение (согласовано с пользователем):**
> - **Режим mTLS `relaxed` (по умолчанию)** — если сертификаты не найдены, компоненты работают на plain HTTP с предупреждением в логе. Режим `strict` — Manager не стартует без PKI. Это сохраняет обратную совместимость с локальной dev-средой (без TLS).
> - **`docker-compose.yml` создан как новый общий compose** (Manager + WebUI + Redis + secrets). AD-тестовый `docker-compose.ad.yml` (день 33) не трогался.
> - **Скрипты генерации/ротации только на Python** (cross-platform через `cryptography`), без bash-обёрток по требованию пользователя.

---

## Ключевые решения по коду

- **mTLS проверка** для machine-эндпоинтов (агенты/сканер) в `AuthMiddleware`: извлекает клиентский CN из TLS-handshake. В `relaxed`-режиме при отсутствии сертификата или клиентского cert запрос пропускается; в `strict` — отклоняется (401).
- **SSL-контекст uvicorn** создаётся в `run_manager.py` из `manager/config/config.json` (секция `security`): `mtls_enabled`, `mtls_strict`, `certs_dir`. Шифры — `ECDHE+AESGCM:ECDHE+CHACHA20`, TLS 1.2+.
- **Все senders агентов** (Windows/Linux/S3) и **ManagerClient сканера** поддерживают опциональный client-cert через `requests.Session.cert/verify`. При отсутствии путей — plain HTTP с warning.
- **SecretsManager** единообразно читает секреты с приоритетом Docker Secrets → env → default, с кэшированием.

---

## Выполненная работа

### 1. Инфраструктура безопасности (NEW)

| Файл | Назначение |
|------|-----------|
| `manager/src/core/__init__.py` | Пакет core |
| `manager/src/core/security.py` | **CertificateManager**: загрузка серверного сертификата + CA, создание `SSLContext` (сервер/клиент), `verify_client_cert`, `is_revoked` (CRL), режимы relaxed/strict |
| `manager/src/core/secrets.py` | **SecretsManager**: приоритет Docker Secrets → env → default, `get`/`get_required`/`load_all`, кэш, ленивый синглтон `get_secrets_manager()` |
| `shared/cert_utils.py` | Общие утилиты: `generate_ca_keypair`, `generate_component_keypair`, `extract_cn/serial`, `validate_certificate` (подпись CA + срок + CRL), `is_certificate_revoked`, `fingerprint_hex` |
| `shared/security.py` | Константы: `MIN_TLS_VERSION`, `ALLOWED_CIPHERS`, TTL сертификатов, размеры ключей, `DCAP_COMPONENTS`, `COMPONENT_SANS` |

### 2. Генерация и ротация сертификатов (NEW)

- **`scripts/generate_certs.py`** — чистое Python (cryptography), генерирует CA (4096-bit, 10 лет) + серверные компоненты (manager, webui, agent-windows, agent-linux, agent-s3, scanner) (2048-bit, 1 год) + пустой CRL. Флаги `--certs-dir`, `--force`. Устанавливает `BasicConstraints`, `KeyUsage`, **SKI/AKID** (иначе клиенты отклоняют серверный сертификат ошибкой `Missing Authority Key Identifier`), SAN для manager/webui.
- **`scripts/rotate_certs.py`** — ротация: backup старых в `certs/backup/<timestamp>/`, генерация новых с новым serial, CRL-отзыв. Флаги `--component`.

### 3. Manager — mTLS-интеграция

- **`manager/src/auth/middleware.py`** — `AuthMiddleware` получил `cert_manager`; `_is_machine_endpoint`, `_check_mtls` (извлекает CN из `ssl_object.getpeercert()`); в области `dispatch` для machine-эндпоинтов выполняется mTLS-проверка, `request.state.client_cert_cn` заполняется (в т.ч. для всех запросов).
- **`manager/src/main.py`** — создаёт `CertificateManager` из секции `security` конфига, логирует статус mTLS, передаёт `cert_manager` в middleware.
- **`run_manager.py`** — при активном mTLS умеет запускать uvicorn с `ssl_certfile/keyfile/ca_certs`, `ssl_cert_reqs=ssl.CERT_OPTIONAL` (relaxed) и заданными шифрами.

### 4. Агенты и сканер — поддержка mTLS

- **`audit-agent-windows/sender.py`**, **`audit-agent-linux/sender.py`** — `Sender` принимает `cert_path/key_path/ca_path`, задаёт `session.cert/verify`; при отсутствии — plain HTTP.
- **`audit-agent-windows/main.py`**, **`audit-agent-linux/main.py`** — передают mTLS-пути из конфига в Sender.
- **`audit-agent-s3/src/sender.py`** — добавлены mTLS-пути (`config.manager.cert_path/key_path/ca_path`) поверх существующей JWT-поддержки.
- **`audit-agent-s3/config/config.json`** — добавлены `cert_path/key_path/ca_path` (с env-плейсхолдерами `MTLS_*`).
- **`scanner/src/managed_scanner.py`** (ManagerClient) + **`scanner/src/config_loader.py`** (ClientConfig `cert_path/key_path/ca_path`) + **`scanner/config/scanner_config.json`** — поддержка mTLS.

### 5. Docker Compose + Secrets

- **`docker-compose.yml` (NEW, корень)** — Manager + WebUI + Redis; Docker Secrets (`jwt_secret_key`, `db_password`, `ad_service_password`), тома для certs, env `MTLS_*`, `JWT_SECRET_KEY_FILE/DB_PASSWORD_FILE` и т.д.
- **`webui/Dockerfile` (NEW)** — минимальный образ WebUI (запуск `webui.main:app`).
- **`secrets/.gitkeep` (NEW)** — директория Docker Secrets (сами `.txt`-файлы в .gitignore).

### 6. Зависимости и конфиг

- **`requirements.txt`** — `cryptography>=42.0.0`.
- **`.env.example`** — секции `DB_PASSWORD`, `REDIS_PASSWORD`, `MTLS_ENABLED/STRICT/CERTS_DIR`.
- **`.gitignore`** — `certs/`, `*.crt/*.key/*.csr/*.pem`, `secrets/*.txt` (+`.key`), `!secrets/.gitkeep`.
- **`manager/config/config.json`** — секция `security` `{mtls_enabled:false, mtls_strict:false, certs_dir:certs}` (по умолчанию mTLS выключен, relaxed).

### 7. Документация

- **`SECURITY.md`** — политика безопасности: mTLS, секреты, шифрование буферов агентов (EFS/BitLocker/LUKS/eCryptfs/SSE-S3), БД, сеть, реагирование на компрометацию, ответственное раскрытие.
- **`docs/security_checklist.md`** — чеклист для production.

---

## Тестирование

```
python -m pytest manager/tests/test_security.py -v   # 16 passed
python -m pytest manager/tests/test_security.py manager/tests/test_ad_permissions.py manager/tests/test_auth_ad.py -q   # 36 passed
```

**`manager/tests/test_security.py` (NEW, 16 тестов):**
- `cert_utils`: извлечение CN, генерация CA, подпись компонента CA, валидация с правильной/чужой CA.
- `CertificateManager`: relaxed без сертификатов (is_available False), strict (FileNotFoundError), создание server SSL-контекста (TLS 1.2+, verify_mode), `verify_client_cert`, `is_revoked` с реальным CRL.
- `SecretsManager`: env-приоритет, default, Docker-приоритет над env, `get_required` (ValueError), кэширование, `load_all`, синглтон.

### E2E-проверка mTLS (реальный Manager)

Сгенерирована PKI (`scripts/generate_certs.py` → `certs/`), в `manager/config/config.json` включён `mtls_enabled:true`, Manager перезапущен:

- Лог: `mTLS is active for Manager`, `Uvicorn running on https://127.0.0.1:8000`.
- **`GET https://127.0.0.1:8000/api/health`** (без клиентского сертификата, relaxed) → **200**.
- **`GET ...`** (с client cert agent-s3, строгая валидация CA — `verify=ca.crt`) → **200**.
- **`POST /api/audit/agents/register`** (machine endpoint + client cert agent-s3) → **200** (`agent_id=4`).

> **Найдено и исправлено:** первоначально строгая валидация CA клиентом отклонялась `Missing Authority Key Identifier` из-за отсутствия AKID/SKI у сгенерированных сертификатов. Добавлены `SubjectKeyIdentifier`/`AuthorityKeyIdentifier` в `generate_ca_keypair`/`generate_component_keypair` — после этого валидация CA прошла.
>
> curl на Windows (schannel) не может импортировать PEM как client-cert — для mTLS-теста клиента использован `requests.Session` (OpenSSL-бэкенд).

После проверки Manager возвращён в режим по умолчанию (`mtls_enabled:false`, plain HTTP) и оставлен рабочим на :8000; WebUI :8001 также работает.

### checked/чистота

- `python -m py_compile shared/cert_utils.py scripts/generate_certs.py scripts/rotate_certs.py manager/src/core/security.py manager/src/core/secrets.py` — OK (без импорта сторонних).
- `manager.src.main` импортируется без ошибок (с/без mTLS).
- `docker compose -f docker-compose.yml config` — валиден.
- Генерация/ротация сертификатов протестированы на диске.

---

## Файлы

**NEW:**
- `manager/src/core/__init__.py`, `manager/src/core/security.py`, `manager/src/core/secrets.py`
- `shared/cert_utils.py`, `shared/security.py`
- `scripts/generate_certs.py`, `scripts/rotate_certs.py`
- `docker-compose.yml`, `webui/Dockerfile`, `secrets/.gitkeep`
- `SECURITY.md`, `docs/security_checklist.md`
- `manager/tests/test_security.py`
- `prompts/reports/day_34_report.md` (этот отчёт)
- Перенесён ТЗ: `prompts/archive/day_33_ad_integration.md` (удалён из `prompts/tz/`)

**Modified:**
- `requirements.txt` (+cryptography)
- `.env.example`, `.gitignore`
- `manager/config/config.json` (секция `security`)
- `manager/src/main.py`, `manager/src/auth/middleware.py`, `run_manager.py`
- `audit-agent-windows/sender.py`, `audit-agent-windows/main.py`
- `audit-agent-linux/sender.py`, `audit-agent-linux/main.py`
- `audit-agent-s3/src/sender.py`, `audit-agent-s3/config/config.json`
- `scanner/src/managed_scanner.py`, `scanner/src/config_loader.py`, `scanner/config/scanner_config.json`

---

## Запуск (ручное тестирование)

```powershell
# 1. Установка зависимости
pip install -r requirements.txt   # + cryptography

# 2. Генерация сертификатов
python scripts/generate_certs.py

# 3. Включение mTLS (manager/config/config.json)
#    "security": { "mtls_enabled": true, "mtls_strict": false, "certs_dir": "certs" }

# 4. Запуск Manager (mTLS -> https://127.0.0.1:8000)
python run_manager.py

# 5. Проверка mTLS (Python requests, строгая валидация CA)
python -c "import requests; s=requests.Session(); s.verify='certs/ca/ca.crt'; s.cert=('certs/agents/agent-s3.crt','certs/agents/agent-s3.key'); print(s.get('https://127.0.0.1:8000/api/health').text)"

# 6. WebUI (plain HTTP, процентируется)
python run_webui.py

# 7. Ротация сертификатов
python scripts/rotate_certs.py --component manager
```

**Примечание:** `certs/` и `secrets/*.txt` в `.gitignore` — не коммитятся. Для production сгенерируйте PKI в защищённом хранилище и подключите Docker Secrets.

---

## Команда коммита

На ветке `feature/day_34_security`:

```powershell
git checkout -b feature/day_34_security
git add -A
git commit -m "feat: День 34 — Безопасность (mTLS, секреты, документация)

mTLS:
- Генерация сертификатов (scripts/generate_certs.py, cryptography)
- CertificateManager (Manager, relaxed/strict)
- mTLS поддержка во всех агентах и сканере (requests.Session cert/verify)
- CRL для отзыва сертификатов (shared/cert_utils.py)
- Middleware для проверки mTLS (AuthMiddleware._check_mtls)

Секреты:
- SecretsManager (manager/src/core/secrets.py, env + Docker Secrets)
- docker-compose.yml с Docker Secrets + certs тома
- .env.example обновлён

Документация:
- SECURITY.md — политика безопасности
- docs/security_checklist.md — чеклист для production"
```

(Замечание: `docker-compose.yml` — по согласованию с пользователем новый общий compose. Docker-образы manager/webui для локального запуска не востребованы — запуск через run_all.py.)

---

## Обратная связь архитектору

- **mTLS/relaxed** покрывает dev и prod: в production при подложенных сертификатах автоматически переходит на HTTPS+mTLS; в dev без PKI работает на plain HTTP.
- **Агентская аутентификация** (JWT/API-keys) для machine-эндпоинтов остаётся TODO дня 35–37 (флаг в middleware), mTLS даёт дополнительный уровень.
- **Строгая проверка CA клиентом** работает после добавления SKI/AKID в сертификаты (важно — иначе `Missing Authority Key Identifier`).
- **curl на Windows** не импортирует PEM client-cert (schannel) — документировано; для агентов mTLS используется Python `requests`.