# 🔧 ТЗ №4: Fix-спринт №4 — Scanner deep (v3.13.13)

**Дата:** 21.09.2026
**Версия:** v3.13.12 → **v3.13.13**
**Ветка:** `fix/scanner_deep_4`
**Приоритет:** 🔴 важно (блокеры v3.0.0: BUG-063, 067)
**Источник:** верификация ТЗ №3 (v3.13.12), `STATE_TEST_SESSION.md` (Блок 3)
**Предыдущее ТЗ:** `TZ_FIX_SPRINT_3.md` — **выполнено частично** (4 из 6 багов не закрыты)
**Оценка:** ~2.5 часа

---

## 🎯 Контекст

**По итогам верификации ТЗ №3 (v3.13.12) выявлено 4 нерешённых бага:**

| ID | Название | Статус |
|----|----------|--------|
| **BUG-063** | `credit_card` не детектируется (`language="ru"`) | 🔴 **открыт** |
| **BUG-065** | `database_url`/`github_token`/`slack_token`/`basic_auth` не детектируются | 🟡 **открыт** |
| **BUG-066** | `url`-дубликаты email (602 URL) | 🔴 **открыт** |
| **BUG-067c** | OCR для изображений (`ocr_enabled` не из той секции) | 🔴 **открыт** |

**BUG-061, 062 — ✅ (не проверены live, но код корректен).**

**Что работает (не трогать):**
- Prefilter `_quick_line_patterns` — ✅ `credit_card` pattern добавлен.
- Luhn-фильтр — ✅ (`_filter_credit_cards_by_luhn` использует `f.value`).
- Маппинг `CREDIT_CARD → credit_card` — ✅.
- Маскирование — ✅.
- PII-детекция (email, phone, passport, snils, inn) — ✅.

---

## 📋 Задачи

### TASK-029 — BUG-067c: `ocr_enabled` из правильной секции

**Приоритет:** 🔴 **критично**

**Компонент:** `scanner/connectors/filesystem.py::_extract_document`

**Проблема:**

