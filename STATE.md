> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 25.09.2026
**Текущая версия:** v3.13.17
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блок 3 (Scanner deep) ✅; Блок 8 (Мониторинг) ✅; BUG-077 ✅ (v3.13.17); следующий шаг — Блок 5 (WebUI)

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 47.3 — BUG-077 (v3.13.17): bounding_box=None для OCR + fallback full-image |
| Статус дня | ✅ Выполнен |
| Последний принятый отчёт | `day_47.3_fix_bug077_report.md` (v3.13.17) |
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
- **OCR bbox: до v3.1.0 = None** (координаты не вычисляются, Tesseract без tsv); `/fragment` для image_region без bbox отдаёт весь PNG (`X-Fragment-Mode: full-image`); полный OCR-пайплайн — BACKLOG-085 (v3.1.0)
- Фильтры PII: `_filter_url_over_email_finding`, `_filter_spacy_noise`, `_filter_uk_nhs_with_phone`
- Luhn-валидация для `credit_card`

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

- `scanner/connectors/filesystem.py` — BUG-077 (TASK-041): bounding_box=None для OCR
- `manager/src/api/findings.py` — BUG-077 (TASK-042): `/fragment` fallback full-image
- `docker-compose.yml` — TASK-043: VERSION агентов 3.13.16, manager/webui 3.13.17
- `tests/unit/test_ocr_bbox_v31317.py` — 2 теста (144 passed всего)
- `monitoring/prometheus/prometheus.yml` — BACKLOG-084 fix (секция `alerting`)
- `manager/src/api/*.py` — проверка endpoint `/api/alerts/webhook` (отсутствует)
- `monitoring/grafana/provisioning/` — datasource + 2 dashboard
- `STATE.md`, `ROADMAP.md`, `STATE_TEST_SESSION.md`, `CHANGELOG.md` — обновлены

---

**Актуально на:** 25.09.2026
**Версия:** v3.13.17
**Следующий шаг:** Блок 5 (WebUI) — продолжить с п.2.3 (фильтры)