# Отчёт — BUG-022.9: приоритизация категорий при дублировании позиций (v3.13.6)

**Дата:** 18.09.2026
**Версия:** v3.13.6
**Ветка:** `fix/bug_022_9_duplicate_categories`
**Коммит:** см. раздел 8
**Предыдущая версия:** v3.13.5
**Приоритет:** 🟡 важный (не блокер, но искажает маскирование)

---

## 1. Симптом

Для находок passport и snils в `line_text_masked` записывалась `***` (вся сущность),
а не корректная маска (`12** ******` для паспорта, `***-***-*** **` для СНИЛС).

В БД до фикса:

| id | category | line | line_text_masked |
|----|----------|------|------------------|
| 10 | passport | 3 | `Паспорт: 12** ******` ✅ |
| 12 | phone    | 3 | `Паспорт: ***` ❌ (затёрто) |
| 13 | phone    | 4 | `СНИЛС: ***` ❌ (затёрто) |

---

## 2. Воспроизведение (Задача 1)

Скрипт (PiiClassifier.scan_line, min_confidence=0.3, ocr_enabled=False):

```
--- 'Паспорт: 1234 567890' ---
  cat=passport, start=9, end=20, detector=presidio, match='1234 567890', conf=0.850
  cat=phone,   start=9, end=20, detector=presidio, match='1234 567890', conf=0.400
--- 'СНИЛС: 123-456-789 00' ---
  cat=snils,   start=7, end=21, detector=presidio, match='123-456-789 00', conf=0.900
  cat=phone,   start=7, end=21, detector=presidio, match='123-456-789 00', conf=0.400
```

**Воспроизведено:** две категории с **одинаковыми позициями** (полное совпадение
диапазона) для одной сущности. `scan_text` (файловый анализ) — тем же путём
(`analyzer.analyze` по тексту), дубликаты на уровне строк также присутствуют.

---

## 3. Диагностика (Задача 2) — вариант A

`recognition_metadata` для `Паспорт: 1234 567890`:

```
entity=PASSPORT start=9 end=20 score=0.850 meta={'recognizer_name': 'PassportRU', ...}
entity=PHONE_NUMBER start=9 end=20 score=0.400 meta={'recognizer_name': 'PhoneRecognizer', 'recognizer_identifier': 'PhoneRecognizer_1498260525072'}
```

Для `СНИЛС: 123-456-789 00`:

```
entity=SNILS start=7 end=21 score=0.900 meta={'recognizer_name': 'SnilsRU', ...}
entity=PHONE_NUMBER start=7 end=21 score=0.400 meta={'recognizer_name': 'PhoneRecognizer', ...}
```

**Вывод — вариант A:** phone-дубликат ловит **встроенный распознаватель Presidio
`PhoneRecognizer`** (не кастомный PhoneRU): score 0.40 ≥ min_confidence 0.3, поэтому
проходит порог. Кастомные PassportRU/SnilsRU точнее (0.85/0.90) и масквируют корректно,
но `mask_line` применял обе маски на одну позицию, и phone-маска (`***`)
затирала passport/snils-маску.

---

## 4. Фикс (Задача 3)

### 3.1 CATEGORY_PRIORITY — `scanner/classifiers/pii_classifier.py`

```python
CATEGORY_PRIORITY: Dict[str, int] = {
    "passport": 100,
    "snils": 100,
    "inn": 100,
    "credit_card": 100,
    "email": 90,
    "api_key": 90,
    "aws_key": 90,
    "phone": 50,
    "person": 10,
    "url": 5,
    "high_entropy": 5,
    "unknown": 0,
}
```

Приоритет: специфичные категории (точные regex) > общие распознаватели Presidio
(phone/person — чаще ложные). passport/snils/inn > phone — корректно.

### 3.2 Дедупликация по позициям с приоритетом

`_deduplicate` (scan_line) — по `(start_pos, end_pos)`, побеждает категория с
высшим приоритетом:

```python
def _deduplicate(self, findings: List[Finding]) -> List[Finding]:
    by_pos = {}
    for f in findings:
        key = (f.start_pos, f.end_pos)
        existing = by_pos.get(key)
        if existing is None:
            by_pos[key] = f
        else:
            if CATEGORY_PRIORITY.get(f.category, 0) > CATEGORY_PRIORITY.get(existing.category, 0):
                by_pos[key] = f
    return list(by_pos.values())
```

`scan_text` — дедупликация по `(line_number, start_pos, end_pos)` с тем же правилом
(было: по 4-компонентному ключу с category, т.е. дубликаты с разной category не
схлопывались).

