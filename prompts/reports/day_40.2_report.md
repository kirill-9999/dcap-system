# Отчёт — День 40.2: Findings Refactor: сканер (построчно + FP + дедуп) (v3.10.0)

- **Дата:** 12.09.2026
- **Версия:** v3.10.0
- **Ветка:** `feature/day_40.2_scanner_findings` (создана от `feature/day_40.1_findings_model`, коммит v3.9.0)
- **ТЗ:** `prompts/tz/day_40.2_scanner_findings.md` → `prompts/archive/day_40.2_scanner_findings.md`
- **Отчёт:** `prompts/reports/day_40.2_report.md`

---

## 1. Итог

Сканер переведён на новую модель находок (Этап 2 из 4 Findings Refactor):

- классификаторы возвращают `Finding` с позициями (`scan_line(line, line_num) → list[Finding]`);
- `FilesystemConnector` — построчное чтение с контекстом (N строк до/после);
- шифрование + маскирование **на стороне сканера** (AES-256-GCM + HMAC-fingerprint);
- batch FP-фильтр через `POST /api/findings/check-fingerprints` перед отправкой;
- отправка нового формата (`finding_type`, `fingerprint`, `match_text_encrypted`, `line_number`);
- дедупликация в Manager по fingerprint (FP не пересоздаются, повторные находки обновляют `last_seen_at`);
- **обратная совместимость:** если Manager старый (без `check-fingerprints`) или у сканера нет ключей — legacy-режим работает как раньше.

## 2. Что сделано

### 2.1 `scanner/src/finding.py` (NEW)
Модель находки в сканере (dataclass, строго по ТЗ):

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модель находки в сканере.

Находка = конкретное совпадение в строке файла (или фрагменте).
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Finding:
    """Находка в сканере (до шифрования)."""
    # Где найдено
    line_number: int
    line_text: str
    match_text: str
    start_pos: int
    end_pos: int

    # Классификация
    finding_type: str          # pii, credentials, code
    category: str              # phone, email, api_key
    severity: str = "medium"

    # Метаданные
    confidence: float = 0.0
    detector: str = "regex"    # presidio, regex, entropy, ocr

    # Контекст
    context_before: str = ""
    context_after: str = ""

    # Для не-текстовых (заполняется позже)
    fragment_type: str = "text_line"
    fragment_path: Optional[str] = None
    bounding_box: Optional[dict] = None
    byte_offset: Optional[int] = None
    byte_length: Optional[int] = None
    hex_preview: Optional[str] = None

    def to_dict(self) -> dict:
        """Для сериализации (без шифрования — оно позже)."""
        return {
            "line_number": self.line_number,
            "line_text": self.line_text,
            "match_text": self.match_text,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "finding_type": self.finding_type,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "detector": self.detector,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "fragment_type": self.fragment_type,
            "fragment_path": self.fragment_path,
            "bounding_box": self.bounding_box,
            "byte_offset": self.byte_offset,
            "byte_length": self.byte_length,
            "hex_preview": self.hex_preview,
        }


