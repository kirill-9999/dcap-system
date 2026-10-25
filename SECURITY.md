# Политика безопасности DCAP System

## Поддерживаемые версии

| Версия | Поддерживается |
|--------|----------------|
| 3.x.x  | ✅ |
| 2.1.x  | ❌ |
| 2.0.x  | ❌ |
| 1.x.x  | ❌ |

---

## 🚨 Ответственное раскрытие уязвимостей

Если вы обнаружили уязвимость в DCAP System:

1. **НЕ создавайте публичный Issue**
2. Напишите на email: **security@dcap.local** (замените на реальный)
3. Опишите:
   - Версию DCAP (`curl http://localhost:8000/api/health`)
   - Компонент (Manager, WebUI, Scanner, агент)
   - Шаги воспроизведения
   - Потенциальное влияние
4. Мы ответим в течение **48 часов**
5. Публичное раскрытие — **после выпуска исправления**

**PGP-ключ:** (опционально, добавьте fingerprint)

---

## 🔐 Рекомендации по безопасности

### 1. mTLS (взаимная аутентификация)

**Все компоненты должны использовать mTLS в production.**

| Параметр | Значение |
|----------|----------|
| Генерация сертификатов | `python scripts/generate_certs.py` |
| Ротация | Каждые 90 дней (`python scripts/rotate_certs.py`) |
| Отзыв | CRL |
| Режим `relaxed` | Работает на plain HTTP при отсутствии сертификатов (dev) |
| Режим `strict` | Manager **не стартует** без PKI (production) |

**Включение** (секция `security` в `manager/config/config.json`):

