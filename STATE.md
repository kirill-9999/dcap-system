> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 26.09.2026
**Текущая версия:** v3.13.21
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блок 3 (Scanner deep) ✅; Блок 8 (Мониторинг) ✅; BACKLOG-086 (встроенные фрагменты) ✅; BUG-080/081 (reliability сканера) ✅; BUG-086 (masking контекстов) ✅; следующий шаг — Блок 5 (WebUI)

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 47.7 — BUG-086 (v3.13.21): mask_context конвейером _CONTEXT_PATTERNS |
| Статус дня | ✅ Выполнен |
| Последний принятый отчёт | `day_47.7_fix_bug086_mask_context_report.md` (v3.13.21) |
| Следующий шаг | Блок 5 (WebUI) — продолжить с п.2.3 (фильтры) |
| Открытые вопросы к архитектору | — |

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
| 47.3 (bug077) | BUG-077: bounding_box=None для OCR + fallback full-image в /fragment; VERSION агентов синхронизирован (TASK-041..043) | **v3.13.17** | `day_47.3_fix_bug077_report.md` |
| 47.4 (bug077 diag) | BUG-077 diag: причина H3 (Manager дефолтил bbox при сохранении) — TASK-044; live task 38: bbox=NULL | **v3.13.18** | `day_47.4_bug077_diag_report.md` |
| 47.5 (BACKLOG-086) | Встроенные OCR-фрагменты: фрагмент в БД (TASK-045-049), /fragment RBAC Auditor+, батчинг по размеру (TASK-050), live task 39: «после удаления исходника — 200 embedded» | **v3.13.19** | `day_47.5_backlog086_embed_fragments_report.md` |
| 47.6 (BUG-080/081) | Reliability сканера: heartbeat backoff 5→10→30→60→120 с без спама лога (TASK-051); graceful shutdown по SIGINT/SIGBREAK — OCRWorker завершается штатно (TASK-052); live: «restored after 4 failures», Ctrl+C → rc=0 | **v3.13.20** | `day_47.6_backlog080_081_scanner_reliability_report.md` |
| 47.7 (BUG-086) | masking контекстов — критический блокер v3.0.0: mask_context покрывал 6 паттернов из 19 в MASK_RULES (в context_* утекали ghp_/Basic/xoxb-/AKIA/+1); новая реализация — конвейер `_CONTEXT_PATTERNS` (TASK-053, 21 паттерн: специфичные токены раньше generic, только значение KEY=VALUE); live task 40/41 — в контекстах 0 сырых паттернов (SQL + API viewer); тесты: 20 unit (187 passed) + E2E | **v3.13.21** | `day_47.7_fix_bug086_mask_context_report.md` |

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
| BACKLOG-039 | Аудит NOT NULL полей | 📋 | 🟡 |
| BACKLOG-044 | Защита `/metrics` | 📋 production | 🟡 |
| BACKLOG-045 | Параметризация портов | 📋 | 🟢 |
| BACKLOG-063 | Presidio производительность | 📋 v3.1.0 | 🟡 |
| BACKLOG-064 | Бенчмарк сканирования | 📋 v3.1.0 | 🟢 |
| BACKLOG-065 | Удалить `findings_old` | 📋 v3.0.0 | 🟢 |
| BACKLOG-068 | Per-scanner keys | 📋 v3.1.0 | 🟡 |
| **BACKLOG-078** | **Linux-агент вне Docker** | 📋 v3.0.0 | 🟢 |
| **BACKLOG-079** | **Опциональные targets в Prometheus** | 📋 v3.0.0 | 🟢 |
| **BACKLOG-080** | **Тестирование Windows-агента** | 📋 v3.1.0 | 🟡 |
| **BACKLOG-081** | **Тестирование Linux-агента** | 📋 v3.1.0 | 🟡 |
| **BACKLOG-082** | **Тестирование S3-агента + сканирование бакетов** | 📋 v3.1.0 | 🟡 |
| **BACKLOG-083** | **Alertmanager webhook → Manager не реализован** | 📋 v3.0.0 | 🟡 |
| **BACKLOG-084** | **Prometheus → Alertmanager не настроено** | ✅ **исправлено** 23.09 | 🟢 |
| **BACKLOG-085** | **Полный OCR-пайплайн с bbox (tesseract tsv)** | 📋 v3.1.0 | 🟢 |

