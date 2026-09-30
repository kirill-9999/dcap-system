# 🗺️ ROADMAP.md — План развития и бэклог DCAP

> **Обновляется архитектором.** План — редко, бэклог — по мере.
> Текущее состояние — в `STATE.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 30.09.2026
**Стратегия:** Windows First → Linux → S3/MinIO → Enterprise Ready → Rust + DLP + SIEM

---

## 🚀 Вехи

| Версия | Статус | Ключевые фичи |
|--------|--------|---------------|
| v1.0.0-v2.1.0 | ✅ | Обнаружение, классификация, WebUI, Linux-агент |
| **v3.0.0** | **🔄 Финальный этап** | **Enterprise Ready: S3, AD, mTLS, архивация, Findings Refactor, ENV-ключи, RBAC, админ-руководство, GitHub** |
| v3.1.0 | 📋 | Rust Scanner (CIFS/NFS), DLP/ICAP, SMB, Webhook, облака, **Auth Hardening, Per-scanner keys, BOM fix, SIEM-интеграция**, **Cython-оптимизация, быстрые regex** |
| v4.0.0 | 📋 | ML-классификаторы, Zero-Trust, распределённый Manager, Kafka/Kinesis SIEM |

---

## 📋 v3.0.0 — ENTERPRISE READY (🔄 ФИНАЛЬНЫЙ ЭТАП)

### План по дням

| День | Задача | BACKLOG/BUG | Статус |
|------|--------|-------------|--------|
| 28-40.4 | WebUI, AD, безопасность, Findings Refactor | BACKLOG-010…067 | ✅ |
| 42.1-42.4 | Админ-руководство | — | ✅ |
| 43-44 | Блок 1 + AD-контейнер | — | ✅ v3.13.3-8 |
| 45 (тест) | Мастер-сессия: Блок 2 (Auth/RBAC) | — | ✅ |
| 45 (fix1) | Fix-спринт №1: Auth/RBAC (15 багов) | BUG-037…059 | ✅ **v3.13.9** |
| 46 (fix2) | Fix-спринт №2: middleware (BUG-048b) | BUG-048b | ✅ **v3.13.10** |
| 46 (fix3) | Fix-спринт №2: ENV-ключи | TASK-016…021 | ✅ **v3.13.11** |
| 46.5 (fix3) | Fix-спринт №3: OCR, HTTP-retry, Luhn | BUG-061, 063, 067 | ✅ **v3.13.12** |
| 46.7 (fix4) | Fix-спринт №4: OCR-секция + Presidio ru+en | BUG-067c, 063 | ✅ **v3.13.13** |
| 46.8 (fix5) | Fix-спринт №5: BUG-065, 066b, 067d, 069/070 | TASK-033…036 | ✅ **v3.13.14** |
| 46.9 (fix6) | Fix-спринт №6: BUG-071…074 | TASK-037…039 | ✅ **v3.13.15** |
| 46.10 (fix7) | Fix-спринт №7: BUG-075 | TASK-040 | ✅ **v3.13.16** |
| 47.3 (bug077) | BUG-077: bbox=None для OCR + fallback full-image | TASK-041…043 | ✅ **v3.13.17** |
| 47.4 (bug077 diag) | BUG-077 diag: Manager дефолтил bbox (H3) | TASK-044 | ✅ **v3.13.18** |
| 47.5 (BACKLOG-086) | Встраивание OCR-фрагментов в БД | TASK-045…050 | ✅ **v3.13.19** |
| 47.6 (BUG-080/081) | Reliability сканера: heartbeat backoff + graceful shutdown | TASK-051…052 | ✅ **v3.13.20** |
| 47.7 (BUG-086) | Masking контекстов: `_CONTEXT_PATTERNS` (критический блокер) | TASK-053 | ✅ **v3.13.21** |
| 47 (test) | Мастер-сессия: Блок 3 (Scanner deep) | — | ✅ **ЗАКРЫТ** |
| 47.2 (test) | Мастер-сессия: Блок 8 (Мониторинг) | — | ✅ **ЗАКРЫТ** |
| 48 (Блок 5, п.2.3) | Фильтры/пагинация/аудит/экспорт WebUI | TASK-054…059 | ✅ **v3.13.22** |
| 48.1 (диагностика) | «BUG-087» аудит reveal: ложное срабатывание (`CURRENT_USER`) | TASK-060 | ✅ **v3.13.23** |
| 48.2 (BUG-095) | Аудит аутентификации и управления пользователями | TASK-061…062 | ✅ **v3.13.24** |
| 48.3 (BUG-096/096b/097) | `/false-positives` 500, устаревшие E2E, зависшие задания | TASK-064…066 | ✅ **v3.13.25** |
| 49 (BUG-098…101) | PATCH/bulk/DELETE аудит, reset review-полей, FP-пагинация, FP `file_path` | TASK-067…071 | ✅ **v3.13.26** |
| 49.5 (Блок 5, п.7) | Stats — `GET /api/findings/stats` | — | 📋 **следующий** |
| 49.6 (Блок 5, п.13) | Legacy `/count` | — | 📋 |
| 49.7 (Блок 5, п.14) | WebUI визуально | — | 📋 |
| 49.8 (Блок 5, п.15) | Регрессия | — | 📋 |
| 50 | ~~Блок 7 (Retention)~~ — BUG-102 (Mapper[Finding] в Celery) | BUG-102 | ✅ **v3.13.27** |
| 51 | Блок 6 (Агенты — тестирование) | BACKLOG-080…082 | 📋 |
| 52 | GitHub-пакет (BACKLOG-028) | BACKLOG-028/046 | 📋 |
| 53 | Релиз v3.0.0 | — | 📋 |

### Бэклог v3.0.0 — активные задачи

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| **BACKLOG-028** | Публикация на GitHub | 🔴 | 📋 52 |
| **BACKLOG-039** | Аудит NOT NULL полей | 🟡 | 📋 |
| **BACKLOG-044** | Защита `/metrics` (JWT/basic_auth) | 🟡 | 📋 production |
| **BACKLOG-045** | Параметризация портов экспортеров | 🟢 | 📋 |
| **BACKLOG-046** | Полный E2E-прогон на CI | 🔴 | 📋 52 |
| **BACKLOG-047** | `/api/health` версия — синхронизация | 🟡 | 📋 |
| **BACKLOG-065** | Удалить `findings_old` после проверки | 🟢 | 📋 |
| **BACKLOG-076** | Manager: возвращать `findings_updated` (не только новые) | 🟡 | 📋 v3.1.0 |
| **BACKLOG-077** | Сканер: heartbeat до инициализации классификаторов | 🟢 | 📋 v3.1.0 |
| **BACKLOG-078** | Linux-агент вне Docker (убрать из docker-compose) | 🟢 | 📋 v3.0.0 |
| **BACKLOG-079** | Опциональные targets в Prometheus | 🟢 | ✅ **исправлено** 23.09 |
| **BACKLOG-080** | Тестирование Windows-агента | 🟡 | 📋 v3.1.0 |
| **BACKLOG-081** | Тестирование Linux-агента | 🟡 | 📋 v3.1.0 |
| **BACKLOG-082** | Тестирование S3-агента + сканирование бакетов | 🟡 | 📋 v3.1.0 |
| **BACKLOG-083** | Alertmanager webhook → Manager не реализован | 🟡 | 📋 v3.0.0 |
| **BACKLOG-084** | Prometheus → Alertmanager не настроено | 🟢 | ✅ **исправлено** 23.09 |
| **BACKLOG-085** | **Полный OCR-пайплайн с bbox (tesseract tsv)** | 🟢 | 📋 v3.1.0 |
| **BACKLOG-087** | **Дедупликация встроенных фрагментов** | 🟢 | 📋 v3.1.0 |
| **BACKLOG-088** | **Шифрование `fragment_data` (AES-256-GCM)** | 🟡 | 📋 v3.1.0 |
| **BUG-076** | Сканер: `dcap_scanner_current_task` не сбрасывается | 🟢 | 📋 v3.1.0 |

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
| BACKLOG-086 | Встраивание OCR-фрагментов в БД | v3.13.19 |
| TASK-051 (BUG-080) | Heartbeat backoff | v3.13.20 |
| TASK-052 (BUG-081) | Graceful shutdown сканера | v3.13.20 |
| TASK-053 (BUG-086) | Masking контекстов | v3.13.21 |
| TASK-054…059 (BUG-087…093) | WebUI фильтры/пагинация/аудит/экспорт | v3.13.22 |
| TASK-060 (BUG-094) | Аудит reveal — ложное срабатывание | v3.13.23 |
| TASK-061…062 (BUG-095) | Аудит аутентификации и управления пользователями | v3.13.24 |
| TASK-064…066 (BUG-096/096b/097) | `/false-positives` 500, E2E, зависшие задания | v3.13.25 |
| TASK-067…071 (BUG-098…101, 101b) | PATCH/bulk/DELETE аудит, reset review, FP-пагинация, FP `file_path` | v3.13.26 |

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

## 🐛 БАГИ БЛОКА 3 (Scanner deep) — ЗАКРЫТЫ

### ✅ Закрытые

| ID | Название | Закрыт в |
|----|----------|----------|
| BUG-061 | Сканер не восстанавливает HTTP | v3.13.12 |
| BUG-062 | Избыточные логи | v3.13.12 |
| BUG-063 | `credit_card` не детектируется | v3.13.13 |
| BUG-065 | `database_url`/`github_token`/`slack_token`/`basic_auth` | v3.13.14 |
| BUG-066b | `scan_text` не фильтрует url-over-email | v3.13.14 |
| BUG-067c | OCR (`ocr_enabled`) | v3.13.13 |
| BUG-067d | OCR findings не помечаются `image_region`/`ocr` | v3.13.14 |
| BUG-069 | Ложные `date_time` из `en`-прохода | v3.13.14 |
| BUG-070 | Ложные `person`/`organization` из `en`-прохода | v3.13.14 + v3.13.15 |
| BUG-071 | url-over-email (спаны не пересекались) | v3.13.15 |
| BUG-072 | `organization = "INN"` | v3.13.15 |
| BUG-073 | `uk_nhs` на US-телефоне | v3.13.15 |
| BUG-074 | email из URL-логина | v3.13.15 |
| BUG-075 | url = домен email | v3.13.16 |
| BUG-077 | OCR bbox захардкожен {0,0,0,0} → None + fallback full-image | v3.13.17 + v3.13.18 |

### 🟢 TEST-NOTE

| ID | Название |
|----|----------|
| TEST-NOTE-3.1 | `text_extensions` в JSON игнорируется (fallback) |
| TEST-NOTE-3.2 | `byte_range` для `.bin` не реализован (v3.1.0) |
| TEST-NOTE-2.E2E | E2E-тест ротации (отложен) |

### 🟡 Перенесены в v3.1.0

| ID | Название |
|----|----------|
| BUG-060 | BOM ломает маскирование email |
| BUG-076 | Scanner: `current_task` не сбрасывается |
| BACKLOG-076 | Manager: `findings_updated` при дедупликации |
| BACKLOG-077 | Сканер: heartbeat до инициализации |

---

## 🐛 БАГИ БЛОКА 5 (WebUI) — 26-29.09.2026

### ✅ Закрытые в v3.13.22–26

| ID | Название | Закрыт в |
|----|----------|----------|
| BUG-087 | Прокси WebUI ронял заголовки ответа (`X-Total-Count`, `X-Fragment-*`, `Content-Disposition`) | v3.13.22 |
| BUG-088 | Fragment `<img>` без Bearer → 401 | v3.13.22 |
| BUG-089 | `/api/access/resources` 500 на PostgreSQL (`is_active == 1`) | v3.13.22 |
| BUG-090 | Фильтры findings: CSV-категории, пустые параметры, detector/fragment_type/search | v3.13.22 |
| BUG-091 | `/api/audit` игнорировал `event_source`; статические опции фильтров | v3.13.22 |
| BUG-093 | Экспорт findings из WebUI 401 (`window.location.href`) | v3.13.22 |
| BUG-094 | «BUG-087» аудит reveal: ложное срабатывание (CURRENT_USER vs "user") | v3.13.23 |
| BUG-095 | Аудит аутентификации (`auth_login`/`auth_failed`) не писался | v3.13.24 |
| BUG-096 | `/false-positives` 500 (`_m.User` → `User` из `auth.models`) | v3.13.25 |
| BUG-096b | Устаревшие E2E-тесты (finding_type/category, RemoteDisconnected) | v3.13.25 |
| BUG-097 | Зависшие задания + вечный 404 (SubmitStatus OK/RETRY/LOST) | v3.13.25 |
| BUG-098 | `/false-positives` → `file_path` = директория (должен быть файл) | v3.13.26 |
| BUG-099 | `/false-positives` → `offset=-1`/`limit=-5` → 500 (нет `_clamp_int`) | v3.13.26 |
| BUG-100 | PATCH `status=new` не очищает `reviewed_by`/`reviewed_at` | v3.13.26 |
| BUG-101 | PATCH + bulk не пишутся в `audit_logs` | v3.13.26 |
| BUG-101b | DELETE findings не писался в `audit_logs` | v3.13.26 |

### 🟢 Открытые (минорные)

| ID | Название | Приоритет |
|----|----------|-----------|
| BUG-083 | `order_by=severity` — лексикографический порядок (не семантический) | 🟢 v3.1.0 |
| BUG-085 | `/fragment` для text_line → 400 (нужно 404 + пояснение) | 🟢 v3.1.0 |

### 📋 TEST-NOTE Блока 5

| ID | Название |
|----|----------|
| TEST-NOTE-5.2 | ARCHITECTURE.md: имена полей API (`match_text` вместо `match_text_masked`, нет `fingerprint`, есть `value`/`has_fragment`/`has_encrypted`/`can_reveal`) |
| TEST-NOTE-5.3 | Export CSV содержит BOM в начале файла |
| TEST-NOTE-5.4 | `catalog_entries` пуста — каталог формируется динамически |
| TEST-NOTE-5.5 | Осиротевшие сканеры после обновления (связано с BUG-081) |
| TEST-NOTE-5.6 | `GET /api/findings` без `task_id` смешивает задачи |
| TEST-NOTE-5.7 | `event_type=finding_reveal` vs `metadata.action=finding_revealed` |
| TEST-NOTE-5.8 | Сканер на хосте не перезапускается автоматически после рестарта Docker/хоста |

---

## 🐛 БАГИ БЛОКА 8 (Мониторинг) — 23.09.2026

### ✅ Исправлено

| ID | Название | Статус |
|----|----------|--------|
| BACKLOG-084 | Prometheus → Alertmanager: секция `alerting` отсутствовала | ✅ fix 23.09 |
| BACKLOG-079 | Linux-агент target: убран из prometheus.yml | ✅ fix 23.09 |

### 🟡 В бэклог v3.0.0 / v3.1.0

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-078 | Linux-агент вне Docker | 🟢 v3.0.0 |
| BACKLOG-080 | Тестирование Windows-агента | 🟡 v3.1.0 |
| BACKLOG-081 | Тестирование Linux-агента | 🟡 v3.1.0 |
| BACKLOG-082 | Тестирование S3-агента + сканирование бакетов | 🟡 v3.1.0 |
| BACKLOG-083 | Alertmanager webhook → Manager не реализован | 🟡 v3.0.0 |
| BUG-076 | Scanner: `current_task` не сбрасывается | 🟢 v3.1.0 |

---

## 📋 v3.1.0 — RUST + DLP + SIEM + HARDENING + OPTIMIZATION

### План по дням

| День | Задача | BACKLOG/BUG | Приоритет |
|------|--------|-------------|-----------|
| 53-54 | Rust Scanner (только CIFS/NFS + параллелизм) | BACKLOG-036 | 🔴 |
| 55 | **Cython-оптимизация горячих точек** | **BACKLOG-089** | 🟡 |
| 56 | **Быстрые regex: `cre` / `re2`** | **BACKLOG-090** | 🟡 |
| 57 | ICAP Connector (DLP) | BACKLOG-032 | 🟡 |
| 58 | DLP Политики (WebUI) | BACKLOG-033 | 🟡 |
| 59 | SMB-сканер (Rust) | BACKLOG-035 | 🟡 |
| 60 | **SIEM: генерация событий (Syslog + JSON)** | **BACKLOG-069** | 🔴 |
| 61 | **SIEM: экспорт findings/audit** | **BACKLOG-070** | 🔴 |
| 62 | **SIEM: WebUI настройки** | **BACKLOG-072** | 🟡 |
| 63 | **Per-scanner keys** | **BACKLOG-068** | 🟡 |
| 64 | **Multi-key режим** (ротация без downtime) | — | 🟡 |
| 65 | **BOM fix + Scanner hardening** | **BUG-060, BUG-076** | 🟢 |
| 66 | **FP-пагинация + `order_by=severity`** | **BUG-083, BUG-085** | 🟢 |
| 67 | Обработка архивов | BACKLOG-017 | 🟡 |
| 68 | Распределённая архитектура | BACKLOG-018 | 🔴 |
| 69 | Расширенный мониторинг | BACKLOG-063/064 | 🟡 |
| 70 | Red teaming, SAST, SCA | BACKLOG-022 | 🔴 |
| 71 | Релиз v3.1.0 | — | 🔴 |

### Бэклог v3.1.0

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| BACKLOG-036 | **Rust Scanner — только для сетевых ФС (CIFS/NFS) и распараллеливания.** Классификаторы/PII остаются в Python | 🔴 | 📋 |
| **BACKLOG-089** | **Cython-оптимизация горячих точек сканера** (regex-фильтры, `mask_context`, entropy, prefilter) — 3–10× на функциях, 30–50% общего ускорения | 🟡 | 📋 |
| **BACKLOG-090** | **Быстрые regex: `cre` (PCRE + nogil) / `re2` (Google)** — замена `re` в горячих фильтрах, распараллеливание без Rust | 🟡 | 📋 |
| BACKLOG-032 | ICAP Connector (DLP) | 🟡 | 📋 |
| BACKLOG-033 | DLP Политики (WebUI) | 🟡 | 📋 |
| BACKLOG-035 | SMB-сканер | 🟡 | 📋 |
| BACKLOG-040 | Параллельный батч-сканер | 🟡 | 📋 |
| BACKLOG-048 | Rate-limit bypass для тестов | 🟡 | 📋 |
| BACKLOG-049 | Автоматизация chaos-теста scanner inactive | 🟡 | 📋 |
| BACKLOG-063 | Presidio: производительность | 🟡 | 📋 |
| BACKLOG-064 | Бенчмарк сканирования | 🟢 | 📋 |
| BACKLOG-068 | Per-scanner keys | 🟡 | 📋 |
| BACKLOG-069 | SIEM: генерация событий (Syslog + JSON) | 🔴 | 📋 |
| BACKLOG-070 | SIEM: экспорт findings/audit | 🔴 | 📋 |
| BACKLOG-072 | SIEM: WebUI настройки | 🟡 | 📋 |
| BACKLOG-076 | Manager: `findings_updated` | 🟡 | 📋 |
| BACKLOG-077 | Сканер: heartbeat до инициализации | 🟢 | 📋 |
| BACKLOG-080 | Тестирование Windows-агента | 🟡 | 📋 |
| BACKLOG-081 | Тестирование Linux-агента | 🟡 | 📋 |
| BACKLOG-082 | Тестирование S3-агента + сканирование бакетов | 🟡 | 📋 |
| BUG-060 | BOM ломает маскирование email | 🟢 | 📋 |
| BUG-076 | Scanner: `current_task` не сбрасывается | 🟢 | 📋 |
| BUG-083 | `order_by=severity` — семантический порядок | 🟢 | 📋 |
| BUG-085 | `/fragment` text_line → 404 + пояснение | 🟢 | 📋 |
| BACKLOG-011 | Webhook для MinIO | 🟢 | 📋 |
| BACKLOG-012 | Облачные хранилища | 🟢 | 📋 |
| BACKLOG-017 | Обработка архивов | 🟡 | 📋 |
| BACKLOG-018 | Распределённая архитектура | 🔴 | 📋 |
| BACKLOG-022 | Red teaming, SAST, SCA | 🔴 | 📋 |

---

## 💡 Идеи для будущих версий

| ID | Название | Версия |
|----|----------|--------|
| **BACKLOG-089** | **Cython-оптимизация** — перевод 5–7 горячих функций в `.pyx` (`mask_context`, `_filter_url_over_email_finding`, `_filter_spacy_noise`, `_filter_uk_nhs_with_phone`, entropy, prefilter) — 3–10× на функциях, 30–50% общего ускорения сканирования | 📋 v3.1.0 |
| **BACKLOG-090** | **Быстрые regex** — `cre` (PCRE + nogil, распараллеливание без Rust) / `re2` (ReDoS-устойчивость, линейное время) через Cython | 📋 v3.1.0 |
| BACKLOG-091 | TruffleHog — верификация credentials (валидность токенов через API провайдера) | 📋 v3.1.0+ |
| BACKLOG-092 | **Гибрид Cython + Rust**: Cython для горячих точек Python, Rust для сетевых ФС и параллелизма | 📋 v3.1.0+ |

### Находки Блока 7 (Retention) — из тестирования, день 50

| ID | Название | Статус | Приоритет |
|----|----------|--------|-----------|
| TEST-NOTE-7.1 | `findings_archive` — legacy-таблица (старая модель findings), отсутствует в ARCHITECTURE.md | 📋 док | 🟢 |
| TEST-NOTE-7.2 | `last_run` / `last_result` retention не сохраняются в БД — только в памяти процесса и в `data/retention_state.json`, который **не смонтирован** в контейнер воркера, поэтому результат выполнения retention через Celery нельзя проверить через `/api/retention/status`. Нужен общий том либо запись результата в БД | 📋 v3.1.0 | 🟡 |
| TEST-NOTE-7.3 | `findings.ttl_days=180` — удаляется без архивации (в отличие от `audit_events`) | 📋 v3.1.0 | 🟢 |
| TEST-NOTE-7.4 | `dry_run` через `POST /api/retention/run` работает даже без Celery (задача выполняется синхронно в процессе Manager) — поэтому этот путь **не способен поймать BUG-102**; учтено в `tests/e2e/test_retention_e2e.py` | ✅ учтено | — |
| TEST-NOTE-7.5 | Flower не видит worker'ов (`Inspect failed`) — не критично | 🟢 v3.1.0 | 🟢 |

---

## 📋 v4.0.0 — AI/ML + DISTRIBUTED

| День | Задача | Приоритет |
|------|--------|-----------|
| 72-73 | ML-классификаторы | 🔴 |
| 74 | Аномалии в аудите | 🟡 |
| 75-76 | Zero-Trust архитектура | 🔴 |
| 77 | Распределённый Manager | 🔴 |
| 78 | **SIEM: Kafka / Kinesis (streaming)** | 🟡 |
| 79 | Версионирование данных | 🟢 |
| 80 | Релиз v4.0.0 | 🔴 |

---

## 📊 Статистика

| Версия | Задач | Выполнено | Прогресс |
|--------|-------|-----------|----------|
| v1.0.0-v2.1.0 | 27 | 27 | 100% ✅ |
| **v3.0.0** | **~95** | **~88** | **~93% 🔄** |
| v3.1.0 | 31 | 0 | 0% 📋 |
| v4.0.0 | 9 | 0 | 0% 📋 |
| **ИТОГО** | **~162** | **~115** | **~71%** |

---

## 📝 Шаблон новой задачи

| BACKLOG-XXX / BUG-XXX / TASK-XXX | Название | 🔴/🟡/🟢 | 📋/🔄/✅/❌ |
|-----------------------------------|----------|----------|-------------|

**Приоритеты:** 🔴 критично / 🟡 важно / 🟢 nice-to-have
**Статусы:** 📋 запланировано / 🔄 в работе / ✅ выполнено / ❌ отменено

---

## 📚 Связанные документы

- **`STATE.md`** — текущее состояние проекта.
- **`STATE_TEST_SESSION.md`** — протокол тестирования.
- **`ARCHITECTURE.md`** — архитектура, модели, API, SIEM.
- **ТЗ (архив):** `TZ_FIX_SPRINT.md` … `TZ_FIX_BUG077.md`, `TZ_BACKLOG_086_EMBED_FRAGMENTS.md`, `TZ_BUG080_081_SCANNER_RELIABILITY.md`, `TZ_FIX_BUG086_MASK_CONTEXT.md`, `TZ_FIX_BUG095_AUTH_AUDIT.md`, `TZ_FIX_BUG096_097.md`, `TZ_FIX_SPRINT_BUG098-101.md`.
- **`SECURITY.md`**, **`docs/security_checklist.md`**, **`docs/admin-guide/05-security.md`**.

---

**Актуально на:** 30.09.2026
**Версия:** v3.13.27
**Следующая цель:** v3.0.0 (релиз) — осталось Блок 5 (п.7, 13, 14, 15), Блок 6 (Агенты), GitHub