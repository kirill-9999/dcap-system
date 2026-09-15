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
```

**Env:**
- `MTLS_ENABLED=true`
- `MTLS_STRICT=true` (production)
- `CERTS_DIR=certs`

**Компоненты, поддерживающие mTLS:**
- Manager ↔ WebUI
- Manager ↔ Scanner
- Manager ↔ агенты (Windows, Linux, S3)

---

### 2. Шифрование находок (Findings Refactor)

**Модель:** гибрид — маскированное (по умолчанию) + зашифрованное (AES-256-GCM).

| Аспект | Решение |
|--------|---------|
| **Алгоритм** | AES-256-GCM (AEAD) |
| **Ключ шифрования** | Docker Secret `findings_encryption_key` (32 байта) |
| **HMAC-ключ** | Docker Secret `findings_hmac_key` (≥32 байта) |
| **Key ID** | `findings_key_id` (для ротации) |
| **Fingerprint** | HMAC-SHA256 (защита от brute-force) |
| **Legacy-режим** | SHA-256 (НЕ MD5 — MD5 криптографически сломан) |
| **По умолчанию** | Маскированное |
| **Расшифровка** | Только роль **Auditor** (или Admin), с записью в `audit_logs` |
| **Аудит** | Каждый reveal логируется (`action="finding_revealed"`) |

**Генерация ключей:**
```bash
python scripts/generate_findings_keys.py
# → secrets/findings_encryption_key
# → secrets/findings_hmac_key
# → secrets/findings_key_id
```

**Ротация ключей:**
1. Сгенерировать новый ключ → новый `key_id`
2. Старые находки остаются под старым `key_id` (в БД хранится)
3. Расшифровка использует `key_id` из находки
4. Опционально — фоновая перешифровка

**⚠️ ВАЖНО:**
- Ключи **НЕ хранятся в БД**
- Ключи **НЕ коммитятся в git** (`secrets/` в `.gitignore`)
- При потере ключа зашифрованные находки **невосстановимы** (крипто-шреддинг)
- В dev без ключей Manager генерирует **ephemeral** (данные теряются при рестарте)

**Что маскируется:**

| Категория | Маска | Шифрование |
|-----------|-------|-----------|
| phone | `+7***123-45-67` | ✅ |
| email | `iv***@example.com` | ✅ |
| api_key / aws_key | `AKIA***` | ✅ |
| password | `***` | ✅ |
| token / jwt_token | `eyJ***` | ✅ |
| ssh_key / github_token / slack_token | `***` | ✅ |
| database_url / basic_auth | `***` | ✅ |
| passport | `12** ******` | ✅ |
| snils / inn | `***` | ✅ |
| credit_card | `**** **** **** 1234` | ✅ |
| person | **не маскируется** | ❌ |

---

### 3. Хранение секретов

- **Никогда не храните секреты в коде**
- **Production:** Docker Secrets (`/run/secrets/`)
- **Dev:** `.env` (не коммитить!)
- Регулярная ротация паролей и ключей
- `SecretsManager` (приоритет: Docker Secrets → env → default)

**Секреты проекта:**

| Секрет | Назначение |
|--------|-----------|
| `jwt_secret_key` | Подпись JWT |
| `db_password` | Пароль PostgreSQL |
| `ad_service_password` | Пароль AD-сервиса |
| `findings_encryption_key` | AES-256-GCM для находок |
| `findings_hmac_key` | HMAC-SHA256 для fingerprint |
| `findings_key_id` | ID ключа (для ротации) |

**docker-compose.yml:**
```yaml
secrets:
  - jwt_secret_key
  - db_password
  - ad_service_password
  - findings_encryption_key
  - findings_hmac_key
  - findings_key_id
```

---

### 4. Аутентификация и RBAC

**Режимы:**
| Режим | Описание |
|-------|----------|
| `local` | JWT + Bcrypt (разработка) |
| `hybrid` | SPNEGO → fallback JWT (тестирование) |
| `windows_integrated` | Только SPNEGO (production AD) |

**Роли (RBAC):**

| Роль | Права | AD группа |
|------|-------|-----------|
| **Admin** | Полный доступ, удаление | `DCAP_Admins` |
| **Auditor** | Аудит, **reveal находок**, FP | `DCAP_Auditors` |
| **Scanner** | Запуск сканирования | `DCAP_Scanners` |
| **Viewer** | Только чтение (маскированное) | все остальные |

**Рекомендации:**
- Смените пароль `admin/admin123` **сразу** после установки
- Используйте **сложные пароли** (≥12 символов)
- Включите **AD-интеграцию** в production
- Минимизируйте количество Admin-пользователей
- Регулярно проверяйте список пользователей (`GET /api/auth/users`)

---

### 5. Rate-limit

**RateLimitMiddleware** защищает от брутфорса и DoS:

| Параметр | Значение (по умолчанию) |
|----------|------------------------|
| Лимит | 300 запросов/мин на IP |
| Исключение | `/api/health` |
| Хранилище | Redis (in-memory fallback) |
| Ответ | `429 Too Many Requests` |

**Настройка** (секция `redis.rate_limit` в config.json):
```json
{
    "redis": {
        "rate_limit": {
            "max_requests": 300,
            "window_seconds": 60
        }
    }
}
```

**Env:** `RATE_LIMIT_MAX_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`

---

### 6. Шифрование буферов агентов

Агенты буферизуют события при недоступности Manager. Буферы содержат **чувствительные данные** (пути, имена пользователей).

**Windows Agent:**
- EFS (Encrypting File System) для `data/buffer/`
- BitLocker для всего диска

**Linux Agent:**
- LUKS для шифрования диска
- eCryptfs или fscrypt для `data/buffer/`

**S3 Agent:**
- SSE-S3 или SSE-KMS для S3-бакетов с логами
- Клиентское шифрование для буфера

---

### 7. База данных (PostgreSQL)

- **TLS** для подключения к БД (`sslmode=require`)
- **Шифрование на уровне диска**
- **Сетевые политики** (firewall — только Manager)
- **Регулярное резервное копирование** (`pg_dump`)
- **Партиционирование** `audit_logs` по месяцам (уже реализовано)
- **Отдельный пользователь** для Manager (не `postgres`)
- **Аудит доступа** к БД (логи)

**Проверка:**
```bash
# Проверить, что PG слушает только localhost/внутреннюю сеть
ss -tlnp | grep 5432