*(Закрытые в v3.13.9: BUG-037…059 — все 15)*
*(Закрытые в v3.13.10: BUG-048b)*
*(Закрытые в v3.13.11: TASK-016, TASK-018, TASK-020 — ТЗ №2)*
*(Закрытые в v3.13.12: BUG-067, BUG-063 (Luhn), BUG-066, BUG-065, BUG-061 — ТЗ №3)*
*(Закрытые в v3.13.13: TASK-029 (OCR-секция), TASK-030 (Presidio ru+en) — ТЗ №4)*
*(Закрытые в v3.13.14: TASK-033 (BUG-066b), TASK-034 (BUG-067d), TASK-035 (BUG-069/070), TASK-036 (BUG-065) — ТЗ №5)*
*(Закрытые в v3.13.15: TASK-037 (BUG-071/074), TASK-038 (BUG-072), TASK-039 (BUG-073) — ТЗ №6)*
*(Закрытые в v3.13.16: TASK-040 (BUG-075) — ТЗ №7)*
*(Закрытые в v3.13.17: TASK-041/042 (BUG-077), TASK-043 (VERSION агентов) — ТЗ №8)*
*(Закрытые в v3.13.18: TASK-044 (BUG-077 diag — Manager дефолтил bbox); BUG-077 ✅ live task 38 — ТЗ №8 diag)*
*(Закрытые в v3.13.19: TASK-045..050 (BACKLOG-086 — встроенные фрагменты); BUG-079 исправлен (TASK-048 → /fragment только Auditor+) — ТЗ BACKLOG-086)*
*(Закрытые в v3.13.20: TASK-051 (BUG-080 — heartbeat backoff); TASK-052 (BUG-081 — graceful shutdown SIGINT/SIGBREAK) — ТЗ BUG-080/081)*
*(Закрытые в v3.13.21: TASK-053 (BUG-086 — masking контекстов: mask_context конвейером _CONTEXT_PATTERNS, 21 паттерн вместо 6) — ТЗ BUG-086)*
*(Отложено до v3.1.0: BACKLOG-085 (OCR bbox), BACKLOG-087 (дедупликация фрагментов), BACKLOG-088 (шифрование fragment_data, AES-256-GCM))*
*(Минорные: BUG-060 (BOM email) 📋 v3.1.0; BUG-061 (восстановление HTTP после падения Manager) 📋 v3.1.0; BUG-076 (dcap_scanner_current_task) 📋 v3.1.0; BACKLOG-076 (last_seen_at/findings_count) 📋 v3.1.0; BACKLOG-077 (heartbeat после инициализации классификаторов) 📋 v3.1.0)*

---

## 🎯 Ключевые решения

**Findings Refactor (v3.9.0-v3.13.16):**
- Findings = строка/фрагмент, гибрид masked + AES-256-GCM
- HMAC-SHA256 fingerprint
- Ключи Findings — только через ENV (Docker Secrets убраны, TASK-018)
- Scanner fail-fast без ключей
- Ротация с downtime (перешифровка `reencrypt_findings.py` + обновление ENV, TASK-016; E2E — TASK-020)
- Единый ключ для v3.0.0, per-scanner — v3.1.0 (BACKLOG-068)
- **Дедупликация Manager — глобальная по fingerprint** (BACKLOG-076)

**Аутентификация (Блок 2):**
- `verify_token(token, expected_type)` — access ≠ refresh
- RBAC системно — `Depends(require_role(...))` во все write-эндпоинты
- Middleware извлекает JWT для machine-API (BUG-048b)
- Cookie `Secure` — env `AUTH_COOKIE_SECURE`
- `jti` + `iat` + Redis blacklist
- Audit reveal: `event_type=finding_reveal`, `event_source=api`, `metadata.action=finding_revealed`

