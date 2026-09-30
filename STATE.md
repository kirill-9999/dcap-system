> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 30.09.2026
**Текущая версия:** v3.13.27
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блок 3 (Scanner deep) ✅; Блок 8 (Мониторинг) ✅; **Блок 7 (Retention) ✅** (BUG-102, v3.13.27 — retention и sweep_scheduled_scans работают); Блок 5 (WebUI): п.2.3–2.6, 3, 4, 5, 6, 8, 11 ✅; BUG-098…101/101b ✅; следующий шаг — Блок 5, п.7 (Stats)

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 50 (BUG-102) — Retention и sweep_scheduled_scans: фикс Mapper[Finding] в Celery |
| Статус дня | ✅ Выполнен |
| Последний принятый отчёт | `day_50_bug102_celery_mapper_report.md` (v3.13.27) |
| Следующий шаг | Блок 5 (WebUI) → п.7 (Stats) → п.13 (count) → п.14 (WebUI визуально) → п.15 (Регрессия) |
| Открытые вопросы к архитектору | 1) TEST-NOTE-7.2 — `last_run`/`last_result` retention живут только в памяти (файл `data/retention_state.json` не смонтирован в воркер), из-за этого результат выполнения retention в Celery нельзя проверить через API — нужен либо общий том, либо запись в БД; 2) TEST-NOTE-7.1 — `findings_archive` (legacy) отсутствует в ARCHITECTURE.md; 3) Cython (BACKLOG-089) и regex `cre`/`re2` (BACKLOG-090) — в бэклоге v3.1.0; 4) E2E на CI требует seed-данных (BACKLOG-046) |

---

## ✅ Выполненные дни (v3.0.0)

| День | Задача | Версия | Отчёт |
|------|--------|--------|-------|
| 28-40.4 | WebUI, AD, безопасность, Findings Refactor | до v3.12.0 | *(см. предыдущие STATE)* |
| 42.1-42.4 | Админ-руководство | — | ✅ |
| 43-44 | Блок 1 + AD-контейнер | v3.13.3-8 | `day_43_*`, `day_44_*` |
| 45 (тест) | Мастер-сессия Блок 2 (Auth/RBAC) | v3.13.8 | `STATE_TEST_SESSION.md` |
| 45 (fix1) | Fix-спринт №1: Auth/RBAC | **v3.13.9** | `day_45_fix_sprint_report.md` |
| 46 (fix2) | Fix-спринт №2: middleware BUG-048b | **v3.13.10** | — |
| 46 (fix3) | Fix-спринт №2: ENV-ключи Findings + ротация | **v3.13.11** | `day_46_fix_sprint_2_report.md` |
| 46 (fix3.5) | Fix-спринт №3: OCR, HTTP-retry, Luhn, dedup | **v3.13.12** | `day_46.5_fix_sprint_3_report.md` |
| 46.6-46.7 (fix4) | Fix-спринт №4: OCR-секция + Presidio ru+en | **v3.13.13** | `day_46.7_fix_sprint_4_report.md` |
| 46.8 (fix5) | Fix-спринт №5: url-over-email, OCR-markup, spaCy noise, credentials | **v3.13.14** | `day_46.8_fix_sprint_5_report.md` |
| 46.9 (fix6) | Fix-спринт №6: url-over-email (line_text), аббревиатуры, uk_nhs | **v3.13.15** | `day_46.9_fix_sprint_6_report.md` |
| 46.10 (fix7) | Fix-спринт №7: url = домен email (BUG-075) | **v3.13.16** | `day_46.10_fix_sprint_7_report.md` |
| 47 (test) | Мастер-сессия: Блок 3 (Scanner deep) — **ЗАКРЫТ** | — | ✅ |
| 47.2 (test) | Мастер-сессия: **Блок 8 (Мониторинг) — ЗАКРЫТ** | v3.13.16 | ✅ |
| 47.3 (bug077) | BUG-077: bounding_box=None для OCR + fallback full-image | **v3.13.17** | `day_47.3_fix_bug077_report.md` |
| 47.4 (bug077 diag) | BUG-077 diag: Manager дефолтил bbox | **v3.13.18** | `day_47.4_bug077_diag_report.md` |
| 47.5 (BACKLOG-086) | Встроенные OCR-фрагменты в БД | **v3.13.19** | `day_47.5_backlog086_embed_fragments_report.md` |
| 47.6 (BUG-080/081) | Reliability сканера: heartbeat backoff + graceful shutdown | **v3.13.20** | `day_47.6_backlog080_081_scanner_reliability_report.md` |
| 47.7 (BUG-086) | Masking контекстов | **v3.13.21** | `day_47.7_fix_bug086_mask_context_report.md` |
| 48 (Блок 5, п.2.3) | Фильтры/пагинация/аудит/экспорт WebUI | **v3.13.22** | `day_48_block5_webui_filters_report.md` |
| 48.1 (BUG-094) | «BUG-087» аудит reveal: ложное срабатывание | **v3.13.23** | `day_48.1_bug087_audit_user_report.md` |
| 48.2 (BUG-095) | Аудит аутентификации и управления пользователями | **v3.13.24** | `day_48.2_bug095_auth_audit_report.md` |
| 48.3 (BUG-096/096b/097) | `/false-positives` 500, устаревшие E2E, зависшие задания | **v3.13.25** | `day_48.3_bug096_097_report.md` |
| 49 (BUG-098…101, 101b) | PATCH/bulk/DELETE аудит, reset review, FP-пагинация, FP `file_path` | **v3.13.26** | `day_49_bug098_101_report.md` |
| 50 (BUG-102) | **Блок 7 (Retention) — Mapper[Finding] в Celery**: явный импорт `User` в воркер + fail-fast `configure_mappers()`; тот же дефект в `retention/{archiver,cleaner,exporter}` и `access_service`; тесты: 13 unit (регрессия в чистом подпроцессе) + 1 E2E (317 unit / 47 E2E); live: retention dry_run и Celery-путь без mapper-ошибки | **v3.13.27** | `day_50_bug102_celery_mapper_report.md` |