# Проверить SSL
psql "postgresql://dcap@localhost/dcap?sslmode=require" -c "SHOW ssl;"
```

---

### 8. Redis

- **Пароль** обязателен (`REDIS_PASSWORD`)
- **Не доступен извне** (только внутренняя сеть)
- **TLS** (если поддерживается)
- **fail-open** — Manager работает при недоступности Redis

---

### 9. Сеть

- Все компоненты — в **изолированной сети** (Docker network)
- **VPN** для удалённого доступа
- **Firewall:** открыты только необходимые порты

**Порты:**

| Порт | Компонент | Рекомендация |
|------|-----------|--------------|
| 8000 | Manager | Только внутренняя сеть |
| 8001 | WebUI | Только внутренняя сеть / VPN |
| 9101-9103 | Метрики | Только для Prometheus |
| 5432 | PostgreSQL | Только Manager |
| 6379 | Redis | Только Manager/Celery |
| 9090 | Prometheus | Только админ |
| 3000 | Grafana | Только админ |
| 5555 | Flower | Только админ |

---

### 10. Логирование и аудит

**Что логируется:**
- Вход/выход пользователей
- Reveal находок (`action="finding_revealed"`)
- Изменения статусов находок
- Запуск сканирований
- Изменения пользователей/ролей
- Ошибки аутентификации

**Хранение:**
- `audit_logs` — партиционирована по месяцам
- `audit_logs_archive` — TTL 90 дней, архив 365 дней

**Рекомендации:**
- **Не логируйте** секреты (пароли, токены)
- **Маскируйте** PII в логах
- **Ротация** логов (уже реализована в агентах)
- **Отправка** в SIEM (v4.0.0)

---

## 🛡️ Компрометация секретов

При компрометации:

1. **Остановите** затронутые компоненты
2. **Отзовите** сертификаты (CRL)
3. **Сгенерируйте** новые секреты:
   ```bash
   python scripts/generate_certs.py          # сертификаты
   python scripts/generate_findings_keys.py  # ключи находок
   ```
4. **Перезапустите** компоненты
5. **Проверьте** логи на подозрительную активность:
   ```bash
   # Подозрительные reveal
   grep "finding_revealed" audit_logs.log
   
   # Неудачные логины
   grep "auth_failed" audit_logs.log
   ```
6. **Уведомите** пользователей (если PII скомпрометированы)

---

## 📋 Чеклист production

Перед вводом в production:

- [ ] Пароль `admin` сменён
- [ ] mTLS включён (`mtls_strict=true`)
- [ ] Сертификаты сгенерированы + CRL настроен
- [ ] Ключи находок сгенерированы (`generate_findings_keys.py`)
- [ ] Docker Secrets настроены (не `.env`)
- [ ] PostgreSQL: TLS + отдельный пользователь + firewall
- [ ] Redis: пароль + firewall
- [ ] Rate-limit настроен
- [ ] Backup БД настроен (pg_dump + cron)
- [ ] Логи ротация настроена
- [ ] Мониторинг работает (Prometheus + алерты)
- [ ] Firewall: открыты только необходимые порты
- [ ] VPN для удалённого доступа
- [ ] AD-интеграция (если применимо)
- [ ] Проверен `docs/security_checklist.md`

**См. также:** [docs/security_checklist.md](docs/security_checklist.md)

---

## 📚 Дополнительные ресурсы

- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектура, модели, API
- [docs/deployment.md](docs/deployment.md) — развёртывание
- [docs/security_checklist.md](docs/security_checklist.md) — чеклист production
- [docs/admin-guide/05-security.md](docs/admin-guide/05-security.md) — руководство администратора (в разработке)

---

**Последнее обновление:** 12.09.2026
**Версия:** v3.11.0