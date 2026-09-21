🔒 Security Checklist — DCAP Production

> **Чеклист для ввода в production.**
> Политика безопасности — в [SECURITY.md](../SECURITY.md).
> Полное руководство — в [docs/admin-guide/05-security.md](admin-guide/05-security.md).

**Обновлено:** 19.09.2026
**Версия:** v3.13.8

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
- [ ] Fail-fast включён (`DCAP_ALLOW_LEGACY_SCANNER=false`)
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

- [ ] Prometheus собирает метрики (все targets UP)
- [ ] Grafana дашборды открываются
- [ ] Alertmanager настроен (email/Slack)
- [ ] Алерты: `ScannerInactive`, `TaskFailed`, `HighErrorRate`, `CeleryQueueBacklog`
- [ ] Метрики `/metrics` защищены (JWT/basic_auth — BACKLOG-044)
- [ ] Логи ротация

---

## ✅ Безопасность находок (Findings)

### Ключи (ENV-only)

- [ ] Ключи Findings сгенерированы **один раз** на Manager-хосте (`generate_findings_keys.py`)
- [ ] Manager имеет ENV: `FINDINGS_ENCRYPTION_KEY`, `FINDINGS_HMAC_KEY`, `FINDINGS_KEY_ID`
- [ ] **Все** Scanner'ы имеют **ИДЕНТИЧНЫЕ** `FINDINGS_*` ENV
- [ ] `key_id` **совпадает** на Manager и **всех** Scanner'ах
- [ ] Fail-fast включён: `DCAP_ALLOW_LEGACY_SCANNER=false` (или переменная **отсутствует**)
- [ ] **Инвентаризация** сканеров ведётся (Scanner ID → key_id → дата выдачи)
- [ ] Резервная копия ключей — **ОТДЕЛЬНО** от БД (offline / Vault)
- [ ] Доступ к ENV ограничен: `chmod 600` на systemd-файлы, ограничение `docker inspect`
- [ ] Ключи **не коммитятся** в git (`secrets/` в `.gitignore`)
- [ ] Ротация запланирована (90 дней)

### Ключи Findings сгенерированы **один раз**

- [ ] `scripts/generate_findings_keys.py` запущен на Manager-хосте
- [ ] Значения переданы **всем** компонентам (Manager + N Scanner)
- [ ] Старые ключи (если были) — сохранены в offline-хранилище
- [ ] **Категорически нельзя** передавать ключи через email/chat

### Ключи Findings передаются **только через ENV**

- [ ] Manager: `.env` (Docker Compose) или `EnvironmentFile` (systemd)
- [ ] Scanner: `EnvironmentFile` (systemd) или `AppEnvironmentExtra` (NSSM)
- [ ] Docker Secrets / файлы ключей — **не используются** в v3.0.0

### Шифрование и маскирование

- [ ] Reveal доступен **только Auditor+**
- [ ] Аудит reveal работает (`audit_logs` → `finding_revealed`)
- [ ] Маскирование работает (проверить API)
- [ ] **MD5 не используется** (BACKLOG-066)
- [ ] `line_text_encrypted` заполняется (BUG-057 fix: сканер без ключей не стартует)
- [ ] Legacy-режим отключён (ключи заданы)

### Ротация ключей

- [ ] Процедура задокументирована (см. `docs/admin-guide/05-security.md` §3.8)
- [ ] `scripts/reencrypt_findings.py` — доступен
- [ ] Планируемое окно downtime согласовано
- [ ] Тест ротации проведён на stage

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

- [ ] `admin` — только для bootstrap, потом отключить/сменить
- [ ] Минимум Admin-пользователей
- [ ] AD-интеграция (если production)
- [ ] Маппинг AD-групп на роли (`DCAP_Admins` и т.д.)
- [ ] Регулярный аудит пользователей
- [ ] Ротация JWT (refresh token)
- [ ] Блокировка после N неудачных логинов

**Cookie (JWT):**
- [ ] `HttpOnly: True` — проверено (`curl -i` → `Set-Cookie`)
- [ ] `SameSite=Lax` — проверено
- [ ] `Secure: True` при HTTPS (env `COOKIE_SECURE=true` или авто)

---

## ✅ Аудит и логирование

- [ ] `audit_logs` пишутся
- [ ] Reveal находок логируется (`finding_revealed`)
- [ ] Изменения статусов логируются
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

- [ ] Все тесты проходят (`pytest tests/ -v`)
- [ ] CI настроен (GitHub Actions)
- [ ] `STATE.md` актуален
- [ ] `ROADMAP.md` актуален
- [ ] `ARCHITECTURE.md` актуален
- [ ] `SECURITY.md` актуален
- [ ] `docs/admin-guide/05-security.md` актуален
- [ ] `CHANGELOG.md` актуален
- [ ] Документация админа готова (`docs/admin-guide/`)
- [ ] LICENSE выбран
- [ ] README актуален

---

## 🚨 При инциденте

1. **Остановить** затронутые компоненты
2. **Отозвать** сертификаты (CRL)
3. **Сгенерировать** новые секреты
4. **Перезапустить** компоненты
5. **Проверить** логи:
   ```bash
   grep "finding_revealed" audit_logs.log
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

Последнее обновление: 19.09.2026
Версия: v3.13.8