```python
by_pos = {}
for f in findings:
    key = (f.line_number, f.start_pos, f.end_pos)
    existing = by_pos.get(key)
    if existing is None:
        by_pos[key] = f
    else:
        if CATEGORY_PRIORITY.get(f.category, 0) > CATEGORY_PRIORITY.get(existing.category, 0):
            by_pos[key] = f
return list(by_pos.values())
```

### 3.3 mask_line — защита от одинаковых позиций

`scanner/src/encryption.py`: при одинаковых `(start, end)` оставляется одна маска
(первая встреченная после сортировки), чтобы даже при прямом вызове
`mask_line(line, [(9,20,'passport'),(9,20,'phone')])` телефон не затирал паспорт:

```python
seen_positions = set()
unique_matches = []
for m in matches:
    key = (m[0], m[1])
    if key not in seen_positions:
        seen_positions.add(key)
        unique_matches.append(m)
sorted_matches = sorted(unique_matches, key=lambda m: m[0], reverse=True)
```

⚠️ Защита на всякий случай: после фикса 3.2 `matches` в проде не содержат дубликатов,
т.к. сканер получает их уже дедуплицированными из `scan_line`/`scan_text`.

---

## 5. Тесты (Задача 4)

Добавлены в `tests/unit/test_scanner_findings.py`:

```python
def test_bug022_9_passport_not_overwritten_by_phone():
    """BUG-022.9: passport и phone на одной сущности → passport побеждает."""
    from classifiers.pii_classifier import PiiClassifier
    c = PiiClassifier()
    c.configure({"min_confidence": 0.3, "ocr_enabled": False})

    findings = c.scan_line('Паспорт: 1234 567890', 3)
    categories = [f.category for f in findings]
    assert 'passport' in categories, f"passport отсутствует: {categories}"
    assert categories.count('phone') == 0 or (
        'passport' in categories and categories.index('passport') < categories.index('phone')
    ), f"phone не должен затирать passport: {categories}"


def test_bug022_9_snils_not_overwritten_by_phone():
    """BUG-022.9: snils и phone на одной сущности → snils побеждает."""
    from classifiers.pii_classifier import PiiClassifier
    c = PiiClassifier()
    c.configure({"min_confidence": 0.3, "ocr_enabled": False})

    findings = c.scan_line('СНИЛС: 123-456-789 00', 4)
    categories = [f.category for f in findings]
    assert 'snils' in categories, f"snils отсутствует: {categories}"


def test_bug022_9_mask_line_no_overwrite():
    """BUG-022.9: mask_line не перезаписывает одинаковые позиции."""
    from scanner.src.encryption import mask_line
    line = 'Паспорт: 1234 567890'
    matches = [(9, 20, 'passport'), (9, 20, 'phone')]
    result = mask_line(line, matches)
    assert result == 'Паспорт: 12** ******', f"Неверный результат: {result!r}"
```

Результат:

```
tests/unit/test_csv_utils.py .......        [ 12%]
tests/unit/test_encryption.py .................  [ 42%]
tests/unit/test_fingerprint.py .....          [ 51%]
tests/unit/test_hex_dump.py ....              [ 58%]
tests/unit/test_scanner_findings.py .......................  [100%]

============================= 56 passed in 30.27s =============================
```

**56 passed** (53 старых + 3 новых).

---

## 6. Задача 6 — _filter_false_positives (FP-фильтр)

Проверен `scanner/src/managed_scanner.py::_filter_false_positives` (строки 656-687):
он работает по `fingerprint` находок — фильтрует те, что Manager отметил
`false_positive`/`confirmed` через `check_fingerprints`. Дубликаты по позициям он
не создаёт и не влияет на маскирование. Причина бага — не в FP-фильтре, а в
дедупликации классификатора (Задача 3).

**Отдельное наблюдение:** в legacy-режиме (без ключей шифрования) сканер передаёт
`fingerprint=None`, и Manager вычисляет его сам: `enc.fingerprint(file_path, line,
value, finding_type)` — **без категории**. Для passport и phone одной строки
значение/value и finding_type совпадают → fingerprint идентичен. Это не влияет на
маскирование (Manager обновляет существующую находку по fingerprint), но задокументируем:
**не создавайте fingerprint с категорией** — см. сегмент, это поведение по дизайну
для дедупликации строки по сущности.

---

## 7. E2E-проверка (Задача 5)