```json
{
    "security": {
        "mtls_enabled": true,
        "mtls_strict": false,
        "certs_dir": "certs"
    }
}
Env:

MTLS_ENABLED=true

MTLS_STRICT=true (production)

CERTS_DIR=certs

Компоненты, поддерживающие mTLS:

Manager ↔ WebUI

Manager ↔ Scanner

Manager ↔ агенты (Windows, Linux, S3)

**Проверка отзыва (CRL) — v3.13.28:**

До v3.13.28 CRL была сгенерирована, но фактически **не проверялась**: ни на
TLS-уровне, ни в middleware. Отозванный сертификат принимался как валидный.

| Уровень | Механизм |
|---------|----------|
| TLS | `ssl.VERIFY_CRL_CHECK_LEAF` в `get_server_ssl_context()` |
| Middleware | `_check_mtls()`: `getpeercert(binary_form=True)` → `is_revoked(der)` |

Отозванный клиентский сертификат получает **401**. Конвертация DER↔PEM —
`_to_pem()` в `manager/src/core/security.py`.

**Machine-эндпоинты — v3.13.28:**

`/api/scanner*`, `/api/audit/agents/*`, `/api/audit/events` **не являются
публичными**. Раньше они попадали в список публичных, и mTLS-проверка для них
не выполнялась. Сейчас: JWT не требуется (это machine-вызовы), но клиентский
сертификат проверяется, а его CN попадает в `request.state.client_cert_cn`.
В режиме `strict` запрос без сертификата отклоняется.

**Путь к PKI в контейнере — v3.13.28:**

Manager монтирует `./certs:/app/certs:ro` (каталог, куда пишет
`scripts/generate_certs.py`). Прежний mount `./manager/certs` приводил к
тому, что при `mtls_enabled=true` Manager не находил PKI. WebUI mTLS не
использует и монтируется без сертификатов.

2. Шифрование находок (Findings Refactor)
Модель: гибрид — маскированное (по умолчанию) + зашифрованное (AES-256-GCM).

Аспект	Решение
Алгоритм	AES-256-GCM (AEAD)
Ключ шифрования	ENV FINDINGS_ENCRYPTION_KEY (base64, 32 байта)
HMAC-ключ	ENV FINDINGS_HMAC_KEY (base64, ≥32 байта)
Key ID	ENV FINDINGS_KEY_ID (для ротации)
Fingerprint	HMAC-SHA256 (защита от brute-force)
Legacy-режим	SHA-256 (НЕ MD5 — MD5 криптографически сломан)
По умолчанию	Маскированное
Расшифровка	Только роль Auditor (или Admin), с записью в audit_logs
Аудит	Каждый reveal логируется (action="finding_revealed")
Передача ключей — только через ENV (Docker Secrets, файлы, Vault — не используются в v3.0.0).

Генерация ключей:

bash
python scripts/generate_findings_keys.py
# → secrets/findings_encryption_key
# → secrets/findings_hmac_key
# → secrets/findings_key_id
Ротация ключей:

Сгенерировать новый ключ → новый key_id

Перешифровать все существующие находки (reencrypt_findings.py)

Обновить ENV Manager и всех Scanner

Опционально — фоновая перешифровка (v3.1.0+)

⚠️ ВАЖНО:

Ключи НЕ хранятся в БД

Ключи НЕ коммитятся в git (secrets/ в .gitignore)

При потере ключа зашифрованные находки невосстановимы (крипто-шреддинг)

Ключи должны быть ИДЕНТИЧНЫ на Manager и всех Scanner

Fail-fast: Scanner не стартует без ключей (DCAP_ALLOW_LEGACY_SCANNER=false)

Модель владения ключами
Артефакт	Владелец	Где хранится
Мастер-копия	Manager	ENV (Docker Compose / systemd)
Резервная копия	Инфра-команда	Offline / защищённое хранилище (ОТДЕЛЬНО от БД!)
Рабочая копия (N сканеров)	Scanner	ENV (systemd / Windows-служба)
key_id	Manager	ENV + в БД (findings.encryption_key_id)
Принципы:

Один набор ключей на инсталляцию (v3.0.0). Компромисс одного Scanner = компромисс всех находок.

Manager — единственная точка ротации. При ротации все сканеры должны получить новый ключ до старта.

Ключи не покидают доверенную зону по незащищённым каналам.

key_id — не секрет. Публичен, помогает сопоставить находку с ключом.

Fail-fast. Scanner без ключей — не стартует.

При потере ключа — зашифрованные находки невосстановимы.

v3.1.0+: планируется per-scanner key (scanner_id → key_id) — снижение последствий компромисса одного Scanner.

Зачем ключи на Scanner, если есть mTLS?
mTLS защищает канал. Шифрование защищает данные в состоянии покоя.

Угроза	mTLS	Ключи на Scanner
Перехват трафика	✅	✅ (двойная защита)
Компромисс Manager (RAM, логи, core dump)	❌	✅
Компромисс БД (кража диска, дамп)	❌	✅
Утечка бэкапа БД	❌	✅
Компромисс одного Scanner	❌	⚠️ только этот
Debug-логи Manager	❌	✅
Модель DCAP: Scanner шифрует PII на стороне сканирующего хоста — Manager никогда не видит plaintext (кроме короткого момента reveal). Это:

Защищает от компромисса Manager (RAM, логи, core dumps).

Защищает бэкапы БД.

Соответствует 152-ФЗ / GDPR / PCI DSS (PII только в шифротексте).

Оставляет единственный путь к plaintext — reveal (Auditor+, с аудитом).

mTLS — необходимый, но недостаточный слой.

Что маскируется:

Категория	Маска	Шифрование
phone	+7***123-45-67	✅
email	iv***@example.com	✅
api_key / aws_key	AKIA***	✅
password	***	✅
token / jwt_token	eyJ***	✅
ssh_key / github_token / slack_token	***	✅
database_url / basic_auth	***	✅
passport	12** ******	✅
snils / inn	***	✅
credit_card	**** **** **** 1234	✅
person	не маскируется	❌
Полная процедура: docs/admin-guide/05-security.md §3.

3. Хранение секретов
Никогда не храните секреты в коде

Production: ENV (Docker Compose / systemd / Kubernetes Secrets)

Dev: .env (не коммитить!)

Регулярная ротация паролей и ключей (90 дней)

Секреты проекта:

Секрет	Назначение	ENV
JWT	Подпись JWT	JWT_SECRET_KEY
DB	Пароль PostgreSQL	POSTGRES_PASSWORD / DATABASE_URL
AD	Пароль AD-сервиса	AD_SERVICE_PASSWORD
Findings: encryption	AES-256-GCM	FINDINGS_ENCRYPTION_KEY
Findings: HMAC	HMAC-SHA256	FINDINGS_HMAC_KEY
Findings: key ID	Ротация	FINDINGS_KEY_ID
Redis	Пароль	REDIS_PASSWORD
.gitignore — обязательные записи:

text
secrets/
.env
*.key
*.crt
⚠️ Известное ограничение ENV: env видны в ps, /proc/<pid>/environ, docker inspect. Митигация — ограничить доступ к хосту.

4. Аутентификация и RBAC
Режимы:

Режим	Описание
local	JWT + Bcrypt (разработка)
hybrid	SPNEGO → fallback JWT (тестирование)
windows_integrated	Только SPNEGO (production AD)
Роли (RBAC):

Роль	Права	AD группа
Admin	Полный доступ, удаление	DCAP_Admins
Auditor	Аудит, reveal находок, FP	DCAP_Auditors
Scanner	Запуск сканирования	DCAP_Scanners
Viewer	Только чтение (маскированное)	все остальные
Рекомендации:

Смените пароль admin/admin123 сразу после установки

Используйте сложные пароли (≥12 символов)

Включите AD-интеграцию в production

Минимизируйте количество Admin-пользователей

Регулярно проверяйте список пользователей (GET /api/auth/users)

5. Rate-limit
RateLimitMiddleware защищает от брутфорса и DoS:

Параметр	Значение (по умолчанию)
Лимит	300 запросов/мин на IP
Исключение	/api/health
Хранилище	Redis (in-memory fallback)
Ответ	429 Too Many Requests
Настройка (секция redis.rate_limit в config.json):

json
{
    "redis": {
        "rate_limit": {
            "max_requests": 300,
            "window_seconds": 60
        }
    }
}
Env: RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS

6. Шифрование буферов агентов
Агенты буферизуют события при недоступности Manager. Буферы содержат чувствительные данные (пути, имена пользователей).

Windows Agent:

EFS (Encrypting File System) для data/buffer/

BitLocker для всего диска

Linux Agent:

LUKS для шифрования диска

eCryptfs или fscrypt для data/buffer/

S3 Agent:

SSE-S3 или SSE-KMS для S3-бакетов с логами

Клиентское шифрование для буфера

7. База данных (PostgreSQL)
TLS для подключения к БД (sslmode=require)

Шифрование на уровне диска

Сетевые политики (firewall — только Manager)

Регулярное резервное копирование (pg_dump)

Партиционирование audit_logs по месяцам (уже реализовано)

Отдельный пользователь для Manager (не postgres)

Аудит доступа к БД (логи)

Проверка:

bash
# Проверить, что PG слушает только localhost/внутреннюю сеть
ss -tlnp | grep 5432

# Проверить SSL
psql "postgresql://dcap@localhost/dcap?sslmode=require" -c "SHOW ssl;"
8. Redis
Пароль обязателен (REDIS_PASSWORD)

Не доступен извне (только внутренняя сеть)

TLS (если поддерживается)

fail-open — Manager работает при недоступности Redis

9. Сеть
Все компоненты — в изолированной сети (Docker network)

VPN для удалённого доступа

Firewall: открыты только необходимые порты

Порты:

Порт	Компонент	Рекомендация
8000	Manager	Только внутренняя сеть
8001	WebUI	Только внутренняя сеть / VPN
9101-9103	Метрики	Только для Prometheus
5432	PostgreSQL	Только Manager
6379	Redis	Только Manager/Celery
9090	Prometheus	Только админ
3000	Grafana	Только админ
5555	Flower	Только админ
10. Логирование и аудит
Что логируется:

Вход/выход пользователей

Reveal находок (action="finding_revealed")

Изменения статусов находок

Запуск сканирований

Изменения пользователей/ролей

Ошибки аутентификации

Хранение:

audit_logs — партиционирована по месяцам

audit_logs_archive — TTL 90 дней, архив 365 дней

Рекомендации:

Не логируйте секреты (пароли, токены)

Маскируйте PII в логах

Ротация логов (уже реализована в агентах)

Отправка в SIEM (v4.0.0)

🛡️ Компрометация секретов
При компрометации:

Остановите затронутые компоненты

Отзовите сертификаты (CRL)

Сгенерируйте новые секреты:

bash
python scripts/generate_certs.py          # сертификаты
python scripts/generate_findings_keys.py  # ключи находок
Перезапустите компоненты

Проверьте логи на подозрительную активность:

bash
# Подозрительные reveal
grep "finding_revealed" audit_logs.log

# Неудачные логины
grep "auth_failed" audit_logs.log
Уведомите пользователей (если PII скомпрометированы)

📋 Чеклист production
Перед вводом в production:

□ Пароль admin сменён
□ mTLS включён (mtls_strict=true)
□ Сертификаты сгенерированы + CRL настроен
□ Ключи Findings сгенерированы (ENV)
□ Все Scanner имеют идентичные FINDINGS_* ENV
□ key_id совпадает на Manager и всех Scanner
□ Fail-fast включён (DCAP_ALLOW_LEGACY_SCANNER=false)
□ Ведётся инвентаризация сканеров
□ PostgreSQL: TLS + отдельный пользователь + firewall
□ Redis: пароль + firewall
□ Rate-limit настроен
□ Backup БД настроен (pg_dump + cron)
□ Резервная копия ключей Findings — отдельно от БД
□ Логи ротация настроена
□ Мониторинг работает (Prometheus + алерты)
□ Firewall: открыты только необходимые порты
□ VPN для удалённого доступа
□ AD-интеграция (если применимо)
□ Проверен docs/security_checklist.md
См. также: docs/security_checklist.md

📚 Дополнительные ресурсы
ARCHITECTURE.md — архитектура, модели, API

docs/deployment.md — развёртывание

docs/security_checklist.md — чеклист production

docs/admin-guide/05-security.md — руководство администратора

Последнее обновление: 19.09.2026
Версия: v3.13.8


---

## Принятые риски / известные ограничения (v3.14.14, 53.5)

- Trivy image: 6 CRITICAL + 81 HIGH в dcap/manager (базовый python:3.11 + зависимости, в т.ч. Pillow/wheel). План: обновить базовый образ и зависимости в v3.1.0.
- Trivy image webui: 1 CRITICAL + 52 HIGH. Аналогично.
- Bandit: 0 HIGH, 4 MEDIUM (B603/B607/B104/B105 и др.) — задокументированы, исправление в v3.1.0.
- pip-audit: manager — 0 уязвимостей; scanner — не удалось установить в локальном окружении (pip install падает), проверка в Docker — v3.1.0.
- Gitleaks: образ недоступен (registry denied) — skip, повторить при доступе.
- Semgrep: не установлен локально — skip.
- DAST (ZAP): тест-стенд :18000/:18001 не поднят — skip.
- Контейнеры: manager работает от пользователя dcap (non-root), CapDrop пуст, ReadonlyRootfs=false; секреты передаются через env (план: Docker Secrets/Vault в v3.1.0).
