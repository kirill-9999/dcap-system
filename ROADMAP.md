# 🗺️ ROADMAP.md — План развития и бэклог DCAP

> **Обновляется архитектором.** План — редко, бэклог — по мере.
> Текущее состояние — в `STATE.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 01.10.2026
**Стратегия:** Windows First → Linux → S3/MinIO → Enterprise Ready → Rust + DLP + SIEM

---

## 🚀 Вехи

| Версия | Статус | Ключевые фичи |
|--------|--------|---------------|
| v1.0.0-v2.1.0 | ✅ | Обнаружение, классификация, WebUI, Linux-агент |
| **v3.0.0** | **🔄 Финальный этап** | **Enterprise Ready: S3, AD, mTLS, архивация, Findings Refactor, ENV-ключи, RBAC, админ-руководство, GitHub** |
| v3.1.0 | 📋 | Rust Scanner (CIFS/NFS), DLP/ICAP, SMB, Webhook, облака, Auth Hardening, Per-scanner keys, BOM fix, SIEM, Cython, TruffleHog |
| v4.0.0 | 📋 | ML-классификаторы, Zero-Trust, распределённый Manager, Kafka/Kinesis SIEM |

---

## 📋 v3.0.0 — ENTERPRISE READY (🔄 ФИНАЛЬНЫЙ ЭТАП)

### План по дням

| День | Задача | BACKLOG/BUG | Статус |
|------|--------|-------------|--------|
| 28-47.7 | (WebUI, AD, Findings Refactor, Scanner deep, Мониторинг, Masking) | см. STATE | ✅ до v3.13.21 |
| 48 (Блок 5, п.2.3) | Фильтры/пагинация/аудит/экспорт WebUI | TASK-054…059 | ✅ **v3.13.22** |
| 48.1 (BUG-094) | «BUG-087» аудит reveal — ложное срабатывание | TASK-060 | ✅ **v3.13.23** |
| 48.2 (BUG-095) | Аудит аутентификации | TASK-061…062 | ✅ **v3.13.24** |
| 48.3 (BUG-096/096b/097) | FP 500, E2E, зависшие задания | TASK-064…066 | ✅ **v3.13.25** |
| 49 (BUG-098…101, 101b) | PATCH/bulk/DELETE аудит, review, FP | TASK-067…071 | ✅ **v3.13.26** |
| 50 (BUG-102) | Retention + sweep падали на Mapper[Finding] | TASK-072…073 | ✅ **v3.13.27** |
| 50.1 (Блок 7) | Retention deep — политики, dry_run, Celery, архивы | — | ✅ **ЗАКРЫТ** |
| 50.2 (Блок 5 регрессия) | E2E: 47 passed, 6 skipped, 0 failed | — | ✅ |
| **51** | **Блок 9 (Безопасность)** | — | 📋 **следующий** |
| 52 | Блок 6 (Агенты) | BACKLOG-080…082 | 📋 |
| 53 | Блок 11 (Отказоустойчивость) | — | 📋 |
| 54 | GitHub-пакет | BACKLOG-028/046 | 📋 |
| 55 | Релиз v3.0.0 | — | 📋 |

### Бэклог v3.0.0 — активные задачи

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| **BACKLOG-028** | Публикация на GitHub | 🔴 | 📋 54 |
| **BACKLOG-046** | Полный E2E-прогон на CI (seed + изоляция сканера) | 🔴 | 📋 54 |
| **BACKLOG-094** | WebUI/Manager не пересобирается автоматически при `up -d` | 🟡 | 📋 |
| **BACKLOG-039** | Аудит NOT NULL полей | 🟡 | 📋 |
| **BACKLOG-044** | Защита `/metrics` | 🟡 | 📋 production |
| **BACKLOG-045** | Параметризация портов экспортеров | 🟢 | 📋 |
| **BACKLOG-047** | `/api/health` версия — синхронизация | 🟡 | 📋 |
| **BACKLOG-065** | Удалить `findings_old` + `findings_archive` | 🟢 | 📋 |
| **BACKLOG-078** | Linux-агент вне Docker | 🟢 | 📋 |
| **BACKLOG-083** | Alertmanager webhook → Manager | 🟡 | 📋 |
| **TEST-NOTE-5.5** | Осиротевшие сканеры после обновления | 🟡 | 📋 |
| **TEST-NOTE-5.11** | E2E `_assign_task` конкурирует со сканером | 🟡 | 📋 |
| **TEST-NOTE-5.12** | `--remove-orphans` сносит основной стек | 🟡 | 📋 |

### Бэклог v3.0.0 — ЗАКРЫТЫЕ (история, кратко)

| ID | Название | Закрыт в |
|----|----------|----------|
| BACKLOG-010…067 | (см. предыдущие ROADMAP) | v3.0.0 (день 28-40) |
| BACKLOG-086 | Встраивание OCR-фрагментов | v3.13.19 |
| TASK-051/052 (BUG-080/081) | Heartbeat backoff + graceful shutdown | v3.13.20 |
| TASK-053 (BUG-086) | Masking контекстов | v3.13.21 |
| TASK-054…059 (BUG-087…093) | WebUI фильтры/пагинация/аудит/экспорт | v3.13.22 |
| TASK-060 (BUG-094) | Аудит reveal — ложное | v3.13.23 |
| TASK-061/062 (BUG-095) | Аудит аутентификации | v3.13.24 |
| TASK-064…066 (BUG-096/096b/097) | FP 500, E2E, зависшие задания | v3.13.25 |
| TASK-067…071 (BUG-098…101, 101b) | PATCH/bulk/DELETE аудит, review, FP | v3.13.26 |
| TASK-072/073 (BUG-102) | Retention + sweep (Celery mapper) | v3.13.27 |
| **BACKLOG-095** | Fallback `${VERSION:-3.13.12}` → 3.13.27 (6 мест) | v3.13.27 |

---

## 🐛 БАГИ БЛОКА 2 (Auth/RBAC) — ЗАКРЫТЫ

| ID | Название | Закрыт в |
|----|----------|----------|
| BUG-037…059 | (15 багов) | v3.13.9 |
| BUG-048b | Middleware machine-API | v3.13.10 |

---

## 🐛 БАГИ БЛОКА 3 (Scanner deep) — ЗАКРЫТЫ

| ID | Название | Закрыт в |
|----|----------|----------|
| BUG-061, 062, 063, 065, 066b, 067c/d, 069, 070, 071, 072, 073, 074, 075 | (13 багов) | v3.13.12–16 |
| BUG-077 | OCR bbox {0,0,0,0} → None + full-image | v3.13.17–18 |

### 🟢 TEST-NOTE Блока 3

| ID | Название |
|----|----------|
| TEST-NOTE-3.1 | `text_extensions` в JSON игнорируется |
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

## 🐛 БАГИ БЛОКА 5 (WebUI) — 26–29.09.2026

### ✅ Закрытые в v3.13.22–26

| ID | Название | Закрыт в |
|----|----------|----------|
| BUG-087 | Прокси WebUI терял заголовки ответа | v3.13.22 |
| BUG-088 | Fragment `<img>` без Bearer → 401 | v3.13.22 |
| BUG-089 | `/api/access/resources` 500 | v3.13.22 |
| BUG-090 | CSV-категории, пустые параметры, detector/fragment_type/search | v3.13.22 |
| BUG-091 | `/api/audit` игнорировал `event_source` | v3.13.22 |
| BUG-093 | Экспорт findings 401 | v3.13.22 |
| BUG-094 | «BUG-087» аудит reveal — ложное | v3.13.23 |
| BUG-095 | Аудит аутентификации | v3.13.24 |
| BUG-096 | `/false-positives` 500 (`_m.User`) | v3.13.25 |
| BUG-096b | Устаревшие E2E | v3.13.25 |
| BUG-097 | Зависшие задания + вечный 404 | v3.13.25 |
| BUG-098 | FP: `file_path` = директория | v3.13.26 |
| BUG-099 | FP: `limit/offset` → 500 | v3.13.26 |
| BUG-100 | PATCH `new` не очищал review-поля | v3.13.26 |
| BUG-101 | PATCH + bulk не писались в audit_logs | v3.13.26 |
| BUG-101b | DELETE не писался в audit_logs | v3.13.26 |

### 🟢 Открытые (v3.1.0)

| ID | Название | Приоритет |
|----|----------|-----------|
| BUG-083 | `order_by=severity` — лексикографический | 🟢 v3.1.0 |
| BUG-085 | `/fragment` для text_line → 400 | 🟢 v3.1.0 |

---

## 🐛 БАГИ БЛОКА 7 (Retention) — 30.09.2026

### ✅ Закрытые

| ID | Название | Закрыт в |
|----|----------|----------|
| **BUG-102** | Retention + `sweep_scheduled_scans` падали на `Mapper[Finding] ... 'User'` | v3.13.27 |

---

## 🐛 БАГИ БЛОКА 8 (Мониторинг) — 23.09.2026

| ID | Название | Статус |
|----|----------|--------|
| BACKLOG-079 | Linux-агент target | ✅ fix 23.09 |
| BACKLOG-084 | Prometheus → Alertmanager | ✅ fix 23.09 |
| BACKLOG-078 | Linux-агент вне Docker | 📋 v3.0.0 |
| BACKLOG-080…082 | Тестирование агентов | 📋 v3.1.0 |
| BACKLOG-083 | Alertmanager webhook → Manager | 📋 v3.0.0 |
| BUG-076 | Scanner: `current_task` | 📋 v3.1.0 |

---

## 📋 v3.1.0 — RUST + DLP + SIEM + OPTIMIZATION

### План по дням

| День | Задача | ID | Приоритет |
|------|--------|-----|-----------|
| 56-57 | Rust Scanner (CIFS/NFS + параллелизм) | BACKLOG-036 | 🔴 |
| 58 | Cython-оптимизация горячих точек | BACKLOG-089 | 🟡 |
| 59 | Быстрые regex: `cre` / `re2` | BACKLOG-090 | 🟡 |
| 60 | ICAP Connector (DLP) | BACKLOG-032 | 🟡 |
| 61 | DLP Политики (WebUI) | BACKLOG-033 | 🟡 |
| 62 | SMB-сканер (Rust) | BACKLOG-035 | 🟡 |
| 63 | SIEM: генерация событий (Syslog + JSON) | BACKLOG-069 | 🔴 |
| 64 | SIEM: экспорт findings/audit | BACKLOG-070 | 🔴 |
| 65 | SIEM: WebUI настройки | BACKLOG-072 | 🟡 |
| 66 | Per-scanner keys | BACKLOG-068 | 🟡 |
| 67 | Multi-key режим (ротация без downtime) | — | 🟡 |
| 68 | BOM fix + Scanner hardening | BUG-060, 076 | 🟢 |
| 69 | FP-пагинация + `order_by=severity` + `/fragment` text_line | BUG-083, 085 | 🟢 |
| 70 | Обработка архивов | BACKLOG-017 | 🟡 |
| 71 | Распределённая архитектура | BACKLOG-018 | 🔴 |
| 72 | Расширенный мониторинг | BACKLOG-063/064 | 🟡 |
| 73 | Red teaming, SAST, SCA | BACKLOG-022 | 🔴 |
| 74 | Релиз v3.1.0 | — | 🔴 |

### Бэклог v3.1.0

| ID | Название | Приоритет |
|----|----------|-----------|
| BACKLOG-036 | Rust Scanner — **только CIFS/NFS + параллелизм**; классификаторы/PII — Python | 🔴 |
| BACKLOG-089 | Cython-оптимизация горячих точек сканера | 🟡 |
| BACKLOG-090 | Быстрые regex: `cre` / `re2` (Cython) | 🟡 |
| BACKLOG-091 | TruffleHog — верификация credentials | 🟡 |
| BACKLOG-092 | Гибрид Cython + Rust | 🟡 |
| BACKLOG-093 | Редизайн WebUI (визуал) | 🟢 |
| BACKLOG-096 | `run_scanner.py` — `start_metrics_server` | 🟢 |
| BACKLOG-032 | ICAP Connector (DLP) | 🟡 |
| BACKLOG-033 | DLP Политики (WebUI) | 🟡 |
| BACKLOG-035 | SMB-сканер | 🟡 |
| BACKLOG-040 | Параллельный батч-сканер | 🟡 |
| BACKLOG-048 | Rate-limit bypass для тестов | 🟡 |
| BACKLOG-049 | Автоматизация chaos-теста scanner inactive | 🟡 |
| BACKLOG-063 | Presidio: производительность | 🟡 |
| BACKLOG-064 | Бенчмарк сканирования | 🟢 |
| BACKLOG-068 | Per-scanner keys | 🟡 |
| BACKLOG-069 | SIEM: генерация событий (Syslog + JSON) | 🔴 |
| BACKLOG-070 | SIEM: экспорт findings/audit | 🔴 |
| BACKLOG-072 | SIEM: WebUI настройки | 🟡 |
| BACKLOG-076 | Manager: `findings_updated` | 🟡 |
| BACKLOG-077 | Сканер: heartbeat до инициализации | 🟢 |
| BACKLOG-080…082 | Тестирование агентов (Windows/Linux/S3) | 🟡 |
| BUG-060 | BOM ломает маскирование email | 🟢 |
| BUG-076 | Scanner: `current_task` не сбрасывается | 🟢 |
| BUG-083 | `order_by=severity` — семантический порядок | 🟢 |
| BUG-085 | `/fragment` text_line → 404 + пояснение | 🟢 |
| BACKLOG-011 | Webhook для MinIO | 🟢 |
| BACKLOG-012 | Облачные хранилища | 🟢 |
| BACKLOG-017 | Обработка архивов | 🟡 |
| BACKLOG-018 | Распределённая архитектура | 🔴 |
| BACKLOG-022 | Red teaming, SAST, SCA | 🔴 |

---

## 📋 TEST-NOTE (не баги, требуют внимания)

### TEST-NOTE — Блок 3

| ID | Название | Приоритет |
|----|----------|-----------|
| TEST-NOTE-3.1 | `text_extensions` в JSON игнорируется | 📋 док |
| TEST-NOTE-3.2 | `byte_range` для `.bin` не реализован | 🟢 v3.1.0 |
| TEST-NOTE-2.E2E | E2E-тест ротации (отложен) | 🟢 v3.1.0 |

### TEST-NOTE — Блок 5

| ID | Название | Приоритет |
|----|----------|-----------|
| TEST-NOTE-5.2 | ARCHITECTURE.md: имена полей API | 📋 док |
| TEST-NOTE-5.3 | Export CSV содержит BOM | 🟢 v3.1.0 |
| TEST-NOTE-5.4 | `catalog_entries` пуста (динамический каталог) | 📋 док |
| TEST-NOTE-5.5 | Осиротевшие сканеры после обновления | 🟡 v3.0.0 |
| TEST-NOTE-5.6 | `GET /api/findings` без `task_id` смешивает задачи | 📋 док |
| TEST-NOTE-5.7 | `event_type=finding_reveal` vs `metadata.action=finding_revealed` | 📋 v3.1.0 |
| TEST-NOTE-5.8 | Сканер не перезапускается автоматически | 📋 v3.1.0 |
| TEST-NOTE-5.9 | `by_detector` отсутствует в `/stats` | 🟢 v3.1.0 |
| TEST-NOTE-5.10 | Глобальная статистика включает устаревшие findings | 📋 док |
| TEST-NOTE-5.11 | E2E `_assign_task` конкурирует со сканером | 🟡 v3.0.0 |
| TEST-NOTE-5.12 | `--remove-orphans` сносит основной стек | 🟡 v3.0.0 |
| TEST-NOTE-5.13 | Stale-сканеры в БД | 🟢 v3.1.0 |

### TEST-NOTE — Блок 7

| ID | Название | Приоритет |
|----|----------|-----------|
| TEST-NOTE-7.1 | `findings_archive` — legacy-таблица | 📋 док |
| TEST-NOTE-7.2 | `retention.state` — в файле воркера, Manager не видит | 📋 v3.1.0 |
| TEST-NOTE-7.3 | `findings.ttl_days=180` — без архивации | 📋 v3.1.0 |
| TEST-NOTE-7.4 | `run` (sync) ≠ `start` (Celery) | 📋 док |
| TEST-NOTE-7.5 | Flower не видит worker'ов | 🟢 v3.1.0 |

---

## 📋 v4.0.0 — AI/ML + DISTRIBUTED

| День | Задача | Приоритет |
|------|--------|-----------|
| 75-76 | ML-классификаторы | 🔴 |
| 77 | Аномалии в аудите | 🟡 |
| 78-79 | Zero-Trust архитектура | 🔴 |
| 80 | Распределённый Manager | 🔴 |
| 81 | SIEM: Kafka / Kinesis | 🟡 |
| 82 | Версионирование данных | 🟢 |
| 83 | Релиз v4.0.0 | 🔴 |

---

## 📊 Статистика

| Версия | Задач | Выполнено | Прогресс |
|--------|-------|-----------|----------|
| v1.0.0-v2.1.0 | 27 | 27 | 100% ✅ |
| **v3.0.0** | **~100** | **~93** | **~93% 🔄** |
| v3.1.0 | 35 | 0 | 0% 📋 |
| v4.0.0 | 9 | 0 | 0% 📋 |
| **ИТОГО** | **~171** | **~120** | **~70%** |

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
- **ТЗ (архив):** `TZ_FIX_SPRINT.md` … `TZ_FIX_BUG102_CELERY_MAPPER.md`.
- **`SECURITY.md`**, **`docs/security_checklist.md`**, **`docs/admin-guide/05-security.md`**.

---

**Актуально на:** 01.10.2026
**Версия:** v3.13.27
**Следующая цель:** v3.0.0 (релиз) — осталось Блок 9 (Безопасность), Блок 6 (Агенты), Блок 11 (Отказоустойчивость), GitHub