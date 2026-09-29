> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 29.09.2026
**Текущая версия:** v3.13.26
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блок 3 (Scanner deep) ✅; Блок 8 (Мониторинг) ✅; BACKLOG-086 ✅; BUG-080/081 ✅; BUG-086 ✅; Блок 5 (WebUI) п.2.3 ✅; BUG-095 ✅; BUG-096/096b/097 ✅; BUG-098/099/100/101 ✅ — ревью находок теперь аудируется (PATCH + bulk + DELETE), сброс ревью чистит поля, `/false-positives` не отдаёт 500 и показывает путь файла; следующий шаг — Блок 5, п.2.4

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 49 (BUG-098/099/100/101) — аудит ревью находок, сброс review-полей, пагинация FP, file_path |
| Статус дня | ✅ Выполнен |
| Последний принятый отчёт | `day_49_bug098_101_report.md` (v3.13.26) |
| Следующий шаг | Блок 5 (WebUI) — п.2.4: отчёты/архив, следующий прогон по бэклогу |
| Открытые вопросы к архитектору | 1) TASK-063 (алерт на N неудачных входов) — отложен на v3.1.0/SIEM; 2) BUG-061 (сканер не восстанавливает HTTP после падения Manager) — воспроизведён при рестарте контейнера Manager: heartbeat отбивается `RemoteDisconnected`, urllib3-retry вытягивает, но отдельная задача; 3) логи сканера пишутся в stderr, а не в `logging.file` (`logs/scanner.log`) — файл не создаётся, диагностика затруднена |

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
| 48 (Блок 5, п.2.3) | Фильтры/пагинация/аудит/экспорт WebUI: TASK-054 (BUG-087) прокси ронял `X-Total-Count`/`X-Fragment-*`/`Content-Disposition`; TASK-055 (BUG-088) fragment `<img>` без Bearer → 401, теперь fetch+blob; TASK-056 (BUG-089) `is_active == 1` → 500 на PostgreSQL; TASK-057 (BUG-090) CSV-категории, пустые параметры вместо 422, `detector`/`fragment_type`/`search`/`order_by=id`; TASK-058 (BUG-091) `event_source` в `/api/audit` + data-driven фильтры из `/api/audit/stats`; TASK-059 (BUG-093) export через fetch+blob вместо `window.location`; тесты: 33 unit (220 passed) + 8 E2E | **v3.13.22** | `day_48_block5_webui_filters_report.md` |
| 48.1 (TASK-060) | «BUG-087» аудит reveal: 🔴 **баг ложный** — код пишет `auditor`/`admin` корректно; `dcap` = `CURRENT_USER`, т.к. диагностический SQL использовал `SELECT user` без кавычек (в PG `user` — keyword). Фикс кода не требуется; регрессия закрыта 7 unit + 3 E2E (227 unit passed), раздел 6 в troubleshooting; live: `revealed_by=auditor`, `SELECT "user"` → `auditor` | **v3.13.23** | `day_48.1_bug087_audit_user_report.md` |
| 48.2 (BUG-095) | Аудит auth + управления пользователями: TASK-061 (`manager/src/auth/audit.py` — `log_auth_event`, `_sanitize`, `classify_login_failure`, `role_diff`; `auth_login`/`auth_failed`/`auth_logout`) + TASK-062 (`user_created`/`user_updated`/`user_deleted`/`user_password_changed`/`role_assigned`/`role_revoked`); `auth_refresh` не пишется по решению из ТЗ; тесты: 15 unit + 2 E2E (242 unit passed); live: все 9 event_type в `audit_logs`, утечек пароля 0 | **v3.13.24** | `day_48.2_bug095_auth_audit_report.md` |
| | 48.3 (BUG-096/096b/097) | TASK-064 (BUG-096): `_m.User` → `User` из `manager.src.auth.models` в `findings.py`, live `/false-positives` 200; TASK-065 (BUG-096b): `finding_type`/`category`, `_get_with_retry` (RemoteDisconnected), precheck сканера, `@pytest.mark.timeout(600)` + 240 с, освобождение зависших заданий, `fingerprint` не в ответе API; TASK-066 (BUG-097): диагноз — исключение в `_execute_task` гасилось и задание висело `assigned` 30 мин, оффлайн-пачка `task_43.json` давала вечный 404; фикс — `SubmitStatus`(OK/RETRY/LOST) + `submit_results_status()`, отбрасывание потерянной пачки, `_fail_task_safely()` при исключении, логирование 404 в Manager с task_id/scanner/batch; тесты: +8 и +14 unit (264 unit passed), E2E 50 passed / 2 skipped (было 47/3 failed); live: 200 на /false-positives, 404 с контекстом | **v3.13.25** | `day_48.3_bug096_097_report.md` |
| 49 (BUG-098/099/100/101) | BUG-101: PATCH и bulk не писались в `audit_logs` (0 записей за 30 мин) — хелпер `_log_finding_status_change()` с маппингом статуса (`confirmed`/`false_positive`/`archived`/`new` → `finding_confirmed`/`finding_false_positive`/`finding_archived`/`finding_reset`), `via='patch'|'bulk'`, по записи на находку в bulk (Вариант A), единый коммит; закрыт открытый вопрос ТЗ — DELETE тоже аудируется (`finding_deleted`, лог создаётся до `db.delete`); BUG-100: `_apply_status()` очищает `reviewed_by`/`reviewed_at` при `status=new`, `comment` из тела (PATCH и bulk); BUG-099: `OptInt` + `_clamp_int` в `list_false_positives` (было 500 на `offset=-1`/`limit=-5`), проаудирован весь `manager/src/api/` — остальные защищены `ge/le` (422) либо явной проверкой (400); BUG-098: `file_path` = `fragment_path`, `res_map` только fallback; сигнатуры PATCH/bulk/DELETE получили `request: Request` (нужен `source_host`); тесты: +40 unit (301 unit passed), E2E 38 passed/9 skipped на стенде + 5 отдельно на основном стенде; live: 4 записи аудита от PATCH + 2 от bulk, `reviewed_by=NULL` после reset, `file_path=C:\test\scanner_clean\pii\phones_clean.txt` | **v3.13.26** | `day_49_bug098_101_report.md` |

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
*(Закрытые в v3.13.22: TASK-054 (BUG-087 — прокси headers: X-Total-Count/X-Fragment-*/Content-Disposition; Set-Cookie и hop-by-hop отбрасываются), TASK-055 (BUG-088 — fragment через fetch+blob с Bearer), TASK-056 (BUG-089 — is_active == True вместо == 1, 500 на PostgreSQL), TASK-057 (BUG-090 — CSV-категории, пустые числовые параметры, detector/fragment_type/search/order_by=id в list+count+export), TASK-058 (BUG-091 — фильтр event_source в /api/audit + опции фильтров из /api/audit/stats), TASK-059 (BUG-093 — export findings через fetch+blob) — Блок 5 п.2.3)*
*(Закрытые в v3.13.24: BUG-095 (TASK-061 — аудит login/logout: auth_login/auth_failed/auth_logout + reason user_not_found|user_inactive|invalid_credentials; TASK-062 — аудит user_created/user_updated/user_deleted/user_password_changed/role_assigned/role_revoked; пароли/токены вырезаются _sanitize(); auth_refresh не пишется по решению ТЗ). Закрыт пробел 152-ФЗ/GDPR/PCI DSS 10.2 и подготовлена выгрузка для SIEM (BACKLOG-069/070))*
*(Новые находки дня 48.2: BUG-096 — 500 в `GET /api/findings/false-positives` (`manager/src/api/findings.py:324`: `_m.User`, но `User` живёт в `manager.src.auth.models`); 2 устаревших E2E-теста ждут `finding_type in {pii, credentials}` после рефакторинга v3.13.22 (теперь `category`: email/person/phone/aws_key))*
*(Закрытые в v3.13.25: BUG-096 (TASK-064 — `_m.User` → `User` из `manager.src.auth.models`; live `/false-positives` 200 вместо 500); BUG-096b (TASK-065 — `finding_type`/`category` в E2E, `_get_with_retry` против `RemoteDisconnected` на keep-alive 5 с, precheck активного сканера, `@pytest.mark.timeout(600)` против глобального `timeout=300`, освобождение зависших заданий, `fingerprint` наружу не отдаётся `_finding_to_dict`); BUG-097 (TASK-066 — задание падало в `_execute_task` на удалённом pytest-каталоге, исключение гасилось и задание висело `assigned` 30 мин = `TASK_TIMEOUT_MINUTES`; оффлайн-пачка `task_43.json` ретраилась с 404 бесконечно. Фикс: `SubmitStatus` OK/RETRY/LOST + `submit_results_status()`, отбрасывание потерянной пачки в `_flush_offline`, `_fail_task_safely()` при исключении, логирование 404 в Manager с task_id/scanner/batch. E2E: 50 passed / 2 skipped — полный цикл сканирования 15 с вместо таймаута 240 с))*
*(Отложено до v3.1.0: TASK-063 — алерт на N неудачных входов (совместно с SIEM-интеграцией); BACKLOG-085 (OCR bbox), BACKLOG-087 (дедупликация фрагментов), BACKLOG-088 (шифрование fragment_data, AES-256-GCM))*
*(Закрытые в v3.13.26: BUG-101 (PATCH `/{id}` и `POST /bulk` не писали `audit_logs` — 0 записей за 30 мин при 10+ вызовах; хелпер `_log_finding_status_change()` с маппингом статуса на event_type, `via='patch'|'bulk'`, **по записи на находку** в bulk = Вариант A, единый коммит, без N коммитов; закрыт открытый вопрос ТЗ — `DELETE /{id}` тоже не аудировался → добавлен `finding_deleted`, лог строится до `db.delete()` и уходит в том же коммите, т.к. после коммита инстанс expire'ится); BUG-100 (PATCH `status='new'` не очищал `reviewed_by`/`reviewed_at` — находка со статусом new выглядела одобренной; общая `_apply_status()` чистит поля на сбросе, `comment` из тела запроса; PATCH и bulk больше не расходятся); BUG-099 (`list_false_positives` остался со старыми `limit: int = Query(100, le=1000)` / `offset: int = 0` — `offset=-1` и `limit=-5` доходили до `.offset()/.limit()` и давали 500; переведён на `OptInt` + `_clamp_int` как в `list_findings`; проаудирован весь `manager/src/api/` — прочие эндпоинты защищены `ge/le` (422) либо явной проверкой (400), других 500 нет); BUG-098 (`file_path` брался из `res_map` = путь **ресурса/директории** раньше `fragment_path` = путь **файла**, поэтому `/false-positives` и `/findings?status=false_positive` расходились; `fragment_path` в приоритете, `res_map` — fallback)*)
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

**WebUI (Блок 5, v3.13.22):**
- WebUI не ходит в БД — всё через прокси `webui/api/routes.py` на Manager; JWT в localStorage, `Authorization: Bearer`, cookie через прокси не доходят
- **Прокси пробрасывает заголовки ответа** (`forwarded_headers`): `X-Total-Count` (пагинация), `X-Fragment-Mode`/`X-Fragment-Hash`/`X-Bounding-Box`, `Content-Disposition` (экспорт); отбрасываются hop-by-hop (`connection`, `transfer-encoding`, `content-length`, `content-encoding`) и `set-cookie` — BUG-087
- Бинарные/приватные данные (fragment PNG, экспорт CSV/JSON) грузятся `fetch()` + `Blob` + Bearer, а не `<img src>`/`window.location` (оба не шли заголовок Authorization → 401) — BUG-088, BUG-093
- **Фильтры findings:** `category` принимает CSV («phone, email») — legacy-категории (pii/credentials/code) фильтруются по `finding_type`, остальные по `category`, объединение через ИЛИ; `detector`, `fragment_type`, `search` (путь/маскированные значения), `order_by=id`; пустые числовые параметры (`?task_id=&limit=`) трактуются как «без фильтра» — BUG-090
- **FastAPI 0.137 gotcha:** `BeforeValidator` в `Annotated` теряется, если `Query(...)` указан в default (`create_model_field` берёт annotation из field_info) → `Query()` объявлен внутри `Annotated`, дефолт через `=`; числовые `le`/`ge` несовместимы с `Optional[int]` (TypeError на None) → `_clamp_int()` в коде
- **Фильтры аудита** заполняются реальными значениями из `/api/audit/stats` (`by_source`, `by_type`) — раньше были захардкожены read/write/delete и windows/linux, а фактические события — `finding_reveal`/`fragment_accessed` и `api`/`scanner`; серверный фильтр `event_source` — BUG-091
- `/api/access/*`: `is_active` — Boolean, сравнение `== True` (на PostgreSQL `== 1` давало 500) — BUG-089
- Тесты: `tests/unit/test_webui_block5_v31322.py` (33), `tests/e2e/test_webui_block5_v31322.py` (8) — E2E логинится один раз на модуль (auth rate limit 5/мин)

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
- `webui/api/routes.py` — TASK-054: `HOP_BY_HOP` + `forwarded_headers()` (BUG-087)
- `webui/static/js/finding_detail.js` — TASK-055: fragment через fetch+blob, `X-Fragment-Mode`/`X-Fragment-Hash`
- `webui/static/js/findings.js` — TASK-059: `showExportDialog` через fetch+blob; `collectFilters` (detector/fragment_type/search), `resetFilters` (BUG-090/093)
- `webui/templates/findings.html` — TASK-057: поиск, CSV-категория, детектор, фрагмент, кнопка «Сброс»
- `webui/templates/audit.html` — TASK-058: `loadFilterOptions`/`fillSelect` из `/api/audit/stats`, `d.total ?? events.length`
- `manager/src/api/findings.py` — TASK-057: `OptInt` + `_clamp_int`, `_parse_categories`/`_apply_category_filter` (OR), фильтры в list/count/export, `has_fragment` по fragment_data
- `manager/src/api/audit.py` — TASK-058: параметр `event_source` + SQL-фильтр
- `manager/src/api/webui.py` — TASK-056: `AccessEntry.is_active == True` (2 места)
- `tests/unit/test_webui_block5_v31322.py` (33) + `tests/e2e/test_webui_block5_v31322.py` (8) — 220 unit passed
- `docker-compose.yml` — manager/webui/celery → 3.13.22
- `manager/src/api/findings.py` — BUG-101: `_STATUS_EVENT_MAP` + `_log_finding_status_change()` (без коммита) + `_apply_status()`; вызовы в `update_finding` (`via='patch'`) и `bulk_update` (`via='bulk'`); `finding_deleted` в `delete_finding` (лог до `db.delete`); все три приняли `request: Request` ради `source_host`
- `manager/src/api/findings.py` — BUG-100: сброс `status='new'` чистит `reviewed_by`/`reviewed_at`, `comment` из тела
- `manager/src/api/findings.py` — BUG-099: `list_false_positives` на `OptInt` + `_clamp_int(limit, 100, 1, 1000)` / `_clamp_int(offset, 0, 0, 10_000_000)`
- `manager/src/api/findings.py` — BUG-098: `file_path = f.fragment_path or res_map.get(f.resource_id)`
- `tests/unit/test_audit_status_change_v31326.py` (18), `test_patch_reset_clears_review_v31326.py` (8), `test_fp_pagination_v31326.py` (8), `test_fp_file_path_v31326.py` (6) — 301 unit passed
- `tests/unit/test_false_positives_v31325.py` — ассерт `file_path` переведён с директории на путь файла (закреплял BUG-098)
- `.env`, `.env.example`, `docker-compose.yml` — VERSION → 3.13.26; образы `dcap/manager:3.13.26`, `dcap/webui:3.13.26`

---

**Актуально на:** 29.09.2026
**Версия:** v3.13.26
**Следующий шаг:** Блок 5 (WebUI) — п.2.4 (отчёты/архив) или следующий пункт бэклога ROADMAP