**Scanner (Блок 3):**
- Scanner — на хосте, не в Docker
- Heartbeat-thread (30 с), fail-open
- spaCy `sm` (ru + en, двухпроходный Presidio)
- OCR: Tesseract (rus+eng), изолированный OCRWorker
- **OCR bbox: до v3.1.0 = None** (координаты не вычисляются, Tesseract без tsv); `/fragment` для image_region без bbox отдаёт весь PNG (`X-Fragment-Mode: full-image`); полный OCR-пайплайн — BACKLOG-085 (v3.1.0); v3.13.18: Manager больше не дефолтит bbox при сохранении findings
- **Встроенные фрагменты (BACKLOG-086, v3.13.19):** сканер встраивает OCR-PNG (≤ MAX_FRAGMENT_EMBED_SIZE, default 2 МБ) base64+SHA-256 в payload → Manager хранит `fragment_data` в findings → `/fragment` отдаёт из БД (`X-Fragment-Mode: embedded`, `X-Fragment-Hash`); `/fragment/hash` — метаданные; RBAC `/fragment` и `/fragment/hash` — только Auditor+ (BUG-079); аудит `event_type=fragment_accessed` (metadata.action, finding_id, mode); батчинг результатов по размеру (MAX_BATCH_SIZE_BYTES=20 МБ, TASK-050); дедупликация фрагментов — BACKLOG-087 (v3.1.0), шифрование — BACKLOG-088 (v3.1.0)
- Фильтры PII: `_filter_url_over_email_finding`, `_filter_spacy_noise`, `_filter_uk_nhs_with_phone`
- Luhn-валидация для `credit_card`
- **Reliability (BUG-080/081, v3.13.20):** heartbeat backoff 5→10→30→60→120 с (TASK-051): `_next_sleep`/`_send_heartbeat`, DEBUG на каждый фейл без спама, WARNING только на 1-м и каждые 5 попыток, `_stop.wait()` вместо `time.sleep()` (мгновенный выход при stop), INFO «Heartbeat restored after N failure(s)»; graceful shutdown (TASK-052): SIGINT (и SIGBREAK на Windows) → `_handle_sigint` ставит `_should_exit`/`_stop_event`, `stop()` = heartbeat stop + `_shutdown_classifiers()`, OCRWorker завершается штатно (None в request_queue → join(5) → terminate → join(2) → kill) — live Ctrl+C → rc=0
- **Masking контекстов (BUG-086, v3.13.21):** `mask_context` — конвейер `_CONTEXT_PATTERNS`: список `(regex, category)` на все категории MASK_RULES (21 паттерн: ghp_/github_pat_→github_token, xoxb→slack_token, AKIA→aws_key, sk-→api_key, discord, JWT eyJ, PEM→ssh_key, Basic→basic_auth, scheme://→database_url, generic password/api_key/token в KEY=VALUE — маскируется ТОЛЬКО значение (2 capture-группы), email, телефоны +7/+1/международные, паспорт/СНИЛС/ИНН/cards); специфичные категории раньше generic; `person` и `high_entropy` в контексте НЕ маскируются (high_entropy — до v3.1.0); BUG-086 был критическим блокером v3.0.0 (Viewer+ видел сырые credentials в context_* через API)

**Мониторинг (Блок 8):**
- Prometheus + Grafana + Alertmanager — работают
- Prometheus targets: manager, scanner, s3-agent, celery, postgres, redis (6/6 up)
- Prometheus `rule_files` = alerts.yml (4 правила)
- Prometheus `alerting.alertmanagers` = alertmanager:9093 (BACKLOG-084 fix)
- Alertmanager: webhook_configs → manager:8000/api/alerts/webhook (BACKLOG-083 — не реализован)
- Grafana: 2 dashboards (`dcap-overview`, `dcap-scanner`)
- Агенты (Windows/Linux) — **вне Docker**, targets опциональны (BACKLOG-078, 079)
- Heartbeat: scanner + S3-agent

---

## 📁 Последние использованные файлы

- `scanner/src/heartbeat.py` — TASK-051: `_send_heartbeat` (DEBUG, timeout=5), `_next_sleep` (backoff 5→10→30→60→120, WARNING 1/5/10), run на `_stop.wait()`
- `scanner/src/managed_scanner.py` — TASK-052: `_handle_sigint` (SIGINT+SIGBREAK), `stop()` (heartbeat + `_shutdown_classifiers`), хуки SIGBREAK
- `scanner/classifiers/ocr_worker.py` — TASK-052: graceful `stop_ocr_worker` — None → join(5) → terminate → join(2) → kill
- `tests/unit/test_heartbeat_backoff.py` (4), `tests/unit/test_scanner_shutdown.py` (3) — 167 unit passed
- `scanner/src/encryption.py` — TASK-053 (BUG-086): `_CONTEXT_PATTERNS` + `mask_context` конвейером (21 паттерн, только значение KEY=VALUE)
- `tests/unit/test_mask_context_v31321.py` (20) — 187 unit passed
- `tests/e2e/test_mask_context_e2e.py` (1) — E2E против живого стека: контексты последнего скана без сырых credentials
- `docker-compose.yml` — manager/webui/celery → 3.13.21
- `docs/admin-guide/05-security.md`, `docs/admin-guide/10-troubleshooting.md` — секция по masking контекстов

---

**Актуально на:** 26.09.2026
**Версия:** v3.13.21
**Следующий шаг:** Блок 5 (WebUI) — продолжить с п.2.3 (фильтры)