ROADMAP.md — полный (обновлённый)
markdown
# 🗺️ ROADMAP.md — План развития и бэклог DCAP

> **Обновляется архитектором.** План — редко, бэклог — по мере.
> Текущее состояние — в `STATE.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 20.09.2026
**Стратегия:** Windows First → Linux → S3/MinIO → Enterprise Ready → Rust + DLP

---

## 🚀 Вехи

| Версия | Статус | Ключевые фичи |
|--------|--------|---------------|
| v1.0.0 | ✅ | Обнаружение, классификация, каталог, WebUI |
| v2.0.0 | ✅ | Управление доступом, аудит Windows (ядро) |
| v2.0.1 | ✅ | WebUI аудита, отчёты |
| v2.1.0 | ✅ | Linux-агент, унификация форматов |
| **v3.0.0** | **🔄 Финальный этап** | **Enterprise Ready: S3, AD, mTLS, архивация, Findings Refactor, ENV-ключи, RBAC, админ-руководство, GitHub** |
| v3.1.0 | 📋 | Rust Scanner, DLP/ICAP, SMB, Webhook, облака, **Auth Hardening, Per-scanner keys, BOM fix** |
| v4.0.0 | 📋 | ML-классификаторы, Zero-Trust, распределённый Manager, SIEM |

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
| 46 (fix3) | **Fix-спринт №3: ENV-ключи (TASK-016…021)** | **TASK-016…021** | ✅ **v3.13.11** |
| 47 | Повторный RBAC-прогон (полная матрица) | — | 📋 |
| 48 | Публикация на GitHub | BACKLOG-028/046 | 📋 |
| 49 | Релиз v3.0.0 | — | 📋 |

### Бэклог v3.0.0 — активные задачи

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| **TASK-016** | `scripts/reencrypt_findings.py` (ENV-ключи) | 🔴 | ✅ v3.13.11 |
| **TASK-017** | Fail-fast сканера (BUG-057) | 🔴 | ✅ v3.13.9 |
| **TASK-018** | Убрать Docker Secrets для Findings | 🟡 | ✅ v3.13.11 |
| **TASK-019** | Обновить документацию (ENV-ключи) | 🟡 | ✅ (done) |
| **TASK-020** | E2E-тест ротации ключей | 🟡 | ✅ v3.13.11 |
| **TASK-021** | Закрыть ТЗ №1 | 🟢 | ✅ v3.13.9 |
| BACKLOG-028 | Публикация на GitHub | 🔴 | 📋 48 |
| BACKLOG-039 | Аудит NOT NULL полей | 🟡 | 📋 |
| BACKLOG-043 | Прогресс сканера в WebUI | 🟡 | ✅ (в 40.3) |
| BACKLOG-044 | Защита `/metrics` (JWT/basic_auth) | 🟡 | 📋 production |
| BACKLOG-045 | Параметризация портов экспортеров | 🟢 | 📋 |
| BACKLOG-046 | Полный E2E-прогон на CI | 🔴 | 📋 48 |
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
| BACKLOG-062 | Удалить `findings_old` | 📋 v3.0.0 |
| BACKLOG-066 | MD5 → SHA-256 в `_legacy_fingerprint` | v3.11.0 |
| BACKLOG-067 | X-Total-Count в `/api/findings` | v3.12.0 |

### 🔧 BACKLOG-050…067: Findings Refactor — детали (закрыто)

**Проблема:** находка = файл. Нельзя посмотреть, где именно найдено, удалить одно FP, дедуплицировать при повторном скане.

**Решение:** находка = строка/фрагмент файла.

**Итог:** ✅ реализовано в v3.9.0-v3.12.0 (см. `ARCHITECTURE.md`).

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

### 🟢 TEST-NOTE (не баги, к документированию)

| ID | Название |
|----|----------|
| TEST-NOTE-2.3c | Единый ответ `"Authentication required"` на auth-провалы |
| TEST-NOTE-2.3g | `/refresh` cookie-only, тело игнорируется |
| TEST-NOTE-2.3k | Logout stateless |
| TEST-NOTE-2.3m | `/check` дублирует `/me` |
| TEST-NOTE-2.4b | ARCHITECTURE.md расходится с OpenAPI (catalog) |
| TEST-NOTE-2.4g | Разные форматы пагинации |
| TEST-NOTE-2.5b | Документировать env-ключи сканера ✅ |
| TEST-NOTE-2.5c | Bulk: `finding_ids`, не `ids` |
| TEST-NOTE-2.6b | `token_type: "bearer"` (lowercase) |
| TEST-NOTE-2.6c | `/api/tasks/create` — кириллица в `message`, PS 5.1 не читает |

### 🟢 Новый минорный баг (v3.1.0)

| ID | Название | Приоритет |
|----|----------|-----------|
| **BUG-060** | BOM (`\ufeff`) ломает маскирование email в `mask_context`/`mask_line` | 🟢 v3.1.0 |

---

## 📋 v3.1.0 — RUST + DLP + HARDENING (📋 ПЛАНИРУЕТСЯ)

### План по дням

| День | Задача | BACKLOG/BUG | Приоритет |
|------|--------|-------------|-----------|
| 49-50 | Rust Scanner (ядро + интеграция) | BACKLOG-036 | 🔴 |
| 51 | ICAP Connector (DLP) | BACKLOG-032 | 🟡 |
| 52 | DLP Политики (WebUI) | BACKLOG-033 | 🟡 |
| 53 | SMB-сканер (на базе Rust) | BACKLOG-035 | 🟡 |
| 54 | Webhook для MinIO | BACKLOG-011 | 🟢 |
| 55 | Аудит для облачных хранилищ | BACKLOG-012 | 🟢 |
| 56 | Обработка архивов | BACKLOG-017 | 🟡 |
| 57 | **Auth Hardening** (`jti`+`iat`+Redis blacklist — уже сделано в v3.13.9, доработать) | BUG-041 | ✅ частично |
| 58 | **Per-scanner keys** (`scanner_id → key_id`) | **BACKLOG-068** | 🟡 |
| 59 | **Multi-key режим** (ротация без downtime) | — | 🟡 |
| 60 | **BOM fix + Scanner hardening** | **BUG-060** | 🟢 |
| 61 | Распределённая архитектура | BACKLOG-018 | 🔴 |
| 62 | Расширенный мониторинг | BACKLOG-063/064 | 🟡 |
| 63 | Red teaming, SAST, SCA | BACKLOG-022 | 🔴 |
| 64 | Релиз v3.1.0 | — | 🔴 |

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

### 🔧 BUG-060: BOM fix — детали

**Проблема:** BOM (`\ufeff`) в начале строки ломает regex `([\w.+-]+)@...` в `_mask_email`.

**Fix:**
- `s.lstrip("\ufeff")` перед маскированием.
- Или regex `[\s\ufeff]` для whitespace.
- Или `[\w.+-]*` с BOM-исключением.

**Компонент:** `scanner/src/encryption.py::_mask_email`, `mask_line`, `mask_context`.

**Приоритет:** 🟢 (только **2 из 1200** findings; только **первая строка** BOM-файлов).

---

## 📋 v4.0.0 — AI/ML + DISTRIBUTED (📋 ПЛАНИРУЕТСЯ)

| День | Задача | Приоритет |
|------|--------|-----------|
| 65-66 | ML-классификаторы | 🔴 |
| 67 | Аномалии в аудите | 🟡 |
| 68-69 | Zero-Trust архитектура | 🔴 |
| 70 | Распределённый Manager | 🔴 |
| 71 | Интеграция с SIEM | 🟡 |
| 72 | Версионирование данных | 🟢 |
| 73 | Релиз v4.0.0 | 🔴 |

---

## 📊 Статистика

| Версия | Задач | Выполнено | Прогресс |
|--------|-------|-----------|----------|
| v1.0.0 | 8 | 8 | 100% ✅ |
| v2.0.0 | 10 | 10 | 100% ✅ |
| v2.0.1 | 4 | 4 | 100% ✅ |
| v2.1.0 | 5 | 5 | 100% ✅ |
| **v3.0.0** | **35 + 22 (BUG) + 6 (TASK)** | **56** | **89% 🔄** |
| v3.1.0 | 17 | 0 | 0% 📋 |
| v4.0.0 | 9 | 0 | 0% 📋 |
| **ИТОГО** | **116** | **83** | **72%** |

### Детали v3.0.0

| Категория | Всего | Закрыто | Открыто |
|-----------|-------|---------|---------|
| Дни плана (28-49) | 25 | 22 | 3 |
| Бэклог (BACKLOG-010…065) | 35 | 33 | 2 |
| Баги Блока 2 (BUG-037…059) | 17 | 17 | 0 |
| TASK (ENV-ключи) | 6 | 1 | 5 |
| **Итого v3.0.0** | **63** | **56** | **7** |

---

## 📝 Шаблон новой задачи
| BACKLOG-XXX / BUG-XXX / TASK-XXX | Название | 🔴/🟡/🟢 | 📋/🔄/✅/❌ |

text

**Приоритеты:** 🔴 критично / 🟡 важно / 🟢 nice-to-have
**Статусы:** 📋 запланировано / 🔄 в работе / ✅ выполнено / ❌ отменено

---

## 📚 Связанные документы

- **`STATE.md`** — текущее состояние проекта
- **`STATE_TEST_SESSION.md`** — протокол тестирования (Блок 2 закрыт)
- **`ARCHITECTURE.md`** — архитектура, модели, API
- **`TZ_FIX_SPRINT.md`** — ТЗ №1 (Auth/RBAC) — закрыто
- **`TZ_FIX_SPRINT_2.md`** — ТЗ №2 (ENV-ключи) — готово к запуску
- **`SECURITY.md`** — политика безопасности
- **`docs/security_checklist.md`** — чеклист production
- **`docs/admin-guide/05-security.md`** — управление ключами ENV
- **`docs/admin-guide/06-scanner.md`** — ENV сканера, fail-fast
- **`CHANGELOG.md`** — история версий

---

**Актуально на:** 20.09.2026
**Версия:** v3.13.10
**Следующая цель:** v3.0.0 (релиз) — осталось **7 задач** (ТЗ №2 + GitHub + релиз)
🎯 Итого в ROADMAP
Что изменилось:

Даты/статусы обновлены:

45 (fix1) — ✅ v3.13.9

46 (fix2) — ✅ v3.13.10

46 (fix3) — 📋 ТЗ №2 (следующий)

Бэклог v3.0.0:

Новый раздел «Бэклог — ЗАКРЫТЫЕ (история)» — 29 задач перенесены.

Активные — 14 (TASK-016…021 + BACKLOG-028/039/044/045/046/047/065).

Новый раздел «БАГИ БЛОКА 2»:

Критичные (5) — ✅

Важные (12) — ✅

Средние (5) — ✅

TEST-NOTE (10) — 🟢

BUG-060 (BOM) — 🟢 v3.1.0

v3.1.0 обновлён:

Добавлен BUG-060 (BOM fix).

Уточнён Auth Hardening — уже частично сделано.

Статистика:

v3.0.0: 63 задачи, 56 закрыто (89%).

ИТОГО: 116 задач, 83 (72%).

Детализация:

BACKLOG-068 (Per-scanner keys) — таблица.

BUG-060 (BOM fix) — таблица.

Связанные документы.

Остаток v3.0.0:

ТЗ №2 (5 задач: reencrypt, fail-fast, Docker Secrets, E2E, ТЗ-close).

GitHub (BACKLOG-028/046).

Релиз v3.0.0.

Мелочи (BACKLOG-039/044/045/047/065).

Общий прогресс проекта: 72% (83/116 задач).

Следующий шаг: запуск ТЗ №2.