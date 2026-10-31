# 🔧 ТЗ №5: Fix-спринт №5 — Scanner deep (v3.13.14)

**Дата:** 21.09.2026
**Версия:** v3.13.13 → **v3.13.14**
**Ветка:** `fix/scanner_deep_5`
**Приоритет:** 🔴 важно (блокеры v3.0.0: BUG-065, BUG-066b)
**Источник:** верификация ТЗ №4 (v3.13.13), `STATE_TEST_SESSION.md` (Блок 3)
**Предыдущее ТЗ:** `TZ_FIX_SPRINT_4.md` — **выполнено частично** (BUG-063 ✅, 067c ⚠️, 066 ⚠️, 065 ❌)
**Оценка:** ~2.5 часа

---

## 🎯 Контекст

**По итогам верификации ТЗ №4 (v3.13.13) выявлено 4 нерешённых бага + 2 новых:**

| ID | Название | Статус |
|----|----------|--------|
| **BUG-063** | `credit_card` не детектируется | ✅ **ЗАКРЫТ** (v3.13.13) |
| **BUG-066b** | `scan_text` не фильтрует url-over-email | 🔴 **открыт** (2 свежих url) |
| **BUG-067c** | OCR | ⚠️ **частично** (OCR работает, но не помечен) |
| **BUG-067d** | OCR findings не помечаются `image_region`/`ocr` | 🔴 **открыт** |
| **BUG-065** | `database_url`/`github_token`/`slack_token`/`basic_auth` | 🔴 **открыт** (fix TASK-032 не применён) |
| **BUG-069** | Ложные `date_time` из `en`-прохода | 🟢 **новый** |
| **BUG-070** | Ложные `person`/`organization` из `en`-прохода | 🟢 **новый** |

**Что работает (не трогать):**
- **BUG-063** — двухпроходный `ru`+`en` → `credit_card` найден ✅.
- **OCR для PNG** — работает (email/phone из `screenshot.png`).
- **Маскирование** — корректное.
- **Prefilter** — ✅.
- **Luhn-фильтр** — ✅.

---

## 📋 Задачи

### TASK-033 — BUG-066b: `scan_text` не фильтрует url-over-email

**Приоритет:** 🔴 важно

**Компонент:** `scanner/classifiers/pii_classifier.py::scan_text`, `scan_line`

**Проблема:**

**В `scan_text`** (построчный конвейер) — **НЕ вызывается** `_filter_url_over_email`. **Фильтр применяется только в `classify()`** (old-путь `Orchestrator`).

**Построчный конвейер (`scan_text`)** — используется в `FilesystemConnector._scan_text` → **url-дубликаты email проходят**.

**Дополнительно:** `scan_text` возвращает **`Finding`** (`start_pos`/`end_pos`), а `_filter_url_over_email` работает с **`ClassificationFinding`** (`position`/`len(value)`). **Модели разные.**

**Проверено (task 30):**
- `emails.txt` — 2 свежих url (line 1, 2) с email-доменом.
- `last_seen_at = 2026-09-21 20:27:28` — свежие.

**Fix — добавить отдельный фильтр для `Finding`:**