---

## 🔴 Открытые проблемы

### 🟢 Минорные (не блокеры v3.0.0)

| ID | Проблема | Статус | Приоритет |
|----|----------|--------|-----------|
| BUG-060 | BOM ломает маскирование email (`context_before`) | 📋 v3.1.0 | 🟢 |
| BUG-061 | Сканер не восстанавливает HTTP после падения Manager | 📋 v3.1.0 | 🟡 |
| BUG-076 | Сканер: `dcap_scanner_current_task` не сбрасывается после задачи | 📋 v3.1.0 | 🟢 |
| BACKLOG-076 | Manager: не обновляет `last_seen_at`, возвращает заниженный `findings_count` | 📋 v3.1.0 | 🟡 |
| BACKLOG-077 | Сканер: heartbeat стартует после инициализации классификаторов (~35-60 с inactive) | 📋 v3.1.0 | 🟢 |

### 🟡 Средние (перенесены)

| ID | Проблема | Статус | Приоритет |
|----|----------|--------|-----------|
| BUG-083 | `order_by=severity` — лексикографический порядок | 📋 v3.1.0 | 🟢 |
| BUG-085 | `/fragment` для text_line → 400 (нужно 404 + пояснение) | 📋 v3.1.0 | 🟢 |
| BACKLOG-039 | Аудит NOT NULL полей | 📋 | 🟡 |
| BACKLOG-044 | Защита `/metrics` | 📋 production | 🟡 |
| BACKLOG-045 | Параметризация портов | 📋 | 🟢 |
| BACKLOG-063 | Presidio производительность | 📋 v3.1.0 | 🟡 |
| BACKLOG-064 | Бенчмарк сканирования | 📋 v3.1.0 | 🟢 |
| BACKLOG-065 | Удалить `findings_old` | 📋 v3.0.0 | 🟢 |
| BACKLOG-068 | Per-scanner keys | 📋 v3.1.0 | 🟡 |
| **BACKLOG-078** | **Linux-агент вне Docker** | 📋 v3.0.0 | 🟢 |
| **BACKLOG-079** | **Опциональные targets в Prometheus** | ✅ **исправлено** 23.09 | 🟢 |
| **BACKLOG-080** | **Тестирование Windows-агента** | 📋 v3.1.0 | 🟡 |
| **BACKLOG-081** | **Тестирование Linux-агента** | 📋 v3.1.0 | 🟡 |
| **BACKLOG-082** | **Тестирование S3-агента + сканирование бакетов** | 📋 v3.1.0 | 🟡 |
| **BACKLOG-083** | **Alertmanager webhook → Manager не реализован** | 📋 v3.0.0 | 🟡 |
| **BACKLOG-084** | **Prometheus → Alertmanager не настроено** | ✅ **исправлено** 23.09 | 🟢 |
| **BACKLOG-085** | **Полный OCR-пайплайн с bbox (tesseract tsv)** | 📋 v3.1.0 | 🟢 |
| **BACKLOG-087** | **Дедупликация встроенных фрагментов** | 📋 v3.1.0 | 🟢 |
| **BACKLOG-088** | **Шифрование `fragment_data` (AES-256-GCM)** | 📋 v3.1.0 | 🟡 |
| **BACKLOG-089** | **Cython-оптимизация горячих точек** | 📋 v3.1.0 | 🟡 |
| **BACKLOG-090** | **Быстрые regex: `cre` / `re2`** | 📋 v3.1.0 | 🟡 |
| **BACKLOG-091** | **TruffleHog — верификация credentials** | 📋 v3.1.0+ | 🟡 |

