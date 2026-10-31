# 🔒 Security Checklist — DCAP Production

> **Чеклист для ввода в production.**
> Политика безопасности — в [SECURITY.md](../SECURITY.md).
> Полное руководство — в [docs/admin-guide/05-security.md](admin-guide/05-security.md).

**Обновлено:** 03.10.2026
**Версия:** v3.13.28

---

## ✅ Перед установкой

- [ ] Определён **режим аутентификации** (local / hybrid / windows_integrated)
- [ ] Определены **роли** пользователей (Admin, Auditor, Scanner, Viewer)
- [ ] Подготовлены **сертификаты** (если mTLS strict)
- [ ] Подготовлены **ключи шифрования находок**
- [ ] Определён **объём хранения** (БД, архив, логи)
- [ ] Настроен **backup** (PostgreSQL)
- [ ] Определены **порты** (firewall)

---

## ✅ Установка

### Manager

- [ ] Пароль `admin` сменён (≥12 символов)
- [ ] `AUTH_MODE` установлен корректно
- [ ] `JWT_SECRET_KEY` — уникальный, ≥32 байт
- [ ] `MTLS_ENABLED=true`, `MTLS_STRICT=true` (production)
- [ ] Сертификаты сгенерированы (`generate_certs.py`)
- [ ] **Volume `./certs:/app/certs:ro`** — BUG-105, v3.13.28
- [ ] `DATABASE_URL` с `sslmode=require`
- [ ] `REDIS_PASSWORD` установлен
- [ ] Rate-limit настроен

### PostgreSQL

- [ ] Отдельный пользователь (не `postgres`)
- [ ] Пароль ≥20 символов
- [ ] TLS включён (`ssl=on`)
- [ ] Слушает только внутреннюю сеть
- [ ] Firewall: только Manager
- [ ] Backup (pg_dump + cron)
- [ ] Партиционирование `audit_logs` (миграция 001)

### Redis

- [ ] Пароль установлен (`requirepass`)
- [ ] Слушает только внутреннюю сеть
- [ ] Firewall: только Manager/Celery
- [ ] `maxmemory` + LRU

### WebUI

- [ ] Слушает только `127.0.0.1` / VPN
- [ ] JWT передаётся через `Authorization: Bearer`
- [ ] CDN отключён (локальные vendor)
- [ ] HTTPS (через reverse proxy)

### Scanner

- [ ] **На хосте** (не в Docker)
- [ ] Ключи `FINDINGS_*` **ИДЕНТИЧНЫ** ключам Manager
- [ ] `key_id` совпадает с Manager
- [ ] Fail-fast включён (`DCAP_ALLOW_LEGACY_SCANNER=false` или переменная отсутствует)
- [ ] Tesseract + spaCy + Presidio установлены
- [ ] Доступ к сканируемым путям
- [ ] Запуск через systemd (Linux) / службу (Windows)

### Агенты (Windows / Linux / S3)

- [ ] Конфиг с уникальным именем
- [ ] mTLS (если strict)
- [ ] Буфер зашифрован (EFS / LUKS / SSE)
- [ ] Ротация логов
- [ ] Systemd / Windows-служба
- [ ] Firewall: только Manager

---

## ✅ Мониторинг

- [ ] Prometheus собирает метрики (6/6 targets UP при запущенном сканере)
- [ ] Grafana дашборды открываются
- [ ] Alertmanager настроен
- [ ] Алерты: `ScannerInactive`, `TaskFailed`, `HighErrorRate`, `CeleryQueueBacklog`
- [ ] **MetricsMiddleware снаружи всех** — BUG-103, v3.13.28
- [ ] **Метка `endpoint` нормализована (`{id}`)** — BUG-103, v3.13.28
- [ ] **401-ответы видны в метриках** — BUG-103, v3.13.28
- [ ] Метрики `/metrics` защищены (JWT/basic_auth) — BACKLOG-044, v3.0.0 production
- [ ] Логи ротация

---

## ✅ Безопасность находок (Findings)

### Ключи (ENV-only)

- [ ] Ключи Findings сгенерированы **один раз** на Manager-хосте
- [ ] Manager имеет ENV: `FINDINGS_ENCRYPTION_KEY`, `FINDINGS_HMAC_KEY`, `FINDINGS_KEY_ID`
- [ ] **Все** Scanner'ы имеют **ИДЕНТИЧНЫЕ** `FINDINGS_*` ENV
- [ ] `key_id` **совпадает** на Manager и всех Scanner'ах
- [ ] Fail-fast включён: `DCAP_ALLOW_LEGACY_SCANNER=false` (или переменная отсутствует)
- [ ] **`fail_if_missing=True`** — default (BUG-057 fix)
- [ ] **Инвентаризация** сканеров ведётся
- [ ] Резервная копия ключей — **ОТДЕЛЬНО** от БД
- [ ] Доступ к ENV ограничен (`chmod 600`, ограничение `docker inspect`)
- [ ] Ключи **не коммитятся** в git
- [ ] Ротация запланирована (90 дней)
- [ ] **`reencrypt_findings.py` пересчитывает FP** — BUG-116, v3.13.28
- [ ] **`reencrypt_findings.py --dedup`** — дубликаты помечаются/удаляются

### Ключи Findings передаются только через ENV

- [ ] Manager: `.env` (Docker Compose) или `EnvironmentFile` (systemd)
- [ ] Scanner: `EnvironmentFile` (systemd) или `AppEnvironmentExtra` (NSSM)
- [ ] Docker Secrets / файлы ключей — **не используются** в v3.0.0

### Шифрование и маскирование

