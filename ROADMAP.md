# 🗺️ ROADMAP.md — План развития и бэклог DCAP

> **Обновляется архитектором.** План — редко, бэклог — по мере.
> Текущее состояние — в `STATE.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 12.09.2026
**Стратегия:** Windows First → Linux → S3/MinIO → Enterprise Ready → Rust + DLP

---

## 🚀 Вехи

| Версия | Статус | Ключевые фичи |
|--------|--------|---------------|
| v1.0.0 | ✅ | Обнаружение, классификация, каталог, WebUI |
| v2.0.0 | ✅ | Управление доступом, аудит Windows (ядро) |
| v2.0.1 | ✅ | WebUI аудита, отчёты |
| v2.1.0 | ✅ | Linux-агент, унификация форматов |
| **v3.0.0** | **🔄** | **Enterprise Ready: S3, AD, mTLS, архивация, Secret Scanner, масштабирование, контейнеризация, мониторинг, Findings Refactor, админ-руководство, GitHub** |
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
| 40-41 | Тестирование (E2E + Chaos + Load) | — | ✅ |
| 40.1 | Findings Refactor: модель + шифрование + API | BACKLOG-050/051/052 | ✅ |
| 40.2 | Findings Refactor: сканер (построчно + FP + дедуп) | BACKLOG-053/054/055 | ✅ |
| **40.3** | **Findings Refactor: WebUI (находки, каталог, FP)** | **BACKLOG-056/057/066** | 🔄 |
| 40.4 | Findings Refactor: фрагменты (изображения, бинарные, экспорт) | BACKLOG-058/059/060 | 📋 |
| 42.1 | Админ-руководство: установка + конфигурация | — | 📋 |
| 42.2 | Админ-руководство: аутентификация + безопасность | — | 📋 |
| 42.3 | Админ-руководство: сканер + агенты | — | 📋 |
| 42.4 | Админ-руководство: мониторинг + retention + troubleshooting + FAQ | — | 📋 |
| 42 | Публикация на GitHub | BACKLOG-028/046 | 📋 |
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
| BACKLOG-050 | Модель Findings (строка/фрагмент) | 🔴 | ✅ 40.1 |
| BACKLOG-051 | Шифрование находок (AES-256-GCM) | 🔴 | ✅ 40.1 |
| BACKLOG-052 | API находок + reveal + аудит | 🔴 | ✅ 40.1 |
| BACKLOG-053 | Сканер: построчное сканирование | 🔴 | ✅ 40.2 |
| BACKLOG-054 | Fingerprint + дедупликация | 🔴 | ✅ 40.2 |
| BACKLOG-055 | FP-фильтр перед отправкой | 🔴 | ✅ 40.2 |
| **BACKLOG-056** | **WebUI: находки + каталог (строки)** | 🔴 | 🔄 40.3 |
| **BACKLOG-057** | **WebUI: reveal + FP** | 🔴 | 🔄 40.3 |
| **BACKLOG-058** | **Фрагменты изображений (bounding box)** | 🟡 | 📋 40.4 |
| **BACKLOG-059** | **Бинарные: hex-дамп** | 🟢 | 📋 40.4 |
| **BACKLOG-060** | **Экспорт с маскированием** | 🟡 | 📋 40.4 |
| **BACKLOG-061** | **WebUI v3.8: legacy Findings (деградация)** | 🟡 | 🔄 40.3 |
| **BACKLOG-062** | **Удалить `findings_old` после проверки** | 🟢 | 📋 v3.0.0 |
| **BACKLOG-063** | **Presidio: производительность на 100k+ строк** | 🟡 | 📋 v3.1.0 |
| **BACKLOG-064** | **Бенчмарк построчного сканирования** | 🟢 | 📋 v3.1.0 |
| **BACKLOG-065** | **Удалить legacy-код Findings** | 🟢 | 📋 v3.0.0 |
| **BACKLOG-066** | **MD5 → SHA-256 в `_legacy_fingerprint` (крипто-фикс)** | 🔴 | 🔄 40.3 |
| BACKLOG-028 | Публикация на GitHub | 🔴 | 📋 42 |
| BACKLOG-039 | Аудит NOT NULL полей в приёмных эндпоинтах | 🟡 | 📋 |
| BACKLOG-043 | Прогресс сканера в WebUI | 🟡 | 🔄 40.3 |
| BACKLOG-044 | Защита `/metrics` (JWT/basic_auth) | 🟡 | 📋 |
| BACKLOG-045 | Параметризация портов экспортеров | 🟢 | 📋 |
| BACKLOG-046 | Полный E2E-прогон на CI | 🔴 | 📋 42 |
| BACKLOG-047 | `/api/health` версия — синхронизация | 🟡 | 📋 |
| BACKLOG-048 | Rate-limit bypass для тестов | 🟡 | 📋 v3.1.0 |
| BACKLOG-049 | Автоматизация chaos-теста scanner inactive | 🟡 | 📋 v3.1.0 |

### 🔧 BACKLOG-050…066: Findings Refactor — детали

**Проблема:** находка = файл. Нельзя посмотреть, где именно найдено, удалить одно FP, дедуплицировать при повторном скане.

**Решение:** находка = строка/фрагмент файла.

**Модель данных:**
```python
Finding:
  # Классификация
  finding_type: str      # pii, credentials, code
  category: str          # phone, email, api_key
  severity: str

  # Где найдено
  fragment_type: str     # text_line, text_context, image_region, byte_range
  line_number: int
  line_text_masked: str
  line_text_encrypted: str
  match_text_masked: str
  match_text_encrypted: str
  context_before_masked: str
  context_after_masked: str

  # Не-текстовые
  fragment_path: str
  bounding_box: JSON     # {x,y,w,h}
  byte_offset: int
  byte_length: int
  hex_preview: str

  # Дедупликация
  fingerprint: str       # HMAC-SHA256
  encryption_key_id: str

  # Статус
  status: str            # new, confirmed, false_positive, archived
  reviewed_by: int
  reviewed_at: datetime
  comment: str