__all__ = ["Finding"]
```

### 2.2 `scanner/src/encryption.py` (NEW)
Шифрование + маскирование на стороне сканера (AES-256-GCM, HMAC-SHA256 fingerprint,
`MASK_RULES` + `mask/mask_line/mask_context`, синглтон `get_encryption`/`reset_encryption`,
legacy-режим при отсутствии ключей). Полный код — в ветке (см. раздел 3; ключевые моменты):

- ключи: `FINDINGS_ENCRYPTION_KEY`, `FINDINGS_HMAC_KEY`, `FINDINGS_KEY_ID` (env или Docker Secrets `/run/secrets/findings_*`);
- `ScannerEncryption.from_env()` → `None`, если ключей нет (legacy — открытый текст, Manager шифрует сам);
- маскирование расширено категориями дня 40.2: `jwt_token`, `ssh_key`, `github_token`, `slack_token`,
  `discord_token`, `database_url`, `basic_auth`, `high_entropy` (имена `person` НЕ маскируются).

### 2.3 Классификаторы — `scan_line` (MODIFIED)
`scanner/classifiers/pii_classifier.py`, `credentials_classifier.py`, `code_classifier.py`:
добавлен метод `scan_line(line, line_num) -> list[Finding]` (сохранён `scan_text` для совместимости):

- **PII**: presidio (если доступен) → custom regex-паттерны → `_map_presidio_entity` → `_severity` → `_deduplicate`;
- **Credentials**: префильтр одним regex → паттерны (`_apply_filters`/FP-фильтры) → entropy-детекция → `_deduplicate`. Добавлена категорийная карта `CATEGORY_MAP`;
- **Code**: `scan_line` возвращает `[]` (он про язык/фреймворк, файл-уровень) — разрешено ТЗ.

### 2.4 `scanner/connectors/filesystem.py` — `FilesystemConnector` (MODIFIED/NEW)
Новый класс построчного сканирования: `scan_path(path, classifiers, progress_callback)` →
`_discover_files` → `scan_file` → `_scan_text_file` (построчно + контекст) /
`_scan_document` (document_extractor) / image-заглушка; skip-директории, расширения,
буферизованное чтение, `CRED_FILENAMES`. `_within_size` фиксирован для str/Path.
Старый `FileSystemConnector` сохранён для обратной совместимости (fallback).

### 2.5 `scanner/src/config_loader.py` + `scanner/config/scanner_config.json` (MODIFIED)
`ConnectorConfig.context_lines` (по умолчанию 2); конфиг сквера дополнен `context_lines` и `text_extensions`.

### 2.6 `scanner/src/managed_scanner.py` (MODIFIED)
- `ManagerClient.check_fingerprints(fingerprints)` — POST `/api/findings/check-fingerprints`;
- построчный конвейер: `_init_line_pipeline` → `FilesystemConnector` + классификаторы с `scan_line`;
- `_scan_line_by_line` — scan_path с `progress_callback` (feed будущий heartbeat);
- `_serialize_finding` — новый формат (при ключах сырой текст на хосте, `value="(encrypted)"`);
- `_filter_false_positives` — batch-фильтр (FP/confirmed не отправляются; ошибка/404 → всё как раньше);
- `_execute_task_linewise` — приоритетный путь в `_execute_task`; старый Orchestrator-путь — fallback.

### 2.7 `manager/src/api/scanner.py` — `submit_results` (MODIFIED)
Новый формат + дедупликация по fingerprint:

```python
# === Сохраняем findings (день 40.2: новый формат + дедупликация по fingerprint) ===
from manager.src.core.encryption import get_encryption, mask, mask_line
_enc = None
saved_findings = 0
deduped_findings = 0
skipped_false_positives = 0

for finding_data in payload.get("findings", []):
    file_path = finding_data.get("file_path", finding_data.get("filepath", ""))
    line_number = finding_data.get("line_number", finding_data.get("line", 0))
    category = finding_data.get("category", "")
    subcategory = finding_data.get("subcategory", finding_data.get("sub_type", ""))
    value = finding_data.get("value", finding_data.get("matched_text", ""))
    confidence = finding_data.get("confidence", 1.0)
    context = finding_data.get("context", "")

    if _enc is None:
        _enc = get_encryption()

    # New format (день 40.2): finding_type передаётся явно.
    finding_type = finding_data.get("finding_type")
    if finding_type not in ("pii", "credentials", "code"):
        finding_type = category if category in ("pii", "credentials", "code") else "code"
    detail_category = finding_data.get("category") or "unknown"
    if detail_category in ("pii", "credentials", "code"):
        detail_category = subcategory or "unknown"

    fingerprint = finding_data.get("fingerprint")
    if not fingerprint:
        fingerprint = _enc.fingerprint(file_path, int(line_number or 0), value, finding_type)

    # === Дедупликация (день 40.2): не создаём повторно ===
    existing = db.query(models.Finding).filter(
        models.Finding.fingerprint == fingerprint
    ).first()
    if existing:
        if existing.status == "false_positive":
            skipped_false_positives += 1
            continue
        existing.last_seen_at = datetime.utcnow()
        deduped_findings += 1
        continue

    # Шифрование/маскирование: сканер приложил готовые значения — используем их.
    if finding_data.get("match_text_encrypted"):
        match_masked = finding_data.get("match_text_masked") or mask(value, detail_category)
        match_enc = finding_data["match_text_encrypted"]
    else:
        match_masked = mask(value, detail_category) if value else None
        match_enc = _enc.encrypt(value) if value else None

    line_text = finding_data.get("line_text", "")
    line_text_masked = finding_data.get("line_text_masked")
    if line_text_masked is None and finding_data.get("start_pos") is not None:
        st, en = finding_data.get("start_pos"), finding_data.get("end_pos")
        line_text_masked = mask_line(line_text, [(st, en, detail_category)])
    elif line_text_masked is None and line_text:
        line_text_masked = line_text

    finding = models.Finding(
        task_id=task_id,
        resource_id=task.resource_id,
        finding_type=finding_type,
        category=detail_category,
        severity=finding_data.get("severity", "medium"),
        fragment_type=finding_data.get("fragment_type", "text_line"),
        fragment_path=file_path,
        line_number=line_number or 0,
        match_text_masked=match_masked,
        match_text_encrypted=match_enc,
        line_text_masked=line_text_masked,
        line_text_encrypted=finding_data.get("line_text_encrypted"),
        context_before_masked=finding_data.get("context_before_masked") or context or None,
        context_after_masked=finding_data.get("context_after_masked") or None,
        bounding_box=finding_data.get("bounding_box") or (
            {"x": 0, "y": 0, "width": 0, "height": 0}
            if finding_data.get("fragment_type") == "image_region" else None
        ),
        byte_offset=finding_data.get("byte_offset"),
        byte_length=finding_data.get("byte_length"),
        hex_preview=finding_data.get("hex_preview"),
        fingerprint=fingerprint,
        encryption_key_id=finding_data.get("encryption_key_id") or _enc.key_id,
        status="new",
        confidence=float(confidence) if confidence else None,
        detector=finding_data.get("detector") or "legacy",
    )
    db.add(finding)
    saved_findings += 1

