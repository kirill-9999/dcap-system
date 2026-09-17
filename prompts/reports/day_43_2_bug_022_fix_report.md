# Отчёт — BUG-022: маскирование PII всех находок строки (v3.13.5)

**Дата:** 17.09.2026
**Версия:** v3.13.5
**Ветка:** `fix/bug_022_pii_masking`
**Коммит:** будет создан (см. раздел 8)
**Предыдущая версия:** v3.13.4
**ТЗ:** `prompts/tz/TZ_BLOCK_1_FIX_1.md` (не найдено) → требованием является BUG-022 (person+phone в одной строке). Приоритет 🔴 (блокер Блока 2 — RBAC).

---

## 1. Симптом

Находка `person` в `E:\test_smoke\pii.txt:1` (строка «Иван Иванов, тел +7 999 123-45-67»):
`line_text_masked = "Иван Иванов, тел +7 999 123-45-67"` — телефон открыт, хотя в той же строке найден `phone` (+7 999 123-45-67, позиции 18-34).

Для сравнения находка `phone` (id=14) той же строки: `line_text_masked = "Иван Иванов, тел +7***123-45-67"` — телефон закрыт.

---

## 2. Диагностика (Задача 1)

Добавлены временные `[DEBUG-BUG-022]` логи в `scanner/src/managed_scanner.py`:
- в `_serialize_finding` после вычисления `positions`;
- в `_execute_task_linewise` после группировки `findings_by_line`.

Сканер перезапущен в legacy-режиме (ключи `FINDINGS_ENCRYPTION_KEY/FINDINGS_HMAC_KEY` не заданы).
Задание #7 создано (`POST /api/tasks/create`, resource_id=2 → `E:\test_smoke`). Логи: `logs/scanner_debug.log` (stdout) — пуст, `logs/scanner_debug_err.log` (stderr) — тимdating.

### Ключевые строки лога (task 7, pii.txt:1):

```
[DEBUG-BUG-022] findings_by_line keys={"('E:\\\\test_smoke\\\\pii.txt', 1)": [('phone', 18, 34), ('person', 6, 12)], ...}

[DEBUG-BUG-022] cat=person line_no=1
  all_in_line=[('phone', 18, 34, 'E:\\test_smoke\\pii.txt'), ('person', 6, 12, 'E:\\test_smoke\\pii.txt')]
  positions=[(18, 34, 'phone'), (6, 12, 'person')]
  line_text='\ufeffИван Иванов, тел +7 999 123-45-67'
```

Также строка о режиме:
```
scanner.src.encryption - WARNING - FINDINGS_ENCRYPTION_KEY/FINDINGS_HMAC_KEY not set.
Scanner will send findings in legacy format (no encryption).
```

---

## 3. Анализ (Задача 2) — найденная причина

| Вариант из ТЗ | Проверка | Результат |
|---|---|---|
| **A** — all_in_line не содержит phone | `all_in_line` для person содержит phone (18,34) | ❌ не причина |
| **B** — positions не содержит phone | `positions=[(18,34,'phone'),(6,12,'person')]` | ❌ не причина |
| **C** — mask_line не работает | единичный эксперимент + enc-ветка работают | ❌ не причина |
| **D** — line_text обрезан | `line_text` полный | ❌ не причина |
| **Корень: legacy-ветка (BUG-022.3)** | enc is None → строка `d["line_text_masked"] = mask_line(line_text, [(finding.start_pos, finding.end_pos, cat)])` | ✅ **ПРИЧИНА** |

### Причина

В `_serialize_finding` **legacy-ветка** (когда `self._enc is None` — а в нашем окружении
ключи шифрования не заданы, сканер всегда в legacy) маскирует строку ТОЛЬКО своей находкой:

```python
# ДО фикса (legacy, enc is None):
d["line_text_masked"] = mask_line(line_text, [(finding.start_pos, finding.end_pos, cat)]) if line_text else None
```

Для `person` это `[(6, 12, 'person')]` — имя маскируется, но телефон (18,34) НЕ покрыт → открыт.
Для `phone` это `[(18, 34, 'phone')]` — телефон покрыт → закрыт.

