🔒 Security Checklist — DCAP Production

> **Чеклист для ввода в production.**
> Политика безопасности — в [SECURITY.md](../SECURITY.md).

**Обновлено:** 12.09.2026
**Версия:** v3.11.0

---

## ✅ Перед установкой

- [ ] Определён **режим аутентификации** (local / hybrid / windows_integrated)
- [ ] Определены **роли** пользователей (Admin, Auditor, Scanner, Viewer)
- [ ] Подготовлены **сертификаты** (если mTLS strict)
- [ ] Подготовлены **ключи шифрования находок**
- [ ] Подготовлены **секреты** (Docker Secrets / Vault)
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
- [ ] Ключи находок сгенерированы (`generate_findings_keys.py`)
- [ ] `DCAP_ALLOW_LEGACY_SCANNER` не задан/`false` (BUG-057: сканер fail-fast без ключей)
- [ ] Docker Secrets настроены (не `.env`)
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
- [ ] Ключи `FINDINGS_*` совпадают с Manager
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

## ✅ Безопасность находок

- [ ] Ключи `findings_encryption_key` / `findings_hmac_key` — в Docker Secrets
- [ ] `key_id` актуален
- [ ] Reveal доступен **только Auditor+**
- [ ] Аудит reveal работает (`audit_logs`)
- [ ] Маскирование работает (проверить API)
- [ ] **MD5 не используется** (BACKLOG-066)
- [ ] Legacy-режим отключён (ключи заданы)

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
- [ ] Backup сертификатов и ключей (**отдельно** от БД!)
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
   ```
6. **Уведомить** пользователей (если PII скомпрометированы)
7. **Задокументировать** инцидент

---

## 📚 См. также

- [SECURITY.md](../SECURITY.md) — политика безопасности
- [ARCHITECTURE.md](../ARCHITECTURE.md) — архитектура
- [docs/deployment.md](deployment.md) — развёртывание
- [docs/monitoring.md](monitoring.md) — мониторинг
- [docs/admin-guide/05-security.md](admin-guide/05-security.md) — руководство админа (в разработке)

---

**Последнее обновление:** 12.09.2026