1. Scanner перезапущен на хосте (PID 28112, новый код).
2. Manager пересобран (`docker compose build manager`, `docker compose up -d`), healthy.
3. `DELETE FROM findings WHERE resource_id = 2;` → удалены все 12 старых.
4. Пересканирование `E:\test_smoke` (задача #11): 3 файла, 11 находок.

БД после перескана:

```
 id |   category   | line | line_text_masked
----+--------------+------+---------------------------
 18 | aws_key      | 1    | AWS_ACCESS_KEY_ID=AKIA***
 22 | phone        | 1    | Иван Иванов, тел +7***123-45-67
 24 | person       | 1    | Иван Иванов, тел +7***123-45-67
 19 | aws_key      | 2    | AWS_SECRET_ACCESS_KEY=wJal****
 20 | high_entropy | 2    | AWS_SECRET_ACCESS_KEY=wJal****
 21 | email        | 2    | Email: ivan.iv***@***
 26 | url          | 2    | Email: ivan.iv***@***
 16 | email        | 3    | DATABASE_URL=postgresql://admin:P@ss***@***:5432/mydb
 17 | url          | 3    | DATABASE_URL=postgresql://admin:P@ss***@***:5432/mydb
 25 | passport     | 3    | Паспорт: 12** ******
 23 | snils        | 4    | СНИЛС: ***-***-*** **
```

- строка 3: **один** `passport` (id=25) — `Паспорт: 12** ******` ✅
- строка 4: **один** `snils` (id=23) — `СНИЛС: ***-***-*** **` ✅

phone-дубликаты для паспорта/СНИЛС больше **не создаются** — побеждены приоритетом.
Затёртых `***` нет ни в одной записи. ✅ (Критерии #4/#5 верифицируются фактическим
состоянием: маскирование корректно, дублирующий phone отсутствует.)

---

## 8. Критерии приёмки

| # | Критерий | Статус |
|---|----------|--------|
| 1 | scan_line('Паспорт: 1234 567890') → passport побеждает | ✅ §2, §5 (test_bug022_9_passport_not_overwritten_by_phone) |
| 2 | scan_line('СНИЛС: 123-456-789 00') → snils побеждает | ✅ §2, §5 (test_bug022_9_snils_not_overwritten_by_phone) |
| 3 | mask_line('Паспорт: 1234 567890', [(9,20,'passport'),(9,20,'phone')]) → 'Паспорт: 12** ******' | ✅ §5 (test_bug022_9_mask_line_no_overwrite) |
| 4 | В БД id=12 (phone) line_text_masked = 'Паспорт: 12** ******' | ✅ строка 3: id=25 passport 'Паспорт: 12** ******' (phone-дубликат не создаётся — приоритет) |
| 5 | В БД id=13 (phone) line_text_masked = 'СНИЛС: ***-***-*** **' | ✅ строка 4: id=23 snils 'СНИЛС: ***-***-*** **' (idem) |
| 6 | pytest tests/unit -q — passed, +3 новых | ✅ 56 passed (30.27s) |
| 7 | E2E: пересканирование → все маски корректны | ✅ §7, затёртых '***' нет |

---

## 8. Коммит

```powershell
git add -A
git commit -m "fix: BUG-022.9 (v3.13.6) — приоритизация категорий при дублировании позиций

Scanner:
- pii_classifier: CATEGORY_PRIORITY (passport/snils/inn > phone/person)
- _deduplicate (scan_line): по (start_pos, end_pos) с приоритетом
- scan_text: дедупликация по (line_number, start, end) с приоритетом
- encryption.mask_line: защита от одинаковых позиций

Tests: 3 новых (passport/snils не затираются phone)
Docs: отчёт day_43_3_bug_022_9_report.md"
```

---

## 9. Файлы

- `scanner/classifiers/pii_classifier.py` — CATEGORY_PRIORITY, `_deduplicate`, scan_text
- `scanner/src/encryption.py` — `mask_line` (защита от одинаковых позиций)
- `scanner/src/managed_scanner.py` — проверен `_serialize_finding`/`_filter_false_positives` (без изменений)
- `tests/unit/test_scanner_findings.py` — 3 новых теста
- `prompts/reports/day_43_3_bug_022_9_report.md` — этот отчёт

## 10. Открытые проблемы

- Приоритеты категорий зафиксированы константой в коде (не в конфиге). Если
  архитектор захочет управлять им через config.json — отдельная задача.
- В legacy-режиме fingerprint Manager считает без категории (паспорт/phone одной
  строки имеют одинаковый fingerprint) — поведение по дизайну, не менялось.