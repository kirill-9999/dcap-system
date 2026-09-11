markdown
# 🗺️ ROADMAP.md — План развития и бэклог DCAP

> **Обновляется архитектором.** План — редко, бэклог — по мере.
> Текущее состояние — в `STATE.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 11.09.2026
**Стратегия:** Windows First → Linux → S3/MinIO → Enterprise Ready → Rust + DLP

---

## 🚀 Вехи

| Версия | Статус | Ключевые фичи |
|--------|--------|---------------|
| v1.0.0 | ✅ | Обнаружение, классификация, каталог, WebUI |
| v2.0.0 | ✅ | Управление доступом, аудит Windows (ядро) |
| v2.0.1 | ✅ | WebUI аудита, отчёты |
| v2.1.0 | ✅ | Linux-агент, унификация форматов |
| **v3.0.0** | **🔄** | **Enterprise Ready: S3, AD, mTLS, архивация, Secret Scanner, масштабирование, контейнеризация, мониторинг, GitHub** |
| v3.1.0 | 📋 | Rust Scanner, DLP/ICAP, SMB, Webhook, облака, распределённая система |
| v4.0.0 | 📋 | ML-классификаторы, Zero-Trust, распределённый Manager, SIEM |

---

## 📋 v3.0.0 — ENTERPRISE READY (🔄 ЗАВЕРШАЕТСЯ)

### План по дням

| День | Задача | BACKLOG | Статус |
|------|--------|---------|--------|
| 28 | WebUI: редизайн | BACKLOG-015 | ✅ |
| 29 | Стандартизация структуры | BACKLOG-026 | ✅ |
| 29.5 | Унификация Manager и WebUI | — | ✅ |
| 30 | Гибридная аутентификация | BACKLOG-016 | ✅ |
| 31-32 | S3/MinIO агент | BACKLOG-010 | ✅ |
| 33 | AD интеграция + RBAC WebUI | BACKLOG-029 | ✅ |
| 34 | Безопасность (mTLS, секреты) | BACKLOG-013 | ✅ |
| 34.5 | Secret Scanner интеграция | BACKLOG-034 | ✅ |
| 35 | Архивация данных | BACKLOG-030 | ✅ |
| 36-37 | Масштабирование (PG, Redis, Celery) | BACKLOG-014 | ✅ |
| 38 | Контейнеризация и деплой | BACKLOG-027 | ✅ |
| 38.5 | Scanner: Docker → хост | — | ✅ |
| 39 | Мониторинг + Heartbeat-thread | BACKLOG-021/037/038/041/042 | ✅ |
| **40-41** | **Тестирование (E2E + Chaos)** | — | ✅ |
| 42 | Публикация на GitHub | BACKLOG-028 | 📋 |
| 43 | Релиз v3.0.0 | — | 📋 |

### Бэклог v3.0.0

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| BACKLOG-010 | S3/MinIO аудит-агент | 🔴 | ✅ |
| BACKLOG-013 | Безопасность (mTLS, секреты) | 🔴 | ✅ |
| BACKLOG-014 | Масштабирование (PG, Redis, Celery) | 🔴 | ✅ |
| BACKLOG-015 | WebUI редизайн | 🟡 | ✅ |
| BACKLOG-016 | Гибридная аутентификация | 🔴 | ✅ |
| BACKLOG-021 | Расширенный мониторинг (Prometheus/Grafana) | 🟡 | ✅ |
| BACKLOG-026 | Стандартизация структуры | 🟡 | ✅ |
| BACKLOG-027 | Контейнеризация и деплой | 🔴 | ✅ |
| BACKLOG-029 | AD интеграция + RBAC | 🔴 | ✅ |
| BACKLOG-030 | Архивация данных | 🟡 | ✅ |
| BACKLOG-034 | Secret Scanner интеграция | 🔴 | ✅ |
| BACKLOG-037 | Heartbeat-thread для сканера | 🔴 | ✅ |
| BACKLOG-038 | Прогресс-пинг в heartbeat | 🟡 | ✅ |
| BACKLOG-041 | Prometheus/Grafana мониторинг | 🔴 | ✅ |
| BACKLOG-042 | Alertmanager + алерты | 🟡 | ✅ |
| BACKLOG-028 | Публикация на GitHub | 🔴 | 📋 |
| BACKLOG-039 | Аудит NOT NULL полей в приёмных эндпоинтах | 🟡 | 📋 |
| BACKLOG-043 | Прогресс сканера в WebUI | 🟡 | 📋 |
| BACKLOG-044 | Защита `/metrics` (JWT/basic_auth) | 🟡 | 📋 |
| BACKLOG-045 | Параметризация портов экспортеров | 🟢 | 📋 |

---

## 📋 v3.1.0 — RUST + DLP (📋 ПЛАНИРУЕТСЯ)

### План по дням

| День | Задача | BACKLOG | Приоритет |
|------|--------|---------|-----------|
| 44-45 | Rust Scanner (ядро + интеграция) | BACKLOG-036 | 🔴 |
| 46 | ICAP Connector (DLP) | BACKLOG-032 | 🟡 |
| 47 | DLP Политики (WebUI) | BACKLOG-033 | 🟡 |
| 48 | SMB-сканер (на базе Rust) | BACKLOG-035 | 🟡 |
| 49 | Webhook для MinIO | BACKLOG-011 | 🟢 |
| 50 | Аудит для облачных хранилищ | BACKLOG-012 | 🟢 |
| 51 | Обработка архивов | BACKLOG-017 | 🟡 |
| 52 | Распределённая архитектура | BACKLOG-018 | 🔴 |
| 53 | Расширенный мониторинг | BACKLOG-021 | 🟡 |
| 54 | Red teaming, SAST, SCA | BACKLOG-022 | 🔴 |
| 55 | Релиз v3.1.0 | — | 🔴 |

### Бэклог v3.1.0

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| BACKLOG-036 | Rust Scanner (IPC, CIFS, NFS) | 🔴 | 📋 |
| BACKLOG-032 | ICAP Connector (DLP) | 🟡 | 📋 |
| BACKLOG-033 | DLP Политики (WebUI) | 🟡 | 📋 |
| BACKLOG-035 | SMB-сканер | 🟡 | 📋 |
| BACKLOG-040 | Параллельный батч-сканер | 🟡 | 📋 |
| BACKLOG-011 | Webhook для MinIO | 🟢 | 📋 |
| BACKLOG-012 | Облачные хранилища | 🟢 | 📋 |
| BACKLOG-017 | Обработка архивов | 🟡 | 📋 |
| BACKLOG-018 | Распределённая архитектура | 🔴 | 📋 |
| BACKLOG-022 | Red teaming, SAST, SCA | 🔴 | 📋 |

### 🔧 BACKLOG-036: Rust Scanner — детали

| Аспект | Решение |
|--------|---------|
| **Ядро** | Rust (обход ФС, regex-префильтр, entropy, heartbeat, метрики) |
| **Python Sidecar** | OCR (Tesseract) + PII (Presidio/spaCy) + код-классификаторы |
| **Связь** | **IPC (JSON-RPC)** — Unix socket / Named Pipe, крейт `interprocess` (length-prefix framing) |
| **CIFS (SMB)** | Rust `pavao` + `libsmbclient` (пререквизит, документируется) |
| **NFS** | Rust `nfs-rs` — чистый Rust, **автоматическое монтирование через API** (без root при `noresvport=true`) |
| **Кроссплатформенность** | Windows + Linux (Rust + Python одинаково) |
| **Fallback** | Старый Python-сканер (`scanner/`) остаётся для совместимости |

**Пререквизиты `libsmbclient` (для CIFS):**

| ОС | Команда |
|----|---------|
| Debian/Ubuntu | `sudo apt-get install libsmbclient-dev` |
| RedHat/Fedora | `sudo dnf install libsmbclient-devel` |
| macOS | `brew install samba` |
| Windows | SMB через `std::fs` (если смонтировано) или крейт `remotefs-smb` |

**NFS URL (nfs-rs):** `nfs://server:/export?version=4.1&noresvport=true`
- `version=3` или `4.1` (NFSv4.0/4.2 не реализованы)
- `noresvport=true` — непривилегированный порт (без root)