*(Закрытые в v3.13.9: BUG-037…059)*
*(Закрытые в v3.13.10: BUG-048b)*
*(Закрытые в v3.13.11: TASK-016, TASK-018, TASK-020)*
*(Закрытые в v3.13.12–16: BUG-061, 063, 065, 066b, 067c/d, 069–075)*
*(Закрытые в v3.13.17–18: BUG-077, TASK-041…044)*
*(Закрытые в v3.13.19: BACKLOG-086, BUG-079)*
*(Закрытые в v3.13.20: BUG-080, BUG-081)*
*(Закрытые в v3.13.21: BUG-086)*
*(Закрытые в v3.13.22: BUG-087, 088, 089, 090, 091, 093)*
*(Закрытые в v3.13.23: BUG-094)*
*(Закрытые в v3.13.24: BUG-095)*
*(Закрытые в v3.13.25: BUG-096, 096b, 097)*
*(Закрытые в v3.13.26: BUG-098, 099, 100, 101, 101b)*
*(Закрытые в v3.13.27: BUG-102 — Retention и `sweep_scheduled_scans` падали на `Mapper[Finding]` ... `'User'`; импорт `User` в воркер + fail-fast `configure_mappers()`; Блок 7 закрыт)*
*(Открытые TEST-NOTE Блока 7: TEST-NOTE-7.1 `findings_archive` — legacy-таблица, нет в ARCHITECTURE.md 📋 док; TEST-NOTE-7.2 `last_run`/`last_result` retention только в памяти (файл не смонтирован в воркер) 📋 v3.1.0; TEST-NOTE-7.3 `findings.ttl_days=180` без архивации 📋 v3.1.0; TEST-NOTE-7.5 Flower не видит worker'ов 🟢 v3.1.0; TEST-NOTE-7.4 dry_run через API работает без Celery ✅ — учтено в E2E)*

---

## 🎯 Ключевые решения

**Findings Refactor (v3.9.0-v3.13.26):**
- Findings = строка/фрагмент, гибрид masked + AES-256-GCM
- HMAC-SHA256 fingerprint
- Ключи Findings — только через ENV (Docker Secrets убраны, TASK-018)
- Scanner fail-fast без ключей
- Ротация с downtime (перешифровка `reencrypt_findings.py`)
- Единый ключ для v3.0.0, per-scanner — v3.1.0 (BACKLOG-068)
- **Дедупликация Manager — глобальная по fingerprint** (BACKLOG-076)
- **Аудит PATCH/bulk/DELETE findings (BUG-101, 101b, v3.13.26):** `_log_finding_status_change` с маппингом `confirmed`/`false_positive`/`archived`/`new` → `finding_confirmed`/`finding_false_positive`/`finding_archived`/`finding_reset`; `DELETE` → `finding_deleted`; `via=patch|bulk|delete` в metadata; запись через один commit на batch
- **Сброс review-полей при `new` (BUG-100, v3.13.26):** `_apply_status` — единая функция для PATCH и bulk; при `new` очищаются `reviewed_by`/`reviewed_at`

**Аутентификация (Блок 2):**
- `verify_token(token, expected_type)` — access ≠ refresh
- RBAC системно — `Depends(require_role(...))` во все write-эндпоинты
- Middleware извлекает JWT для machine-API (BUG-048b)
- Cookie `Secure` — env `AUTH_COOKIE_SECURE`
- `jti` + `iat` + Redis blacklist
- **Аудит аутентификации (BUG-095, v3.13.24):** 9 event_type — `auth_login`, `auth_failed` (`reason: invalid_credentials`/`user_inactive`/`user_not_found`), `auth_logout`, `user_created`, `user_updated`, `user_deleted`, `user_password_changed` (`by_admin`/`self_service`), `role_assigned`, `role_revoked`; fail-open; `_sanitize` вырезает password/token/secret/hash/salt; `auth_refresh` НЕ логируется

**Scanner (Блок 3):**
- Scanner — на хосте, не в Docker
- Heartbeat-thread (30 с), fail-open
- spaCy `sm` (ru + en, двухпроходный Presidio)
- OCR: Tesseract (rus+eng), изолированный OCRWorker
- **OCR bbox до v3.1.0 = None** (BACKLOG-085)
- **Встроенные фрагменты (BACKLOG-086, v3.13.19):** OCR-PNG (≤2 МБ) base64+SHA-256 → `fragment_data` в БД; `/fragment` — embedded-first (`X-Fragment-Mode: embedded`); RBAC `/fragment` — Auditor+ (BUG-079); батчинг (MAX_BATCH_SIZE_BYTES=20 МБ)
- Фильтры PII: `_filter_url_over_email_finding`, `_filter_spacy_noise`, `_filter_uk_nhs_with_phone`
- Luhn-валидация для `credit_card`
- **Reliability (BUG-080/081, v3.13.20):** heartbeat backoff 5→10→30→60→120 с; graceful shutdown SIGINT/SIGBREAK → OCRWorker завершается штатно
- **Masking контекстов (BUG-086, v3.13.21):** `mask_context` — конвейер `_CONTEXT_PATTERNS` (21 паттерн); специфичные токены раньше generic; generic KEY=VALUE маскирует ТОЛЬКО значение (2 capture-группы); `person`/`high_entropy` не маскируются
- **Offline-буфер (BUG-097, v3.13.25):** `SubmitStatus` (OK/RETRY/LOST); 404/410 → LOST (пачка отбрасывается); `_fail_task_safely` — задание сразу в `failed`

**WebUI (Блок 5):**
- WebUI не ходит в БД — всё через прокси `webui/api/routes.py` на Manager; JWT в localStorage, `Authorization: Bearer`
- **Прокси пробрасывает заголовки ответа** (`forwarded_headers`): `X-Total-Count`, `X-Fragment-*`, `Content-Disposition`; hop-by-hop и `set-cookie` отбрасываются — BUG-087
- **Бинарные/приватные данные — `fetch()` + `Blob` + Bearer**, не `<img src>`/`window.location` — BUG-088, BUG-093
- **Фильтры findings:** CSV-категории, legacy (pii/credentials/code) → `finding_type`, остальные → `category`, OR; `detector`, `fragment_type`, `search`, `order_by=id`; пустые числовые → «без фильтра» — BUG-090
- **FastAPI 0.137 gotcha:** `BeforeValidator` в `Annotated` теряется при `Query()` в default; числовые `le`/`ge` несовместимы с `Optional[int]` → `_clamp_int()`
- **Фильтры аудита** — data-driven из `/api/audit/stats`; серверный `event_source` — BUG-091
- `/api/access/*`: `is_active == True` (было `== 1` → 500 на PostgreSQL) — BUG-089
- **FP-эндпоинт (v3.13.25–26):** `/false-positives` — `_m.User` → `User` из `auth.models` (BUG-096); `_clamp_int` для `limit`/`offset` (BUG-099); `file_path` = `fragment_path` (BUG-098)
- **PATCH/bulk (v3.13.26):** аудит статус-изменений (BUG-101); сброс review-полей при `new` (BUG-100)
- **Тесты:** `tests/unit/test_webui_block5_v31322.py` (33), `test_audit_reveal_user_v31323.py` (7), `test_auth_audit_v31324.py` (15), `test_false_positives_v31325.py` (8), `test_bug097_offline_flush.py` (14), `test_audit_status_change_v31326.py` (18), `test_patch_reset_clears_review_v31326.py` (8), `test_fp_pagination_v31326.py` (8), `test_fp_file_path_v31326.py` (6) — итого **301 unit**

**Мониторинг (Блок 8):**
- Prometheus + Grafana + Alertmanager — работают
- Prometheus targets: manager, scanner, s3-agent, celery, postgres, redis (6/6 up)
- `rule_files` = alerts.yml (4 правила)
- `alerting.alertmanagers` = alertmanager:9093 (BACKLOG-084 fix)
- Alertmanager: webhook_configs → manager:8000/api/alerts/webhook (BACKLOG-083 — не реализован)
- Grafana: 2 dashboards (`dcap-overview`, `dcap-scanner`)
- Агенты (Windows/Linux) — **вне Docker**, targets опциональны (BACKLOG-078, 079)
- **Операционный нюанс (TEST-NOTE-5.8):** сканер на хосте не перезапускается автоматически после рестарта Docker Desktop

**Оптимизация (v3.1.0+):**
- **Cython (BACKLOG-089):** перевод 5–7 горячих функций в `.pyx` — regex-фильтры, `mask_context`, entropy, prefilter; 3–10× на функциях, 30–50% общего ускорения
- **Быстрые regex (BACKLOG-090):** `cre` (PCRE + nogil, распараллеливание без Rust) / `re2` (ReDoS-устойчивость, линейное время)
- **Гибрид (BACKLOG-092):** Cython для горячих точек Python, Rust — для сетевых ФС (CIFS/NFS) и параллелизма
- **TruffleHog (BACKLOG-091):** верификация credentials через API провайдера

---

## 📁 Последние использованные файлы

- `manager/src/api/findings.py` — BUG-098…101: хелпер `_log_finding_status_change()`, `_STATUS_EVENT_MAP`, `_apply_status()`; вызовы в PATCH/bulk/DELETE; `request: Request` в трёх эндпоинтах; `OptInt` + `_clamp_int` в `list_false_positives`; `file_path` = `fragment_path`
- `tests/unit/test_audit_status_change_v31326.py` (18), `test_patch_reset_clears_review_v31326.py` (8), `test_fp_pagination_v31326.py` (8), `test_fp_file_path_v31326.py` (6) — 301 unit passed
- `tests/unit/test_false_positives_v31325.py` — ассерт `file_path` обновлён (баговое поведение → корректное)
- `.env`, `.env.example`, `docker-compose.yml` — VERSION → 3.13.26
- `CHANGELOG.md`, `STATE.md`, `ROADMAP.md` — BUG-098…101, 101b → ✅
- `ARCHITECTURE.md` — таблица событий аудита findings (см. обновление ниже)
- `manager/src/workers/tasks.py` — BUG-102: `from manager.src.auth.models import User` до первого обращения к `Finding`/`AuditLog`
- `manager/src/workers/celery_app.py` — BUG-102: fail-fast `configure_mappers()` после импорта обеих групп моделей (страховка; сам модуль уже подтягивал `User` транзитивно)
- `manager/src/retention/{archiver,cleaner,exporter}.py`, `manager/src/services/access_service.py` — BUG-102: тот же дефект, найденный «заодно» по п. «Проверить заодно»
- `tests/unit/test_celery_mapper_v31327.py` (13) — регрессия в чистом подпроцессе; на коде без фикса падают 12 из 13
- `tests/e2e/test_retention_e2e.py` (1) — live: 5 шагов без error + очередь Celery; 317 unit / 47 E2E

---

**Актуально на:** 30.09.2026
**Версия:** v3.13.27
**Следующий шаг:** Блок 5 (WebUI) — п.7 (Stats) → п.13 (count) → п.14 (WebUI визуально) → п.15 (Регрессия)