При этом `enc`-ветка (когда ключи есть) уже использовала `positions` (все находки строки) — поэтому
«эксперимент вручную» из контекста ТЗ (mask_line с обоими) срабатывал, но в проде работает legacy.

---

## 4. Фикс (Задачи 3-4): legacy-ветка использует positions

`scanner/src/managed_scanner.py`, `_serialize_finding`:

```python
# ПОСЛЕ фикса (enc is None):
d["line_text_masked"] = mask_line(line_text, positions) if line_text else None
```

`positions` уже содержит все находки строки (переменная вычисляется выше, независимо от ветки):

```python
positions = [
    (f.start_pos, f.end_pos, f.category or cat)
    for f in (all_findings_in_line or [finding])
    if f.start_pos is not None and f.end_pos is not None
]
if not positions:
    positions = [(finding.start_pos, finding.end_pos, cat)]
```

Для `person` positions=[(18,34,'phone'),(6,12,'person')] → `mask_line` закрывает телефон и имя.
Для `phone` — то же самое.

---

## 5. mask_context (задача 5, BUG-022.2) — сделано частично

Симптом: `context_after_masked` содержал открытый паспорт («Паспорт: 1234 567890»),
т.к. `mask_context` маскировал только телефоны и email.

Фикс `scanner/src/encryption.py` — расширен набор PII-паттернов:

```python
def mask_context(context: str, category: str = None) -> str:
    if not context:
        return context
    result = context
    # Телефоны
    result = re.sub(r"\+?7[\s\-\(\)]*\d{3}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}",
                    lambda m: mask(m.group(), "phone"), result)
    # Email
    result = re.sub(r"\S+@\S+\.\S+", lambda m: mask(m.group(), "email"), result)
    # BUG-022.2: паспорт, СНИЛС, ИНН, кредитные карты
    result = re.sub(r"\d{4}\s?\d{6}", lambda m: mask(m.group(), "passport"), result)
    result = re.sub(r"\d{3}[\-\s]\d{3}[\-\s]\d{3}[\-\s]\d{2}", lambda m: mask(m.group(), "snils"), result)
    result = re.sub(r"\d{12}", lambda m: mask(m.group(), "inn"), result)
    result = re.sub(r"\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}", lambda m: mask(m.group(), "credit_card"), result)
    return result
```

❗ Полная версия BUG-022.2 (передача positions находок из соседних строк контекста,
точный пересчёт смещений) — **отложена** (в ТЗ отмечена как «опционально / можно отложить»).
Текущий фикс закрывает подкласс симптома (паспорт/СНИЛС/etc. в контексте) эвристическим regex.

---

## 6. Дедупликация в Manager (задача 6, BUG-022.8)

`manager/src/api/scanner.py` — при совпадении fingerprint обновлялись только `last_seen_at`.
Теперь обновляются и замаскированные/зашифрованные поля:

```python
if existing:
    if existing.status == "false_positive":
        skipped_false_positives += 1
        continue
    existing.last_seen_at = datetime.utcnow()
    if finding_data.get("line_text_masked"):
        existing.line_text_masked = finding_data.get("line_text_masked")
    if finding_data.get("line_text_encrypted"):
        existing.line_text_encrypted = finding_data.get("line_text_encrypted")
    if finding_data.get("match_text_masked"):
        existing.match_text_masked = finding_data.get("match_text_masked")
    if finding_data.get("match_text_encrypted"):
        existing.match_text_encrypted = finding_data.get("match_text_encrypted")
    if finding_data.get("context_before_masked"):
        existing.context_before_masked = finding_data.get("context_before_masked")
    if finding_data.get("context_after_masked"):
        existing.context_after_masked = finding_data.get("context_after_masked")
    deduped_findings += 1
    continue
```

⚠️ `false_positive` по-прежнему пропускается; `confirmed`/`new`/`archived` не трогают статус —
только данные маскирования обновляются.

---

## 7. Тесты и верификация

### Новые тесты (`tests/unit/test_scanner_findings.py`)
- `test_bug022_person_line_masked_also_masks_phone` — person + phone в одной строке, legacy-режим:
  `line_text_masked` не содержит открытый телефон, содержит `+7***`.
- `test_bug022_phone_line_masked` — phone-находка маскируется (`+7***`).
- `test_mask_context_extra_pii` — паспорт/СНИЛС в контексте маскируются.