```

**Хранение:** гибрид (маскированное + зашифрованное AES-256-GCM).
- По умолчанию — маскированное
- Расшифровка — только Auditor, с аудитом
- Ключ — Docker Secrets (`findings_encryption_key`, `findings_hmac_key`)

**Маскирование:**

| Категория | Маска |
|-----------|-------|
| phone | `+7***XXX-XX-XX` |
| email | `iv***@example.com` |
| api_key | `AKIA***` |
| password | `***` |
| token | `eyJ***` |
| passport | `12** ******` |
| person | **не маскируется** |

**Дедупликация:**
- `fingerprint = HMAC-SHA256(file_path + line + match_text + finding_type)` *(реально в коде — `finding_type`, не `category`)*
- Legacy-режим (без ключей): SHA-256 (не MD5 — BACKLOG-066)
- При повторном скане:
  - `false_positive` → **не создавать**
  - `confirmed` → обновить `last_seen_at`, не дублировать
  - новый → создать `new`

**FP-фильтр:** сканер перед отправкой батчем проверяет fingerprints в Manager (`POST /api/findings/check-fingerprints`).

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
| 53 | Расширенный мониторинг | BACKLOG-063/064 | 🟡 |
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
| BACKLOG-063 | Presidio: производительность | 🟡 | 📋 |
| BACKLOG-064 | Бенчмарк сканирования | 🟢 | 📋 |
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
| **Связь** | IPC (JSON-RPC) — Unix socket / Named Pipe, крейт `interprocess` |
| **CIFS (SMB)** | Rust `pavao` + `libsmbclient` (пререквизит, документируется) |
| **NFS** | Rust `nfs-rs` — чистый Rust, автоматическое монтирование через API |
| **Кроссплатформенность** | Windows + Linux |
| **Fallback** | Старый Python-сканер (`scanner/`) остаётся |

**Пререквизиты `libsmbclient`:**
- Debian/Ubuntu: `sudo apt-get install libsmbclient-dev`
- RedHat/Fedora: `sudo dnf install libsmbclient-devel`
- macOS: `brew install samba`
- Windows: SMB через `std::fs` (если смонтировано) или крейт `remotefs-smb`

**NFS URL:** `nfs://server:/export?version=4.1&noresvport=true`

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
| v3.0.0 | 35 | 22 | 63% 🔄 |
| v3.1.0 | 12 | 0 | 0% 📋 |
| v4.0.0 | 9 | 0 | 0% 📋 |
| **ИТОГО** | **83** | **49** | **59%** |

---

## 📝 Шаблон новой задачи

```
| BACKLOG-XXX | Название | 🔴/🟡/🟢 | 📋/🔄/✅/❌ |
```

Приоритеты: 🔴 критично / 🟡 важно / 🟢 nice-to-have
Статусы: 📋 запланировано / 🔄 в работе / ✅ выполнено / ❌ отменено