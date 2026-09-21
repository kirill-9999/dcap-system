# 🗺️ ROADMAP.md — План развития и бэклог DCAP

> **Обновляется архитектором.** План — редко, бэклог — по мере.
> Текущее состояние — в `STATE.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 20.09.2026
**Стратегия:** Windows First → Linux → S3/MinIO → Enterprise Ready → Rust + DLP + SIEM

---

## 🚀 Вехи

| Версия | Статус | Ключевые фичи |
|--------|--------|---------------|
| v1.0.0 | ✅ | Обнаружение, классификация, каталог, WebUI |
| v2.0.0 | ✅ | Управление доступом, аудит Windows (ядро) |
| v2.0.1 | ✅ | WebUI аудита, отчёты |
| v2.1.0 | ✅ | Linux-агент, унификация форматов |
| **v3.0.0** | **🔄 Финальный этап** | **Enterprise Ready: S3, AD, mTLS, архивация, Findings Refactor, ENV-ключи, RBAC, админ-руководство, GitHub** |
| v3.1.0 | 📋 | Rust Scanner, DLP/ICAP, SMB, Webhook, облака, **Auth Hardening, Per-scanner keys, BOM fix, SIEM-интеграция** |
| v4.0.0 | 📋 | ML-классификаторы, Zero-Trust, распределённый Manager, Kafka/Kinesis SIEM |

---

## 📋 v3.0.0 — ENTERPRISE READY (🔄 ФИНАЛЬНЫЙ ЭТАП)

### План по дням

| День | Задача | BACKLOG/BUG | Статус |
|------|--------|-------------|--------|
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
| 40.3 | Findings Refactor: WebUI (находки, каталог, FP) | BACKLOG-056/057/066 | ✅ |
| 40.4 | Findings Refactor: фрагменты (изображения, бинарные, экспорт) | BACKLOG-058/059/060 | ✅ |
| 42.1 | Админ-руководство: установка + конфигурация | — | ✅ |
| 42.2 | Админ-руководство: аутентификация + безопасность | — | ✅ |
| 42.3 | Админ-руководство: сканер + агенты | — | ✅ |
| 42.4 | Админ-руководство: мониторинг + retention + troubleshooting + FAQ | — | ✅ |
| 43 | Блок 1 (фиксы): BUG-034/035/027/022 + Deploy/Config + WebUI | — | ✅ v3.13.3-4 |
| 43.3 | BUG-022.9 (приоритизация категорий) | — | ✅ v3.13.6 |
| 44 | BUG-034 (зависшие задачи) + AD-упаковка | — | ✅ v3.13.7-8 |
| 45 (тест) | Мастер-сессия: Блок 2 (Auth/RBAC) | — | ✅ `STATE_TEST_SESSION.md` |
| 45 (fix1) | **Fix-спринт №1: Auth/RBAC (15 багов)** | **BUG-037…059** | ✅ **v3.13.9** |
| 46 (fix2) | **Fix-спринт №2: middleware (BUG-048b)** | **BUG-048b** | ✅ **v3.13.10** |
| 46 (fix3) | **Fix-спринт №3: ENV-ключи (TASK-016…021)** | **TASK-016…021** | 📋 |
| 47 (тест) | Мастер-сессия: Блок 3 (Scanner deep) | — | ✅ `STATE_TEST_SESSION.md` |
| 47 (fix4) | **Fix-спринт №4: Scanner deep (BUG-061, 063, 066, 067, 067b, 065, 062)** | **BUG-061…067** | 📋 **ТЗ №3** |
| 48 | Повторный RBAC-прогон (полная матрица) | — | 📋 |
| 49 | Публикация на GitHub | BACKLOG-028/046 | 📋 |
| 50 | Релиз v3.0.0 | — | 📋 |

### Бэклог v3.0.0 — активные задачи

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| **TASK-016** | `scripts/reencrypt_findings.py` (ENV-ключи) | 🔴 | 📋 fix3 |
| **TASK-017** | Fail-fast сканера (BUG-057) — доработка | 🔴 | ✅ done |
| **TASK-018** | Убрать Docker Secrets для Findings | 🟡 | 📋 fix3 |
| **TASK-019** | Обновить документацию (ENV-ключи) | 🟡 | ✅ done |
| **TASK-020** | E2E-тест ротации ключей | 🟡 | 📋 fix3 |
| **TASK-021** | Закрыть ТЗ №1 | 🟢 | ✅ done |
| **TASK-022** | BUG-067: OCR для изображений | 🔴 | 📋 fix4 |
| **TASK-023** | BUG-067b: OCR для PDF | 🔴 | 📋 fix4 |
| **TASK-024** | BUG-063: `credit_card` распознаватель | 🔴 | 📋 fix4 |
| **TASK-025** | BUG-066: `url`-дубликаты email | 🔴 | 📋 fix4 |
| **TASK-026** | BUG-061: HTTP retry в сканере | 🟡 | 📋 fix4 |
| **TASK-027** | BUG-065: credentials-паттерны | 🟡 | 📋 fix4 |
| **TASK-028** | BUG-062: логи сканера | 🟢 | 📋 fix4 |
| BACKLOG-028 | Публикация на GitHub | 🔴 | 📋 49 |
| BACKLOG-039 | Аудит NOT NULL полей | 🟡 | 📋 |
| BACKLOG-044 | Защита `/metrics` (JWT/basic_auth) | 🟡 | 📋 production |
| BACKLOG-045 | Параметризация портов экспортеров | 🟢 | 📋 |
| BACKLOG-046 | Полный E2E-прогон на CI | 🔴 | 📋 49 |
| BACKLOG-047 | `/api/health` версия — синхронизация | 🟡 | 📋 |
| BACKLOG-065 | Удалить `findings_old` после проверки | 🟢 | 📋 |

### Бэклог v3.0.0 — ЗАКРЫТЫЕ (история)

| ID | Название | Закрыт в |
|----|----------|----------|
| BACKLOG-010 | S3/MinIO аудит-агент | v3.0.0 (день 31-32) |
| BACKLOG-013 | Безопасность (mTLS, секреты) | v3.0.0 (день 34) |
| BACKLOG-014 | Масштабирование (PG, Redis, Celery) | v3.0.0 (день 36-37) |
| BACKLOG-015 | WebUI редизайн | v3.0.0 (день 28) |
| BACKLOG-016 | Гибридная аутентификация | v3.0.0 (день 30) |
| BACKLOG-021 | Расширенный мониторинг | v3.7.0 |
| BACKLOG-026 | Стандартизация структуры | v3.0.0 (день 29) |
| BACKLOG-027 | Контейнеризация и деплой | v3.6.0 |
| BACKLOG-029 | AD интеграция + RBAC | v3.0.0 (день 33) |
| BACKLOG-030 | Архивация данных | v3.0.0 (день 35) |
| BACKLOG-034 | Secret Scanner интеграция | v3.4.0 |
| BACKLOG-037 | Heartbeat-thread для сканера | v3.7.0 |
| BACKLOG-038 | Прогресс-пинг в heartbeat | v3.7.0 |
| BACKLOG-041 | Prometheus/Grafana мониторинг | v3.7.0 |
| BACKLOG-042 | Alertmanager + алерты | v3.7.0 |
| BACKLOG-050 | Модель Findings (строка/фрагмент) | v3.9.0 |
| BACKLOG-051 | Шифрование находок (AES-256-GCM) | v3.9.0 |
| BACKLOG-052 | API находок + reveal + аудит | v3.9.0 |
| BACKLOG-053 | Сканер: построчное сканирование | v3.10.0 |
| BACKLOG-054 | Fingerprint + дедупликация | v3.10.0 |
| BACKLOG-055 | FP-фильтр перед отправкой | v3.10.0 |
| BACKLOG-056 | WebUI: находки + каталог (строки) | v3.11.0 |
| BACKLOG-057 | WebUI: reveal + FP | v3.11.0 |
| BACKLOG-058 | Фрагменты изображений (bounding box) | v3.12.0 |
| BACKLOG-059 | Бинарные: hex-дамп | v3.12.0 |
| BACKLOG-060 | Экспорт с маскированием | v3.12.0 |
| BACKLOG-061 | WebUI v3.8: legacy Findings (деградация) | v3.11.0 |
| BACKLOG-066 | MD5 → SHA-256 в `_legacy_fingerprint` | v3.11.0 |
| BACKLOG-067 | X-Total-Count в `/api/findings` | v3.12.0 |

---

## 🐛 БАГИ БЛОКА 2 (Auth/RBAC) — ЗАКРЫТЫ

### 🔴🔴 Критичные (закрыто в v3.13.9-v3.13.10)

| ID | Название | Закрыт в |
|----|----------|----------|
| BUG-039 | Refresh как access | v3.13.9 |
| BUG-046 | DELETE resources без RBAC | v3.13.9 |
| BUG-047 | DELETE tasks без auth | v3.13.9 |
| BUG-048 | DELETE scanner без auth + 500 | v3.13.9 |
| BUG-048b | Middleware пропускал JWT (machine-API) | v3.13.10 |

### 🔴 Важные (закрыто в v3.13.9)

| ID | Название |
|----|----------|
| BUG-037 | `_defaults.group_mapping` — ед.ч. vs мн.ч. |
| BUG-043 | `/api/catalog/tree` → 500 |
| BUG-045 | `/api/scanner/*` → 500 |
| BUG-049 | DELETE `/api/scanners/{id}` (webui) без RBAC |
| BUG-050 | DELETE `/api/audit/agents/{id}` без RBAC |
| BUG-051 | POST/PUT `/api/resources*` без RBAC |
| BUG-052 | POST `/api/tasks/create`, `/api/scanners/{id}/ping` без RBAC |
| BUG-053 | POST `/api/resources/create`, PUT `/api/access/alerts/{id}`, POST `/api/audit/report/*` без RBAC |
| BUG-054 | POST `/api/permissions/mode`, `/sync`, PUT alerts, POST generate без RBAC |
| BUG-055 | POST `/api/tasks/{id}/cancel` без RBAC |
| BUG-057 | Scanner legacy mode by default |
| BUG-059 | `POST /api/tasks/create` 500 |

### 🟡 Средние (закрыто в v3.13.9)

| ID | Название |
|----|----------|
| BUG-038 | TTL JWT не в env |
| BUG-041 | Reuse старого refresh |
| BUG-042 | `secure=False` hardcoded |
| BUG-044 | `context_before` не маскировал домен |
| BUG-058 | Manager fallback `line_text_encrypted` |

---

## 🐛 БАГИ БЛОКА 3 (Scanner deep) — В РАБОТЕ (ТЗ №3)

### 🔴 Критичные / важные

| ID | Название | Fix |
|----|----------|-----|
| **BUG-067** | Изображения не обрабатываются (stub в `scan_file`) | TASK-022 |
| **BUG-067b** | PDF-сканы не обрабатываются (`ocr_enabled=False`) | TASK-023 |
| **BUG-063** | `credit_card` не детектируется | TASK-024 |
| **BUG-066** | `url`-детектор ложно срабатывает на email-домены | TASK-025 |

### 🟡 Средние

| ID | Название | Fix |
|----|----------|-----|
| **BUG-061** | Сканер не восстанавливает HTTP после падения Manager | TASK-026 |
| **BUG-065** | `database_url`/`basic_auth`/`github_token`/`slack_token` falls back на `high_entropy` | TASK-027 |

### 🟢 Nice-to-have

| ID | Название | Fix |
|----|----------|-----|
| **BUG-062** | Избыточные логи при старте сканера | TASK-028 |

### 🟢 TEST-NOTE

| ID | Название |
|----|----------|
| TEST-NOTE-3.1 | `text_extensions` в JSON игнорируется (fallback работает) |
| TEST-NOTE-3.2 | `byte_range` для `.bin` не реализован (v3.1.0) |

---

## 📋 v3.1.0 — RUST + DLP + SIEM + HARDENING (📋 ПЛАНИРУЕТСЯ)

### План по дням

| День | Задача | BACKLOG/BUG | Приоритет |
|------|--------|-------------|-----------|
| 51-52 | Rust Scanner (ядро + интеграция) | BACKLOG-036 | 🔴 |
| 53 | ICAP Connector (DLP) | BACKLOG-032 | 🟡 |
| 54 | DLP Политики (WebUI) | BACKLOG-033 | 🟡 |
| 55 | SMB-сканер (на базе Rust) | BACKLOG-035 | 🟡 |
| 56 | Webhook для MinIO | BACKLOG-011 | 🟢 |
| 57 | **SIEM: генерация событий (Syslog + JSON)** | **BACKLOG-069** | 🔴 |
| 58 | **SIEM: экспорт findings/audit_logs (Syslog + JSON)** | **BACKLOG-070** | 🔴 |
| 59 | **SIEM: WebUI настройки коннекторов** | **BACKLOG-072** | 🟡 |
| 60 | Обработка архивов | BACKLOG-017 | 🟡 |
| 61 | **Per-scanner keys** (`scanner_id → key_id`) | **BACKLOG-068** | 🟡 |
| 62 | **Multi-key режим** (ротация без downtime) | — | 🟡 |
| 63 | **BOM fix + Scanner hardening** | **BUG-060** | 🟢 |
| 64 | Распределённая архитектура | BACKLOG-018 | 🔴 |
| 65 | Расширенный мониторинг | BACKLOG-063/064 | 🟡 |
| 66 | Red teaming, SAST, SCA | BACKLOG-022 | 🔴 |
| 67 | Релиз v3.1.0 | — | 🔴 |

### Бэклог v3.1.0

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| BACKLOG-036 | Rust Scanner (IPC, CIFS, NFS) | 🔴 | 📋 |
| BACKLOG-032 | ICAP Connector (DLP) | 🟡 | 📋 |
| BACKLOG-033 | DLP Политики (WebUI) | 🟡 | 📋 |
| BACKLOG-035 | SMB-сканер | 🟡 | 📋 |
| BACKLOG-040 | Параллельный батч-сканер | 🟡 | 📋 |
| BACKLOG-048 | Rate-limit bypass для тестов | 🟡 | 📋 |
| BACKLOG-049 | Автоматизация chaos-теста scanner inactive | 🟡 | 📋 |
| BACKLOG-063 | Presidio: производительность | 🟡 | 📋 |
| BACKLOG-064 | Бенчмарк сканирования | 🟢 | 📋 |
| **BACKLOG-068** | **Per-scanner keys (`scanner_id → key_id`)** | 🟡 | 📋 |
| **BACKLOG-069** | **SIEM: генерация событий ИБ (Syslog RFC 5424 + JSON)** | 🔴 | 📋 |
| **BACKLOG-070** | **SIEM: экспорт findings/audit_logs (Syslog + JSON)** | 🔴 | 📋 |
| **BACKLOG-072** | **SIEM: WebUI настройки коннекторов** | 🟡 | 📋 |
| **BUG-060** | **BOM ломает маскирование email** | 🟢 | 📋 |
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
| **CIFS (SMB)** | Rust `pavao` + `libsmbclient` |
| **NFS** | Rust `nfs-rs` — чистый Rust, авто-монтирование |
| **Кроссплатформенность** | Windows + Linux |
| **Fallback** | Старый Python-сканер (`scanner/`) |

### 🔧 BACKLOG-068: Per-scanner keys — детали

**Проблема:** v3.0.0 — один `FINDINGS_ENCRYPTION_KEY` на всю инсталляцию. Компромисс одного Scanner = компромисс **всех** находок.

**Решение:** каждому Scanner — свой ключ. Manager хранит `scanner_id → key_id`.

| Аспект | Решение |
|--------|---------|
| **Генерация** | `generate_findings_keys.py --scanner-id N` |
| **Хранение (Manager)** | Таблица `scanner_keys(scanner_id, key_id, created_at, rotated_at)` |
| **Хранение (Scanner)** | ENV `FINDINGS_ENCRYPTION_KEY` (уникальные) |
| **Расшифровка** | Manager по `findings.encryption_key_id` → mapping |
| **Ротация** | Для одного Scanner (без downtime для остальных) |
| **Миграция** | Старые находки остаются под общим `key_id` (read-only) |

### 🔧 BACKLOG-069: SIEM — генерация событий

**Формат:** Syslog (RFC 5424) + JSON (HTTP webhook).

**События:**

| Источник | Событие | Severity |
|----------|---------|----------|
| Findings | `finding_detected` | по severity |
| Findings | `finding_revealed` | high |
| Findings | `finding_confirmed` | medium |
| Findings | `finding_false_positive` | low |
| Scanner | `scan_started` / `scan_completed` / `scan_failed` | info/high |
| Scanner | `scanner_inactive` | warning |
| Audit | `auth_login` / `auth_failed` | info/medium |
| Audit | `user_created` / `role_changed` | medium |
| Retention | `retention_run` | info |

**Транспорт:**
- **Syslog:** UDP / TCP / TLS (RFC 5424).
- **JSON:** HTTP/HTTPS webhook (Splunk HEC-совместимый).

**Модули:**
manager/src/siem/
├── generator.py # генерация событий
├── config.py # конфигурация
├── senders/
│ ├── syslog_sender.py # RFC 5424
│ └── json_sender.py # HTTP/HTTPS
└── queue.py # dead-letter + retry

text

**Ключевые свойства:**
- Асинхронная отправка (Celery).
- Retry с backoff.
- Dead-letter queue (Redis).
- Метрики: `dcap_siem_events_sent_total`, `dcap_siem_events_failed_total`.
- В SIEM — **только маскированные** данные (без `reveal`).

### 🔧 BACKLOG-070: SIEM — экспорт

**Экспорт:**
- `findings` (masked).
- `audit_logs` (полные).
- `scan_tasks` (completed/failed).
- `failed_files`.
- `access_alerts`.

**Форматы:** Syslog RFC 5424, JSON.

### 🔧 BACKLOG-072: SIEM — WebUI

**Страница `/settings/siem`:**
- Формы: Syslog (host, port, protocol, TLS), JSON (URL, token).
- Выбор событий (чекбоксы).
- Кнопка «Test» — отправить тестовое событие.
- Метрики — отправлено/ошибок за 24ч.

### 🔧 BUG-060: BOM fix

**Проблема:** BOM (`\ufeff`) в начале строки ломает regex `([\w.+-]+)@...` в `_mask_email`.

**Fix:** `s.lstrip("\ufeff")` перед маскированием; regex `[\s\ufeff]`.

**Компонент:** `scanner/src/encryption.py::_mask_email`.

---

## 📋 v4.0.0 — AI/ML + DISTRIBUTED (📋 ПЛАНИРУЕТСЯ)

| День | Задача | Приоритет |
|------|--------|-----------|
| 68-69 | ML-классификаторы | 🔴 |
| 70 | Аномалии в аудите | 🟡 |
| 71-72 | Zero-Trust архитектура | 🔴 |
| 73 | Распределённый Manager | 🔴 |
| 74 | **SIEM: Kafka / Kinesis (streaming)** | 🟡 |
| 75 | Версионирование данных | 🟢 |
| 76 | Релиз v4.0.0 | 🔴 |

---

## 📊 Статистика

| Версия | Задач | Выполнено | Прогресс |
|--------|-------|-----------|----------|
| v1.0.0 | 8 | 8 | 100% ✅ |
| v2.0.0 | 10 | 10 | 100% ✅ |
| v2.0.1 | 4 | 4 | 100% ✅ |
| v2.1.0 | 5 | 5 | 100% ✅ |
| **v3.0.0** | **35 + 22 (BUG) + 6 (TASK) + 7 (TASK №3)** | **56** | **80% 🔄** |
| v3.1.0 | 22 | 0 | 0% 📋 |
| v4.0.0 | 9 | 0 | 0% 📋 |
| **ИТОГО** | **128** | **83** | **65%** |

### Детали v3.0.0

| Категория | Всего | Закрыто | Открыто |
|-----------|-------|---------|---------|
| Дни плана (28-50) | 26 | 22 | 4 |
| Бэклог (BACKLOG-010…065) | 35 | 33 | 2 |
| Баги Блока 2 (BUG-037…059) | 17 | 17 | 0 |
| TASK ENV-ключи (TASK-016…021) | 6 | 3 | 3 |
| TASK Scanner deep (TASK-022…028) | 7 | 0 | 7 |
| **Итого v3.0.0** | **91** | **75** | **16** |

---

## 📝 Шаблон новой задачи
| BACKLOG-XXX / BUG-XXX / TASK-XXX | Название | 🔴/🟡/🟢 | 📋/🔄/✅/❌ |

text

**Приоритеты:** 🔴 критично / 🟡 важно / 🟢 nice-to-have
**Статусы:** 📋 запланировано / 🔄 в работе / ✅ выполнено / ❌ отменено

---

## 📚 Связанные документы

- **`STATE.md`** — текущее состояние проекта
- **`STATE_TEST_SESSION.md`** — протокол тестирования
- **`ARCHITECTURE.md`** — архитектура, модели, API, **SIEM-интеграция**
- **`TZ_FIX_SPRINT.md`** — ТЗ №1 (Auth/RBAC) — закрыто
- **`TZ_FIX_SPRINT_2.md`** — ТЗ №2 (ENV-ключи)
- **`TZ_FIX_SPRINT_3.md`** — ТЗ №3 (Scanner deep)
- **`SECURITY.md`** — политика безопасности
- **`docs/security_checklist.md`** — чеклист production
- **`docs/admin-guide/05-security.md`** — управление ключами ENV
- **`docs/admin-guide/06-scanner.md`** — ENV сканера, fail-fast
- **`CHANGELOG.md`** — история версий

---

**Актуально на:** 20.09.2026
**Версия:** v3.13.10
**Следующая цель:** v3.0.0 (релиз) — осталось **16 задач**