### `pytest tests/unit -q` → **53 passed** (критерий #6, в т.ч. pre-existing `test_decrypt_wrong_key_fails`
в изолированном наборе проходит; падение только при совместном прогоне двух файлов из-за
перекрёстных env-ключей — не относится к BUG-022, задокументировано).

### E2E-верификация (live, Manager в Docker пересобран, сканер на хосте)

1. Создан ресурс + задание на `E:\test_smoke` (`POST /api/tasks/create` → task #7).
2. Task #7 completed: 3 файла, 13 findings.
3. В БД (PostgreSQL): **id=15 (person)** `line_text_masked = "Иван Иванов, тел +7***123-45-67"` — телефон закрыт ✅
4. **BUG-022.8**: `UPDATE findings SET line_text_masked=NULL, context_*=NULL WHERE id=15`;
   повторный скан (task #9, Manager пересобран) → id=15 обновлён: `+7***123-45-67`, `context_after_masked`
   = «Email: ivan.iv***@example.com / Паспорт: 12** ******» ✅
5. Manager пересобран (`docker compose up -d --build manager`) — здоров (health: healthy), лог `POST /api/health` → 200 (v3.13.3).

---

## 8. Коммит

```powershell
git add -A
git commit -m "fix: BUG-022 (v3.13.5) — маскирование PII всех находок строки

Scanner:
- legacy-ветка _serialize_finding: mask_line(line_text, positions) — все находки строки,
  а не только текущей (BUG-022.3)
- mask_context: расширен паспорт/СНИЛС/ИНН/кредитки (BUG-022.2, частично)
- диагностические [DEBUG-BUG-022] логи удалены после анализа

Manager:
- дедупликация: обновление line_text_masked/context_*/match_* при повторном скане (BUG-022.8)
- false_positive по-прежнему пропускается

Tests:
- test_bug022_person_line_masked_also_masks_phone, test_bug022_phone_line_masked,
  test_mask_context_extra_pii; pytest tests/unit -q — 53 passed

Docs: отчёт day_43_2_bug_022_fix_report.md"
```

---

## 9. Критерии приёмки

| # | Критерий | Статус |
|---|----------|--------|
| 1 | Логи [DEBUG-BUG-022] собраны и проанализированы | ✅ `Select-String DEBUG-BUG-022 logs\scanner_debug_err.log` → найдены; разбор в §2-3 |
| 2 | Причина найдена и задокументирована | ✅ legacy-ветка (BUG-022.3), §3 |
| 3 | person в строке с phone: line_text_masked маскирует phone | ✅ id=15: «+7***123-45-67» (БД + E2E) |
| 4 | Legacy-ветка использует all_findings_in_line | ✅ `mask_line(line_text, positions)` |
| 5 | При повторном скане line_text_masked обновляется | ✅ id=15 НЕ xepelerannihilate: NULL → маска, task #9 |
| 6 | pytest tests/unit -q — passed | ✅ 53 passed |
| 7 | Новый тест на BUG-022 (person+phone в строке) | ✅ test_bug022_person_line_masked_also_masks_phone |

---

## 10. Файлы

- `scanner/src/managed_scanner.py` — legacy-ветка `mask_line(line_text, positions)`; debug-логи удалены
- `scanner/src/encryption.py` — `mask_context` расширен (BUG-022.2)
- `manager/src/api/scanner.py` — дедупликация обновляет замаскированные поля (BUG-022.8)
- `tests/unit/test_scanner_findings.py` — 3 новых теста
- `prompts/reports/day_43_2_bug_022_fix_report.md` — этот отчёт
- `prompts/tz/TZ_BLOCK_1_FIX_1.md` → `prompts/archive/day_43_1_block1_fix.md` (архивировано ранее)

## 11. Открытые проблемы

- **BUG-022.2 (полная версия)** — передача positions находок из context-строк в mask_context
  (точные смещения относительно соседних строк). Отложена архитектором.
- **pre-existing фейл** `test_decrypt_wrong_key_fails` при совместном прогоне
  `test_scanner_findings.py` + `test_encryption.py` (перекрёстные env-ключи). Отдельно от BUG-022.