```python
def _filter_url_over_email_finding(self, findings: List[Finding]) -> List[Finding]:
    """BUG-066b: url-over-email для модели Finding (start_pos/end_pos).
    
    В построчном конвейере (scan_text/scan_line) findings — это Finding,
    поля start_pos/end_pos. Отбрасываем url, который находится внутри
    email-спана.
    """
    email_spans = {
        (f.start_pos, f.end_pos)
        for f in findings
        if f.category in ("email", "PII_EMAIL")
    }
    if not email_spans:
        return findings

    filtered = []
    for f in findings:
        if f.category in ("url", "PII_URL"):
            if any(e_start <= f.start_pos and f.end_pos <= e_end
                   for e_start, e_end in email_spans):
                continue
        filtered.append(f)
    return filtered
В scan_text — перед dedup:

python
# BUG-066b: url-over-email (Finding)
findings = self._filter_url_over_email_finding(findings)

# BUG-022.9: дедупликация по позиции
by_pos = {}
...
В scan_line — перед dedup:

python
# BUG-066b: url-over-email (Finding)
findings = self._filter_url_over_email_finding(findings)

return self._deduplicate(findings)
Тесты:

test_scan_text_url_not_duplicated_by_email — email + domain → только email.

test_scan_text_url_standalone — https://example.com (без email) → url finding.

test_scan_line_url_not_duplicated_by_email — то же для построчного.

Verify (ручной):

emails.txt → после fix: SELECT COUNT(*) FROM findings WHERE category='url' AND fragment_path LIKE '%emails.txt%' AND last_seen_at > now() - interval '5 min' → 0.

Оценка: 15 мин.

TASK-034 — BUG-067d: OCR findings не помечаются image_region/ocr
Приоритет: 🟡 важно

Компонент: scanner/connectors/filesystem.py::scan_file

Проблема:

OCR работает — PNG → текст → Presidio → findings. НО — findings не помечаются:

fragment_type = "text_line" (должно быть "image_region").

detector = "presidio" (должно быть "ocr").

bounding_box = None (должно быть {x, y, w, h}).

Проверено (task 30):

text
id=1261 | screenshot.png | email | presidio | text_line
id=1262 | screenshot.png | phone | presidio | text_line
Причина:

python
# filesystem.py::scan_file
if ext in _IMAGE_EXTENSIONS:
    text = self._extract_document(str(p), ext)
    if not text:
        return []
    return self._scan_text(text, classifiers, str(p))   # ← findings как text_line
_scan_text возвращает findings без различения «откуда текст» (изображение vs текстовый файл).

Fix — пост-обработка findings для _IMAGE_EXTENSIONS:

python
if ext in _IMAGE_EXTENSIONS:
    text = self._extract_document(str(p), ext)
    if not text:
        return []
    findings = self._scan_text(text, classifiers, str(p))
    # BUG-067d: помечаем findings как image_region + ocr
    for f in findings:
        f.fragment_type = "image_region"
        f.detector = "ocr"
        f.bounding_box = {"x": 0, "y": 0, "width": 0, "height": 0}
    return findings
Тесты:

test_scan_image_fragment_type — PNG → fragment_type=image_region.

test_scan_image_detector_ocr — PNG → detector=ocr.

test_scan_image_bounding_box — PNG → bounding_box заполнен.

Verify (ручной):

screenshot.png → findings с fragment_type=image_region, detector=ocr.

Оценка: 20 мин.

TASK-035 — BUG-069/070: ложные date_time/person/organization из en-прохода
Приоритет: 🟢 nice-to-have

Компонент: scanner/classifiers/pii_classifier.py

Проблема:

Двухпроходный анализ (en + ru) даёт ложные findings:

date_time × 2 — Card 1:, Card 2: в cards.txt.

person × 2 — GITHUB_TOKEN=..., SLACK_TOKEN=... в database.env.

organization × 1 — DATABASE_URL=... в database.env.

Причина: spaCy en_core_web_sm агрессивно классифицирует капитализированные токены как PERSON/ORG/DATE_TIME.

Fix — фильтр по паттернам:

python
def _filter_spacy_noise(self, findings: List[Finding]) -> List[Finding]:
    """BUG-069/070: фильтр ложных PERSON/ORG/DATE_TIME из spaCy (en).
    
    spaCy en_core_web_sm распознаёт 'Card 1:', 'GITHUB_TOKEN=...',
    'DATABASE_URL=...' как PERSON/ORG/DATE_TIME. Отбрасываем.
    """
    NOISY_CATEGORIES = {"person", "organization", "date_time"}
    
    filtered = []
    for f in findings:
        if f.category in NOISY_CATEGORIES:
            val = f.match_text or ""
            # Пропускаем, если значение:
            # - содержит '_', '=', ':', '://'
            # - >50% цифр
            # - длина < 3
            # - содержит 'card ' (case-insensitive)
            if (any(c in val for c in "_:=")
                or "://" in val
                or sum(c.isdigit() for c in val) > len(val) / 2
                or len(val) < 3
                or "card " in val.lower()):
                continue
        filtered.append(f)
    return filtered
Применить в scan_text/scan_line/classify — после Presidio:

python
# BUG-069/070: фильтр spaCy noise
findings = self._filter_spacy_noise(findings)
Альтернатива (радикальнее): не запрашивать PERSON/ORG/DATE_TIME при en-проходе:

python
results_en = analyzer.analyze(
    text=text,
    language="en",
    entities=[...],  # явный список без PERSON/ORG/DATE_TIME
)
Рекомендую — фильтр (Вариант A) — безопаснее.

Тесты:

test_filter_fake_date_time — Card 1: не в findings.

test_filter_fake_person — GITHUB_TOKEN=... не в person.

test_real_person_preserved — Иван Иванов остаётся.

Verify (ручной):

cards.txt → без date_time.

database.env → без person/organization.

Оценка: 30 мин.

TASK-036 — BUG-065: TASK-032 (credentials-паттерны) — не применён
Приоритет: 🟡 важно

Компонент: scanner/classifiers/credentials_classifier.py

Проблема:

Все 5 изменений из TASK-032 (ТЗ №4) — отсутствуют в коде (проверено при верификации v3.13.13):

python
# 1. PLACEHOLDER_PATTERNS — [0-9x]{8,} ВСЁ ЕЩЁ ЕСТЬ
PLACEHOLDER_PATTERNS = [
    ...
    r'[0-9x]{8,}',             # ← 🔴 НЕ УБРАН
    ...
]

# 2. _apply_filters — НЕТ SIGNATURE_PREFIXES
def _apply_filters(self, value: str, line: str) -> bool:
    # 1. Минимальная длина
    if len(value) < self._min_length:
        return False
    # 2. Плейсхолдеры
    if self._is_placeholder(value):
        return False
    # ... НЕТ проверки value.startswith(SIGNATURE_PREFIXES)
python
# 3. BASIC_AUTH — старый regex (требует Authorization:)
{"name": "BASIC_AUTH", "pattern": r'Authorization:\s*Basic\s+[A-Za-z0-9+/=]+', ...}

# 4. SLACK_TOKEN — старый regex (3 группы)
{"name": "SLACK_TOKEN", "pattern": r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}', ...}
Fix — применить все 5 изменений:

Fix 1 — _apply_filters: пропускать SIGNATURE_PREFIXES
python
def _apply_filters(self, value: str, line: str) -> bool:
    # BUG-065 fix: signature-prefix (AKIA, ghp_, xox, eyJ, sk-, ...)
    # пропускаем ДО placeholder-фильтров — это реальные токены,
    # а не плейсхолдеры, даже если содержат 8+ цифр подряд.
    if value.startswith(SIGNATURE_PREFIXES):
        return True
    
    # 1. Минимальная длина
    if len(value) < self._min_length:
        return False
    
    # 2. Плейсхолдеры
    if self._is_placeholder(value):
        return False
    
    # 3. Дампы
    if self._is_dump_value(value):
        return False
    
    # 4. Комментарии
    if self._is_comment_line(line):
        return False
    
    # 5. Mixed case
    if self._require_mixed and not self._has_mixed_case(value):
        return False
    
    return True
Fix 2 — PLACEHOLDER_PATTERNS: убрать [0-9x]{8,}
python
PLACEHOLDER_PATTERNS = [
    r'your_[a-z_]+',
    r'example_[a-z_]+',
    r'changeme',
    r'<[A-Z_]+>',
    r'{{[A-Z_]+}}',
    r'xxx+',
    # r'[0-9x]{8,}',             # ← УБРАТЬ
    r'NNN[_-]?[A-Z]+',
    r'^password[0-9]{1,2}$',    # ← уточнить: полное совпадение
    r'^admin[0-9]{1,2}$',
    r'^test[_-]?[a-z0-9]+$',
    r'^sample[_-]?[a-z0-9]+$',
    r'^demo[_-]?[a-z0-9]+$',
    r'example\.com',
    r'changeme\.com',
]
Fix 3 — BASIC_AUTH regex
python
{"name": "BASIC_AUTH", "pattern": r'\bBasic\s+[A-Za-z0-9+/=]{10,}', "confidence": 0.8, "check_entropy": False},
Fix 4 — SLACK_TOKEN regex
python
{"name": "SLACK_TOKEN", "pattern": r'xox[baprs]-[A-Za-z0-9-]{10,}', "confidence": 0.85, "check_entropy": False},
Fix 5 — _is_placeholder: не проверять URL
python
def _is_placeholder(self, value: str) -> bool:
    # BUG-065: не проверяем на placeholder, если value — URL
    if '://' in value:
        return False
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    return False
Тесты:

test_database_url_detected — DATABASE_URL=postgresql://... → database_url.

test_github_token_detected — ghp_<36> → github_token.

test_slack_token_detected — xoxb-<num>-<alnum> → slack_token.

test_basic_auth_detected — BASIC_AUTH=Basic <base64> → basic_auth.

Verify (ручной):

database.env → findings database_url, github_token, slack_token, basic_auth.

Оценка: 1-1.5 ч.

📊 Сводка задач
ID	Название	Приоритет	Оценка
TASK-033	BUG-066b: url-over-email в scan_text/scan_line	🔴	15 мин
TASK-034	BUG-067d: image_region/ocr для изображений	🟡	20 мин
TASK-035	BUG-069/070: ложные date_time/person/org	🟢	30 мин
TASK-036	BUG-065: TASK-032 — credentials-паттерны	🟡	1-1.5 ч
Итого: ~2.5 часа.

🚦 Порядок выполнения
TASK-033 (BUG-066b) — 15 мин, чистит findings.

TASK-034 (BUG-067d) — 20 мин, image_region.

TASK-036 (BUG-065) — 1-1.5 ч, credentials.

TASK-035 (BUG-069/070) — 30 мин, spaCy noise.

✅ Критерии приёмки
□ emails.txt → 0 свежих url (SELECT COUNT(*) FROM findings WHERE category='url' AND last_seen_at > now() - interval '5 min').
□ screenshot.png → fragment_type=image_region, detector=ocr, bounding_box ≠ NULL.
□ cards.txt → без ложных date_time.
□ database.env → без ложных person/organization.
□ database.env → findings database_url, github_token, slack_token, basic_auth.
□ Unit-тесты — зелёные.
□ /api/health → 3.13.14.
📌 Коммиты
text
fix: BUG-066b — _filter_url_over_email_finding в scan_text/scan_line (v3.13.14)
fix: BUG-067d — image_region/bounding_box/detector=ocr для изображений (v3.13.14)
fix: BUG-069/070 — фильтр spaCy noise (person/org/date_time) из en-прохода (v3.13.14)
fix: BUG-065 — credentials: SIGNATURE_PREFIXES, PLACEHOLDER_PATTERNS, BASIC_AUTH, SLACK_TOKEN (v3.13.14)
docs: CHANGELOG v3.13.14 — fix-спринт №5 (Scanner deep)
📚 Ссылки
scanner/classifiers/pii_classifier.py — BUG-066b, BUG-067d, BUG-069/070.

scanner/connectors/filesystem.py — BUG-067d.

scanner/classifiers/credentials_classifier.py — BUG-065.

TZ_FIX_SPRINT_4.md — ТЗ №4 (TASK-032 не применён).

STATE_TEST_SESSION.md — Блок 3.

🎯 Что после ТЗ №5
Verify — повторный скан scanner_deep → проверка 4 багов.

CHANGELOG v3.13.14.

STATE.md, ROADMAP.md — обновить.

GitHub публикация (BACKLOG-028/046).

Релиз v3.0.0.

Конец ТЗ №5. Приступай в порядке: TASK-033 → 034 → 036 → 035.

text

---

## 🎯 Итог

**Файл `TZ_FIX_SPRINT_5.md` — готов к передаче разработчику.**

| TASK | BUG | Fix | Оценка |
|------|-----|-----|--------|
| **TASK-033** | BUG-066b | `_filter_url_over_email_finding` для `Finding` | 15 мин |
| **TASK-034** | BUG-067d | `image_region`/`ocr`/`bounding_box` | 20 мин |
| **TASK-036** | BUG-065 | credentials-паттерны (5 изменений) | 1-1.5 ч |
| **TASK-035** | BUG-069/070 | Фильтр spaCy noise | 30 мин |

**Оценка:** ~2.5 часа.

**После выполнения:** v3.13.14 → повторная верификация → **закрытие Блока 3** → **финал** (GitHub + релиз v3.0.0).
