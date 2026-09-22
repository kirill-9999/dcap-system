# 🗺️ ROADMAP.md — План развития и бэклог DCAP

> **Обновляется архитектором.** План — редко, бэклог — по мере.
> Текущее состояние — в `STATE.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 21.09.2026 (вечер)
**Стратегия:** Windows First → Linux → S3/MinIO → Enterprise Ready → Rust + DLP + SIEM

---

## 🚀 Вехи

| Версия | Статус | Ключевые фичи |
|--------|--------|---------------|
| v1.0.0-v2.1.0 | ✅ | Обнаружение, классификация, WebUI, Linux-агент |
| **v3.0.0** | **🔄 Финальный этап** | **Enterprise Ready: S3, AD, mTLS, архивация, Findings Refactor, ENV-ключи, RBAC, админ-руководство, GitHub** |
| v3.1.0 | 📋 | Rust Scanner, DLP/ICAP, SMB, Webhook, облака, **Auth Hardening, Per-scanner keys, BOM fix, SIEM-интеграция** |
| v4.0.0 | 📋 | ML-классификаторы, Zero-Trust, распределённый Manager, Kafka/Kinesis SIEM |

---

## 📋 v3.0.0 — ENTERPRISE READY (🔄 ФИНАЛЬНЫЙ ЭТАП)

### План по дням

| День | Задача | BACKLOG/BUG | Статус |
|------|--------|-------------|--------|
| 28-40.4 | WebUI, AD, безопасность, Findings Refactor | BACKLOG-010…067 | ✅ |
| 42.1-42.4 | Админ-руководство | — | ✅ |
| 43 | Блок 1 (фиксы): BUG-034/035/027/022 + Deploy/Config + WebUI | — | ✅ v3.13.3-4 |
| 43.3 | BUG-022.9 (приоритизация категорий) | — | ✅ v3.13.6 |
| 44 | BUG-034 (зависшие задачи) + AD-упаковка | — | ✅ v3.13.7-8 |
| 45 (тест) | Мастер-сессия: Блок 2 (Auth/RBAC) | — | ✅ `STATE_TEST_SESSION.md` |
| 45 (fix1) | Fix-спринт №1: Auth/RBAC (15 багов) | BUG-037…059 | ✅ **v3.13.9** |
| 46 (fix2) | Fix-спринт №2: middleware (BUG-048b) | BUG-048b | ✅ **v3.13.10** |
| 46 (fix3) | Fix-спринт №3: ENV-ключи (TASK-016…021) | TASK-016…021 | ✅ |
| 46.5 (fix3) | Fix-спринт №3: OCR, HTTP-retry, Luhn | BUG-061, 063, 067 | ✅ **v3.13.12** |
| 46.7 (fix4) | Fix-спринт №4: OCR-секция + двухпроходный Presidio | BUG-067c, 063 | ✅ **v3.13.13** |
| 47 (fix5) | Fix-спринт №5: BUG-065, 066b, 067d, 069/070 | TASK-033…036 | ✅ **v3.13.14** |
| 47 (fix6) | Fix-спринт №6: BUG-071…074 | TASK-037…039 | ✅ **v3.13.15** |
| 47 (fix7) | Fix-спринт №7: BUG-075 (url = домен email) | TASK-040 | ✅ **v3.13.16** |
| 47 (test) | Мастер-сессия: Блок 3 (Scanner deep) — финализация | — | 📋 |
| 48 | Блок 8 (Мониторинг) | — | 📋 |
| 49 | Блок 5 (WebUI) | — | 📋 |
| 50 | Блок 7 (Retention) | — | 📋 |
| 51 | GitHub-пакет (BACKLOG-028) | BACKLOG-028/046 | 📋 |
| 52 | Релиз v3.0.0 | — | 📋 |

### Бэклог v3.0.0 — активные задачи

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| **TASK-033** | BUG-066b: url-over-email в `scan_text`/`scan_line` | 🔴 | ✅ v3.13.14 |
| **TASK-034** | BUG-067d: `image_region`/`ocr`/`bounding_box` | 🟡 | ✅ v3.13.14 |
| **TASK-035** | BUG-069/070: spaCy noise | 🟢 | ✅ v3.13.14 |
| **TASK-036** | BUG-065: credentials — 5 изменений | 🟡 | ✅ v3.13.14 |
| **TASK-037** | BUG-071/074: url-over-email по line_text (TASK-033 расширено) | 🔴 | ✅ v3.13.15 |
| **TASK-038** | BUG-072: аббревиатуры INN/SSN/DOB (spaCy noise) | 🟡 | ✅ v3.13.15 |
| **TASK-039** | BUG-073: uk_nhs при phone в строке | 🟡 | ✅ v3.13.15 |
| **TASK-040** | BUG-075: url = доменная часть email | 🔴 | ✅ v3.13.16 |
| BACKLOG-028 | Публикация на GitHub | 🔴 | 📋 51 |
| BACKLOG-039 | Аудит NOT NULL полей | 🟡 | 📋 |
| BACKLOG-044 | Защита `/metrics` (JWT/basic_auth) | 🟡 | 📋 production |
| BACKLOG-045 | Параметризация портов экспортеров | 🟢 | 📋 |
| BACKLOG-046 | Полный E2E-прогон на CI | 🔴 | 📋 51 |
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

### 🔴🔴 Критичные

| ID | Название | Закрыт в |
|----|----------|----------|
| BUG-039 | Refresh как access | v3.13.9 |
| BUG-046 | DELETE resources без RBAC | v3.13.9 |
| BUG-047 | DELETE tasks без auth | v3.13.9 |
| BUG-048 | DELETE scanner без auth + 500 | v3.13.9 |
| BUG-048b | Middleware пропускал JWT (machine-API) | v3.13.10 |

### 🔴 Важные (v3.13.9)

| ID | Название |
|----|----------|
| BUG-037 | `_defaults.group_mapping` — ед.ч. vs мн.ч. |
| BUG-043 | `/api/catalog/tree` → 500 |
| BUG-045 | `/api/scanner/*` → 500 |
| BUG-049…055 | 7 unprotected write-эндпоинтов |
| BUG-057 | Scanner legacy mode by default |
| BUG-059 | `POST /api/tasks/create` 500 |

### 🟡 Средние (v3.13.9)

| ID | Название |
|----|----------|
| BUG-038 | TTL JWT не в env |
| BUG-041 | Reuse старого refresh |
| BUG-042 | `secure=False` hardcoded |
| BUG-044 | `context_before` не маскировал домен |
| BUG-058 | Manager fallback `line_text_encrypted` |

---

## 🐛 БАГИ БЛОКА 3 (Scanner deep)

### ✅ Закрытые

| ID | Название | Закрыт в |
|----|----------|----------|
| BUG-061 | Сканер не восстанавливает HTTP | v3.13.12 |
| BUG-062 | Избыточные логи | v3.13.12 |
| BUG-063 | `credit_card` не детектируется | v3.13.13 |
| BUG-067c | OCR (`ocr_enabled`) | v3.13.13 |
| BUG-066b | `scan_text` не фильтрует url-over-email | v3.13.14 |
| BUG-067d | OCR findings не помечаются `image_region`/`ocr` | v3.13.14 |
| BUG-065 | `database_url`/`github_token`/`slack_token`/`basic_auth` | v3.13.14 |
| BUG-069 | Ложные `date_time` из `en`-прохода | v3.13.14 |
| BUG-070 | Ложные `person`/`organization` из `en`-прохода | v3.13.14 |
| BUG-071 | url-over-email не фильтруется (2 случая) | v3.13.15 |
| BUG-072 | `organization = "INN"` (аббревиатура) | v3.13.15 |
| BUG-073 | uk_nhs на US-телефоне | v3.13.15 |
| BUG-074 | email из URL-логина (`postgresql://...@...`) | v3.13.15 |
| BUG-075 | url = доменная часть email (task 34: 5 url) | v3.13.16 |

### 🟢 TEST-NOTE

| ID | Название |
|----|----------|
| TEST-NOTE-3.1 | `text_extensions` в JSON игнорируется (fallback) |
| TEST-NOTE-3.2 | `byte_range` для `.bin` не реализован (v3.1.0) |
| TEST-NOTE-2.E2E | E2E-тест ротации (отложен) |

---

## 📋 v3.1.0 — RUST + DLP + SIEM + HARDENING

### План по дням

| День | Задача | BACKLOG/BUG | Приоритет |
|------|--------|-------------|-----------|
| 53-54 | Rust Scanner (ядро + интеграция) | BACKLOG-036 | 🔴 |
| 55 | ICAP Connector (DLP) | BACKLOG-032 | 🟡 |
| 56 | DLP Политики (WebUI) | BACKLOG-033 | 🟡 |
| 57 | SMB-сканер (Rust) | BACKLOG-035 | 🟡 |
| 58 | **SIEM: генерация событий (Syslog + JSON)** | **BACKLOG-069** | 🔴 |
| 59 | **SIEM: экспорт findings/audit** | **BACKLOG-070** | 🔴 |
| 60 | **SIEM: WebUI настройки** | **BACKLOG-072** | 🟡 |
| 61 | **Per-scanner keys** | **BACKLOG-068** | 🟡 |
| 62 | **Multi-key режим** (ротация без downtime) | — | 🟡 |
| 63 | **BOM fix + Scanner hardening** | **BUG-060** | 🟢 |
| 64 | Обработка архивов | BACKLOG-017 | 🟡 |
| 65 | Распределённая архитектура | BACKLOG-018 | 🔴 |
| 66 | Расширенный мониторинг | BACKLOG-063/064 | 🟡 |
| 67 | Red teaming, SAST, SCA | BACKLOG-022 | 🔴 |
| 68 | Релиз v3.1.0 | — | 🔴 |

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
| **BACKLOG-068** | **Per-scanner keys** | 🟡 | 📋 |
| **BACKLOG-069** | **SIEM: генерация событий (Syslog + JSON)** | 🔴 | 📋 |
| **BACKLOG-070** | **SIEM: экспорт findings/audit** | 🔴 | 📋 |
| **BACKLOG-072** | **SIEM: WebUI настройки** | 🟡 | 📋 |
| **BUG-060** | **BOM ломает маскирование email** | 🟢 | 📋 |
| BACKLOG-011 | Webhook для MinIO | 🟢 | 📋 |
| BACKLOG-012 | Облачные хранилища | 🟢 | 📋 |
| BACKLOG-017 | Обработка архивов | 🟡 | 📋 |
| BACKLOG-018 | Распределённая архитектура | 🔴 | 📋 |
| BACKLOG-022 | Red teaming, SAST, SCA | 🔴 | 📋 |

---

## 📋 v4.0.0 — AI/ML + DISTRIBUTED

| День | Задача | Приоритет |
|------|--------|-----------|
| 69-70 | ML-классификаторы | 🔴 |
| 71 | Аномалии в аудите | 🟡 |
| 72-73 | Zero-Trust архитектура | 🔴 |
| 74 | Распределённый Manager | 🔴 |
| 75 | **SIEM: Kafka / Kinesis (streaming)** | 🟡 |
| 76 | Версионирование данных | 🟢 |
| 77 | Релиз v4.0.0 | 🔴 |

---

## 📊 Статистика

| Версия | Задач | Выполнено | Прогресс |
|--------|-------|-----------|----------|
| v1.0.0-v2.1.0 | 27 | 27 | 100% ✅ |
| **v3.0.0** | **35 + 22 + 6 + 4 = 67** | **56 + 4 = 60** | **90% 🔄** |
| v3.1.0 | 22 | 0 | 0% 📋 |
| v4.0.0 | 9 | 0 | 0% 📋 |
| **ИТОГО** | **125** | **87** | **70%** |

---

## 📝 Шаблон новой задачи
| BACKLOG-XXX / BUG-XXX / TASK-XXX | Название | 🔴/🟡/🟢 | 📋/🔄/✅/❌ |

text

**Приоритеты:** 🔴 критично / 🟡 важно / 🟢 nice-to-have
**Статусы:** 📋 запланировано / 🔄 в работе / ✅ выполнено / ❌ отменено

---

## 📚 Связанные документы

- **`STATE.md`** — текущее состояние проекта.
- **`STATE_TEST_SESSION.md`** — протокол тестирования.
- **`ARCHITECTURE.md`** — архитектура, модели, API, SIEM.
- **`TZ_FIX_SPRINT.md`** — ТЗ №1 (закрыто).
- **`TZ_FIX_SPRINT_2.md`** — ТЗ №2 (закрыто).
- **`TZ_FIX_SPRINT_3.md`** — ТЗ №3 (частично).
- **`TZ_FIX_SPRINT_4.md`** — ТЗ №4 (частично).
- **`TZ_FIX_SPRINT_5.md`** — ТЗ №5 (в работе).
- **`SECURITY.md`**, **`docs/security_checklist.md`**, **`docs/admin-guide/05-security.md`**.

---

**Актуально на:** 21.09.2026 (вечер)
**Версия:** v3.13.13
**Следующая цель:** v3.0.0 (релиз) — осталось 7 задач (ТЗ №5) + Блок 8 + Блок 5 + Блок 7 + GitHub