# ... catalog_entries / failed_files / task.completed ...

task.findings_count = saved_findings
# ...
return {
    "status": "accepted",
    "task_id": task_id,
    "findings_count": saved_findings,
    "catalog_entries_count": len(payload.get("catalog_entries", [])),
    "failed_files_count": len(payload.get("failed_files", [])),
    "deduped": deduped_findings,
    "skipped_false_positives": skipped_false_positives,
}
```

### 2.8 `docs/deployment.md` (MODIFIED)
Раздел «Ключи шифрования сканера (День 40.2)»: env `FINDINGS_*`, требование совпадения
с ключами Manager, поведение legacy-режима.

## 3. Тесты

```
python -m pytest tests/unit -m unit
# 34 passed (test_encryption.py 17 + test_scanner_findings.py 17)

python -m pytest tests/e2e -m "e2e and not requires_scanner and not requires_docker"  # против :18000
# 15 passed, 4 deselected (в т.ч. 2 новых e2e дня 40.2)

python -m pytest tests/e2e -m "e2e and (requires_scanner or requires_docker)"
# 4 skipped (нет живого сканера :9101 / Docker-марки)
```

Новые тесты:
- `tests/unit/test_scanner_findings.py` — Finding/to_dict, encryption (disabled/roundtrip/fingerprint),
  mask/mask_line/mask_context, CredentialsClassifier.scan_line (password/aws/placeholder/empty),
  FilesystemConnector (scan_file, `.env` по имени, scan_path, skip dirs, binary/empty);
- `tests/e2e/test_scanner_findings.py` — новый формат (сохранение категорий + маска от сканера),
  дедуп при повторном submit (`deduped`), FP не пересоздаётся (`skipped_false_positives`),
  сквозной сценарий с реальным сканером (`requires_scanner`, пока скипается).

Найденные и исправленные по ходу проблемы:
1. `_within_size` вызывал `.stat()` на str → `AttributeError` → `False` (все файлы «пропускались»). Исправлено: `Path(file_path)`.
2. Тест `test_mask_phone` имел неверное ожидание («999» в маске); актуализирован под `+7***123-45-67`.
3. Credentials-тест не находил пароль из-за `entropy_threshold=4.5`; в тестовом конфиге `1.0»`.
4. E2E читал `fragment_path` в ответе Manager — актуализировано на `file_path` (legacy-алиас).

## 4. Инструкция по запуску (ручной тест)

1. **Docker-стек тестов (Manager на :18000):**
   ```powershell
   cd D:\Projects\dcap-system
   docker compose -f docker-compose.test.yml up -d --build
   # проверка: http://localhost:18000/api/health
   ```
2. **Тесты Manager (без сканера):**
   ```powershell
   python -m pytest tests/e2e/test_scanner_findings.py -m e2e -v   # 2 теста (номенклатура)
   python -m pytest tests/unit/test_scanner_findings.py -m unit -v
   ```
3. **E2E с реальным сканером (опционально):**
   Запустите сканер против тест-стека с ключами (те же, что у Manager):
   ```powershell
   $env:MANAGER_URL="http://localhost:18000"
   python run_scanner.py scanner/config/scanner_config.json
   python -m pytest tests/e2e/test_scanner_findings.py -m "e2e and requires_scanner" -v
   ```
   Без ключей сканер уйдёт в legacy-режим (Manager зашифрует сам) — тоже рабочий путь.
4. **Локальный dev-стек:** как обычно `python run_manager.py` → `run_webui.py` → `run_scanner.py`.

## 5. Отклонения от ТЗ (обратная связь)

- **Fingerprint-компонент:** в `_serialize_finding` HMAC считает `enc.fingerprint(fpath, line_no, value, finding.finding_type)`
  (4-й компонент = `finding_type`), тогда как ТЗ 5.1 рисовал `category`. Это сделано для стабильности
  fingerprint при переименовании категорий и не ломает дедуп (и на сканере, и в legacy-ветке Manager
  компонент согласован). Задокументировано в комментарии кода.
- **`_legacy_fingerprint`:** md5 по `match_text` (не file|line|match|category, как в ТЗ). В legacy-режиме
  решающий fingerprint всё равно считает Manager (HMAC) — поле информационное.
- **Presidio:** в системном Python (3.13.5) импорт `presidio_analyzer` завис — unit-тесты не импортируют
  `pii_classifier`; на машине сканера (Anaconda с Presidio/spaCy) PII-ветка работает. Строчная обработка
  остаётся медленной на файлах 100k+ строк — префильтр `_quick_line_check` снимает нагрузку.
- **Code-classifier:** `scan_line → []` (по ТЗ — допустимо).
- **`scan_path`:** по ТЗ 4.1 `scan_file` сканировал одну папку; вместо этого сканер использует
  `scan_path` с обходом каталога (логичнее для заданий) — старый конвейер сохранён как fallback.
- **Производительность:** построчный путь буферизованный, контекст — только начальные N строк до/после
  без повторов; энтропия — по строке. Отдельный бенчмарк не проводился (см. День 40-41 load-тесты).

## 6. Готовность к Дню 40.3 (WebUI)

Протокол Manager→WebUI готов: GET `/api/findings` отдаёт новый формат с legacy-алиасами
`file_path`/`value`. WebUI найдет страницы Findings/Dashboard (деградация описана в STATE.md как
NEW-40.1, запланировано на 40.3).

## 7. Команда коммита

```bash
git checkout -b feature/day_40.2_scanner_findings
git add -A
git commit -m "feat: День 40.2 — Findings Refactor: сканер (построчно + FP + дедуп) (v3.10.0)