- [ ] Reveal доступен **только Auditor+**
- [ ] Аудит успешного reveal работает (`finding_revealed`)
- [ ] **Аудит ошибки reveal работает (`finding_reveal_failed`)** — BUG-110, v3.13.28
- [ ] Маскирование работает
- [ ] **MD5 не используется** (BACKLOG-066)
- [ ] `line_text_encrypted` заполняется (BUG-057 fix)
- [ ] Legacy-режим отключён (ключи заданы)

### Ротация ключей

- [ ] Процедура задокументирована
- [ ] `scripts/reencrypt_findings.py` — доступен
- [ ] Планируемое окно downtime согласовано
- [ ] Тест ротации проведён на stage
- [ ] **Fingerprint пересчитывается** — BUG-116, v3.13.28

---

## ✅ mTLS

- [ ] `MTLS_ENABLED=true`, `MTLS_STRICT=true` (production)
- [ ] Сертификаты сгенерированы (`generate_certs.py`)
- [ ] **Volume certs: `./certs:/app/certs:ro`** — BUG-105, v3.13.28
- [ ] **`run_manager.py` использует `CertificateManager`** — BUG-108, v3.13.28
- [ ] **Strict → `CERT_REQUIRED`** — BUG-108, v3.13.28
- [ ] **CRL enforce: `VERIFY_CRL_CHECK_LEAF`** — BUG-107, v3.13.28
- [ ] **Machine-эндпоинты в strict без сертификата → 401** — BUG-106, v3.13.28
- [ ] **`is_revoked` вызывается в `_check_mtls`** — BUG-107, v3.13.28
- [ ] CRL обновляется регулярно (`rotate_certs.py --revoke <serial>`)

---

## ✅ Сеть

- [ ] Все компоненты — в изолированной сети
- [ ] Firewall: открыты только необходимые порты
- [ ] VPN для удалённого доступа
- [ ] HTTPS для WebUI (reverse proxy)

**Порты:**

| Порт | Компонент | Доступ |
|------|-----------|--------|
| 8000 | Manager | Только внутренняя сеть |
| 8001 | WebUI | VPN / reverse proxy |
| 9101-9103 | Метрики | Только Prometheus |
| 5432 | PostgreSQL | Только Manager |
| 6379 | Redis | Только Manager/Celery |
| 9090 | Prometheus | Только админ |
| 3000 | Grafana | Только админ |
| 9093 | Alertmanager | Только админ |
| 5555 | Flower | Только админ |

---

## ✅ Аутентификация и RBAC

- [ ] `admin` — только для bootstrap
- [ ] Минимум Admin-пользователей
- [ ] AD-интеграция (если production)
- [ ] Маппинг AD-групп на роли
- [ ] Регулярный аудит пользователей
- [ ] Ротация JWT (refresh token)
- [ ] Блокировка после N неудачных логинов

**Cookie (JWT):**
- [ ] `HttpOnly: True` — проверено
- [ ] `SameSite=Lax` — проверено
- [ ] `Secure: True` при HTTPS

---

## ✅ Аудит и логирование

- [ ] `audit_logs` пишутся
- [ ] Reveal находок логируется (`finding_revealed`)
- [ ] **Reveal при ошибке логируется (`finding_reveal_failed`)** — BUG-110, v3.13.28
- [ ] Изменения статусов логируются
- [ ] **Экспорт логируется с `source_host`** — BUG-114, v3.13.28
- [ ] Логи не содержат секретов
- [ ] PII в логах маскированы
- [ ] Ротация логов
- [ ] Архивация (`audit_logs_archive`, TTL 90 дней)

---

## ✅ Retention и backup

- [ ] Политики retention настроены
- [ ] Celery Beat работает (расписание)
- [ ] Backup БД (ежедневно)
- [ ] Backup **ключей Findings** — **ОТДЕЛЬНО** от БД!
- [ ] Backup сертификатов — **ОТДЕЛЬНО** от БД!
- [ ] Тест восстановления из backup
- [ ] Экспорт находок (CSV/JSON)

---

## ✅ Перед релизом

- [ ] Все тесты проходят (`pytest` без аргументов — 408 passed, 17 skipped) — BUG-119, v3.13.28
- [ ] **SQLAlchemy pinned `==2.0.54`** — v3.0.0
- [ ] CI настроен (GitHub Actions)
- [ ] `STATE.md` актуален
- [ ] `ROADMAP.md` актуален
- [ ] `ARCHITECTURE.md` актуален
- [ ] `SECURITY.md` актуален
- [ ] `docs/admin-guide/05-security.md` актуален
- [ ] `CHANGELOG.md` актуален
- [ ] Документация админа готова
- [ ] **LICENSE выбран** — v3.0.0 GitHub-пакет
- [ ] README актуален
- [ ] **BUG-117 (Manager-маскирование) закрыт** — v3.0.0 hotfix

---

## 🚨 При инциденте

1. **Остановить** затронутые компоненты
2. **Отозвать** сертификаты (CRL)
3. **Сгенерировать** новые секреты
4. **Перезапустить** компоненты
5. **Проверить** логи:
   ```bash
   grep "finding_revealed" audit_logs.log
   grep "finding_reveal_failed" audit_logs.log
   grep "auth_failed" audit_logs.log
Уведомить пользователей (если PII скомпрометированы)

Задокументировать инцидент

Детали — в docs/admin-guide/05-security.md §9.

📚 См. также
SECURITY.md — политика безопасности

ARCHITECTURE.md — архитектура

docs/deployment.md — развёртывание

docs/monitoring.md — мониторинг

docs/admin-guide/05-security.md — руководство админа

Последнее обновление: 03.10.2026
Версия: v3.13.28