```python
# scanner/connectors/filesystem.py::_extract_document
extractor = DocumentExtractor(
    temp_dir=Path(_tf.gettempdir()),
    ocr_enabled=self.config.get("ocr_enabled", False),   # ← 🔴
)
self.config в FilesystemConnector — это секция connector из scanner_config.json.

В connector — НЕТ ключа ocr_enabled → self.config.get("ocr_enabled", False) → False.

OCR выключен, хотя в classifiers.pii_classifier.ocr_enabled = true.

→ 0 findings с detector=ocr (проверено на screenshot.png).

Fix (Вариант A — правильный):

В managed_scanner.py::_init_line_pipeline:

python
def _init_line_pipeline(self) -> bool:
    ...
    connector_cfg = self._get_connector_config()
    # BUG-067c: ocr_enabled из classifiers.pii_classifier (а не connector)
    if self.config and self.config.classifiers and self.config.classifiers.pii:
        connector_cfg["ocr_enabled"] = bool(self.config.classifiers.pii.ocr_enabled)
    else:
        connector_cfg["ocr_enabled"] = True
    self._connector = FilesystemConnector(connector_cfg)
    ...
В _get_connector_config — добавить дефолт:

python
def _get_connector_config(self) -> Dict[str, Any]:
    if self.config and self.config.connector:
        cfg = {
            ...
            "ocr_enabled": True,   # ← будет переопределено в _init_line_pipeline
        }
        return cfg
    return {...}
Fix (Вариант B — минимальный):

В filesystem.py::_extract_document:

python
extractor = DocumentExtractor(
    temp_dir=Path(_tf.gettempdir()),
    ocr_enabled=self.config.get("ocr_enabled", True),   # ← default=True
)
Fix (Вариант C — радикальный):

python
ocr_enabled=True,   # всегда
Рекомендую Вариант A — архитектурно правильно.

Тесты:

test_scan_image_with_ocr_enabled — PNG с email → finding image_region, detector=ocr.

test_scan_image_with_ocr_disabled — при ocr_enabled=False → 0 findings.

Verify (ручной):

Создать screenshot.png с email/phone.

Запустить скан scanner_deep.

Ожидаем: findings с fragment_type=image_region, detector=ocr, bounding_box.

Оценка: 15 мин.

TASK-030 — BUG-063: language="ru" → двухпроходный (ru + en)
Приоритет: 🔴 важно

Компонент: scanner/classifiers/pii_classifier.py

Проблема:

python
# scan_line (L~300)
results = analyzer.analyze(text=line, language="ru")   # ← 🔴

# scan_text (L~430)
results = analyzer.analyze(text=text, language="ru")   # ← 🔴

# classify (L~800)
results = self._analyzer.analyze(text=text, language="ru")   # ← 🔴
Presidio CREDIT_CARD — только для en. С language="ru" — не находит. Проверено:

python
analyzer.analyze(text='Card 1: 4111 1111 1111 1111', language='en')
# → [('CREDIT_CARD', 1.0)]

analyzer.analyze(text='Card 1: 4111 1111 1111 1111', language='ru')
# → [] (без CREDIT_CARD)
Также language="ru" теряет:

US_BANK_NUMBER, US_DRIVER_LICENSE, US_PASSPORT, US_SSN.

IP_ADDRESS (частично).

URL (частично).

Fix — двухпроходный анализ:

В scan_text:

python
if analyzer is not None:
    try:
        with analyzer_lock:
            results_ru = analyzer.analyze(text=text, language="ru")
            results_en = analyzer.analyze(text=text, language="en")
        results = list({
            (r.entity_type, r.start, r.end): r
            for r in (results_ru + results_en)
        }.values())
        
        min_confidence = self.config.get("min_confidence", 0.5)
        for r in results:
            ...
Аналогично в scan_line и classify.

Плюс — регистрация кастомных распознавателей для en:

В _add_custom_recognizers — добавить дубликаты с supported_language="en":

python
phone_recognizer_en = PatternRecognizer(
    supported_entity="PHONE_NUMBER",
    name="PhoneEN",   # имя должно быть другим
    patterns=phone_patterns,
    supported_language="en"
)
analyzer.registry.add_recognizer(phone_recognizer_en)
# ... аналогично для Passport, Snils, Inn, Email
⚠️ Важно: при analyzer.analyze(text, language="en") распознаватели с supported_language="ru" не срабатывают. И наоборот.

Тесты:

test_credit_card_language_en — 4111 1111 1111 1111 → finding credit_card.

test_credit_card_language_ru — не находит (подтверждение).

test_phone_ru_and_en — работает для обоих языков.

test_email_ru_and_en — работает.

Verify (ручной):

cards.txt → credit_card × 2 (после fix).

Оценка: 30 мин.

TASK-031 — BUG-066: _filter_url_over_email — неправильные поля
Приоритет: 🔴 важно

Компонент: scanner/classifiers/pii_classifier.py::_filter_url_over_email

Проблема:

python
def _filter_url_over_email(self, findings: List[ClassificationFinding]) -> List[ClassificationFinding]:
    email_spans = {
        (f.start_pos, f.end_pos)                    # ← 🔴
        for f in findings
        if f.subcategory in ("PII_EMAIL", "email")
    }
    ...
    for f in findings:
        if f.subcategory in ("PII_URL", "url"):
            if any(
                email_start <= f.start_pos < f.end_pos <= email_end    # ← 🔴
                for email_start, email_end in email_spans
            ):
                continue
ClassificationFinding (scanner/core/base.py):

python
@dataclass
class ClassificationFinding:
    category: DataCategory
    subcategory: str
    value: str
    position: int              # ← только `position`
    context: str
    confidence: float
    detection_method: str
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
f.start_pos — AttributeError. f.end_pos — AttributeError. Ошибка проглатывается общим try/except → фильтр не работает → 602 url-дубликатов в БД.

Fix:

python
def _filter_url_over_email(self, findings: List[ClassificationFinding]) -> List[ClassificationFinding]:
    """BUG-066 (день 46.3): url с email-доменом — отбрасываем url.

    Presidio распознаёт в адресе `user@example.com` и EMAIL_ADDRESS,
    и URL (домен `example.com`). URL-находка — дубликат email-домена:
    отбрасываем её, чтобы не плодить ложные дубли.
    """
    # BUG-066 fix: ClassificationFinding имеет `position` + `len(value)`,
    # НЕ `start_pos`/`end_pos`.
    email_spans = {
        (f.position, f.position + len(f.value))
        for f in findings
        if f.subcategory in ("PII_EMAIL", "email")
    }
    if not email_spans:
        return findings

    filtered = []
    for f in findings:
        if f.subcategory in ("PII_URL", "url"):
            f_start = f.position
            f_end = f.position + len(f.value)
            # url внутри email-спана (домен внутри адреса)?
            if any(e_start <= f_start and f_end <= e_end for e_start, e_end in email_spans):
                continue
        filtered.append(f)
    return filtered
Дополнительно — очистка старых 602 url findings:

SQL-скрипт (в scripts/cleanup_url_over_email.py):

sql
DELETE FROM findings
WHERE category = 'url'
  AND EXISTS (
    SELECT 1 FROM findings e
    WHERE e.category = 'email'
      AND e.fragment_path = findings.fragment_path
      AND e.line_number = findings.line_number
  );
Или — не удалять, оставить как исторические (TEST-NOTE).

Тесты:

test_url_not_duplicated_by_email — email + domain → только email.

test_url_standalone — https://example.com (без email) → url finding.

Verify (ручной):

emails.txt → SELECT COUNT(*) ... WHERE category = 'url' → 0.

Оценка: 10 мин + SQL-скрипт (опционально).

TASK-032 — BUG-065: credentials-паттерны
Приоритет: 🟡 важно

Компонент: scanner/classifiers/credentials_classifier.py

Проблема (по результатам scan_line):

Строка	Regex matches?	Finding?	Причина
DATABASE_URL=postgresql://...	✅	🔴 Нет	_is_placeholder('...password123...') = True
BASIC_AUTH=Basic ...	❌	🔴 Нет	regex требует Authorization:
GITHUB_TOKEN=ghp_...	✅	⚠️ high_entropy	_is_placeholder('ghp_1234567890...') = True (matches [0-9x]{8,})
SLACK_TOKEN=xoxb-...	❌	⚠️ high_entropy	regex требует 3 группы
Fix — три изменения:

1. _apply_filters: не отбрасывать signature-prefix
python
def _apply_filters(self, value: str, line: str) -> bool:
    """Применение всех FP-фильтров к найденному значению."""
    
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
2. _is_placeholder: убрать [0-9x]{8,} (слишком агрессивен)
python
PLACEHOLDER_PATTERNS = [
    r'your_[a-z_]+',
    r'example_[a-z_]+',
    r'changeme',
    r'<[A-Z_]+>',
    r'{{[A-Z_]+}}',
    r'xxx+',
    # r'[0-9x]{8,}',           # ← УБРАТЬ — отбрасывает ghp_/xoxb_/AKIA
    r'NNN[_-]?[A-Z]+',
    r'^password[0-9]{1,2}$',    # ← уточнить: только ПОЛНОЕ совпадение
    r'^admin[0-9]{1,2}$',
    r'^test[_-]?[a-z0-9]+$',
    r'^sample[_-]?[a-z0-9]+$',
    r'^demo[_-]?[a-z0-9]+$',
    r'example\.com',
    r'changeme\.com',
]
3. Regex BASIC_AUTH и SLACK_TOKEN
В _get_default_patterns:

python
# Было:
{"name": "BASIC_AUTH", "pattern": r'Authorization:\s*Basic\s+[A-Za-z0-9+/=]+', ...},
{"name": "SLACK_TOKEN", "pattern": r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}', ...},

# Стало:
{"name": "BASIC_AUTH", "pattern": r'\bBasic\s+[A-Za-z0-9+/=]{10,}', "confidence": 0.8, "check_entropy": False},
{"name": "SLACK_TOKEN", "pattern": r'xox[baprs]-[A-Za-z0-9-]{10,}', "confidence": 0.85, "check_entropy": False},
4. _is_placeholder — не проверять URL
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
TASK-029	BUG-067c: OCR для изображений	🔴	15 мин
TASK-030	BUG-063: language="ru" → двухпроходный	🔴	30 мин
TASK-031	BUG-066: _filter_url_over_email	🔴	10 мин
TASK-032	BUG-065: credentials-паттерны	🟡	1-1.5 ч
Итого: ~2-2.5 часа.

🚦 Порядок выполнения
TASK-029 (BUG-067c) — 15 мин, критично для OCR.

TASK-030 (BUG-063) — 30 мин, критично для credit_card.

TASK-031 (BUG-066) — 10 мин, чистит findings.

TASK-032 (BUG-065) — 1-1.5 ч, полный fix credentials.

✅ Критерии приёмки
□ screenshot.png → findings fragment_type=image_region, detector=ocr (BUG-067c).
□ cards.txt → findings category=credit_card × 2 (BUG-063).
□ emails.txt → SELECT COUNT(*) FILTER (WHERE category='url') = 0 (BUG-066).
□ database.env → findings database_url, basic_auth, github_token, slack_token (BUG-065).
□ Unit-тесты — зелёные.
□ /api/health → 3.13.13.
📌 Коммиты
text
fix: BUG-067c — ocr_enabled из classifiers.pii_classifier (v3.13.13)
fix: BUG-063 — language="ru" → двухпроходный ru+en анализ (v3.13.13)
fix: BUG-066 — _filter_url_over_email использует position/len(value) (v3.13.13)
fix: BUG-065 — credentials-паттерны: BASIC_AUTH, SLACK_TOKEN, _is_placeholder (v3.13.13)
docs: CHANGELOG v3.13.13 — fix-спринт №4 (Scanner deep)
📚 Ссылки
scanner/connectors/filesystem.py — BUG-067c.

scanner/classifiers/pii_classifier.py — BUG-063, BUG-066.

scanner/classifiers/credentials_classifier.py — BUG-065.

scanner/core/base.py — ClassificationFinding (для BUG-066).

STATE_TEST_SESSION.md — Блок 3 (Scanner deep).

TZ_FIX_SPRINT_3.md — ТЗ №3 (выполнено частично).

🎯 Что после ТЗ №4
Verify — повторный скан scanner_deep → проверка 4 багов.

CHANGELOG v3.13.13.

STATE.md, ROADMAP.md — обновить.

GitHub публикация (BACKLOG-028/046).

Релиз v3.0.0.

Конец ТЗ №4. Приступай в порядке: TASK-029 → 030 → 031 → 032.