---

## 📋 v4.0.0 — AI/ML + DISTRIBUTED (📋 ПЛАНИРУЕТСЯ)

| День | Задача | Приоритет |
|------|--------|-----------|
| 56-57 | ML-классификаторы | 🔴 |
| 58 | Аномалии в аудите | 🟡 |
| 59-60 | Zero-Trust архитектура | 🔴 |
| 61 | Распределённый Manager | 🔴 |
| 62 | Интеграция с SIEM | 🟡 |
| 63 | Версионирование данных | 🟢 |
| 64 | Релиз v4.0.0 | 🔴 |

---

## 📊 Статистика

| Версия | Задач | Выполнено | Прогресс |
|--------|-------|-----------|----------|
| v1.0.0 | 8 | 8 | 100% ✅ |
| v2.0.0 | 10 | 10 | 100% ✅ |
| v2.0.1 | 4 | 4 | 100% ✅ |
| v2.1.0 | 5 | 5 | 100% ✅ |
| v3.0.0 | 20 | 16 | 80% 🔄 |
| v3.1.0 | 11 | 0 | 0% 📋 |
| v4.0.0 | 9 | 0 | 0% 📋 |
| **ИТОГО** | **67** | **43** | **64%** |

---

## 📝 Шаблон новой задачи
| BACKLOG-XXX | Название | 🔴/🟡/🟢 | 📋/🔄/✅/❌ |

text

Приоритеты: 🔴 критично / 🟡 важно / 🟢 nice-to-have
Статусы: 📋 запланировано / 🔄 в работе / ✅ выполнено / ❌ отменено