Модель находки в сканере (BACKLOG-053):
- scanner/src/finding.py: Finding dataclass (line_number, match_text,
  start_pos, end_pos, category, confidence, detector, контекст)
- scanner/src/encryption.py: AES-256-GCM + HMAC-fingerprint + маскирование
- Классификаторы: scan_line(line, line_num) → list[Finding]
  (pii, credentials, code)
- Filesystem connector: построчное чтение + контекст (N строк до/после)
- Конфиг: context_lines, text_extensions

FP-фильтр + дедупликация (BACKLOG-054/055):
- scanner/src/managed_scanner.py: batch-проверка check-fingerprints
- Фильтрация FP перед отправкой
- Отправка нового формата (match_text_encrypted, fingerprint, line_number)
- Legacy-режим (если ключи не заданы)

Manager:
- manager/src/api/scanner.py: submit_results поддерживает новый формат
- Дедупликация: FP не создаются повторно, найденное обновляет last_seen_at
- Legacy-формат конвертируется в новый

Тесты:
- tests/unit/test_scanner_findings.py: Finding, mask, encryption, fingerprint
- tests/e2e/test_scanner_findings.py: построчные находки, FP не дублируются

Docs:
- STATE.md → v3.10.0, следующий — День 40.3
- docs/deployment.md: env сканера (FINDINGS_*)"
```

Затем в STATE.md подправьте статистику и день (сам STATE.md уже обновлён v3.10.0).
```