# Отчёт: День 47.4 — Диагностика BUG-077 (TZ_FIX_BUG077_DIAG.md) — v3.13.18

**Дата:** 26.09.2026
**Версия:** v3.13.17 → **v3.13.18**
**Ветка:** `fix/scanner_deep`
**ТЗ:** `prompts/tz/TZ_FIX_BUG077_DIAG.md`

---

## Вывод диагностики

**Причина: H3 — Manager дефолтил `bounding_box` при сохранении findings.**

Сканер шлёт `bounding_box: null` (для OCR — координаты не вычисляются), но
`manager/src/api/scanner.py:490-492` имел fallback:

```python
bounding_box=finding_data.get("bounding_box") or (
    {"x": 0, "y": 0, "width": 0, "height": 0} if finding_data.get("fragment_type") == "image_region" else None
),
```

`None or default` → в БД уходил `{0,0,0,0}`. Фикс TASK-041 (scanner) был корректен,
но перезаписывался на стороне Manager.

## Шаги диагностики (по ТЗ)

### Шаг 1 — Grep по проекту на `bounding_box` (28 совпадений)
Один источник дефолта: `manager/src/api/scanner.py:490`. Прочее — чтение/сериализация
(findings.py, managed_scanner.py:673, models.py:143, schemas_findings.py:30).

### Шаг 2 — Grep по сканеру на `"x": 0 / 'x': 0` → **нет совпадений**
H4 исключена (второго источника `{0,0,0,0}` в сканере нет).

### Шаг 3 — Процесс сканера
```
PID  22956  python -X utf8 run_scanner.py scanner\config\scanner_config.json
PID  14404  multiprocessing-spawn (OCRWorker)
```
Запуск из корня репо — H5 исключена.

### Шаг 4 — Grep на `to_dict|setdefault|bounding_box.*or` в сканере → **нет второго присваивания**
`finding.to_dict()` (finding.py:60) просто возвращает `self.bounding_box`. H2/H6 исключены.

### Шаг 5 — Grep по Manager → **H3 подтверждена**
`manager/src/api/scanner.py:490` — дефолт `{0,0,0,0}` для `image_region`, когда bbox пуст/None.
Pydantic-модель Manager (`schemas_findings.py:30`) — `Optional[dict] = None`, DB-колонка nullable.

### Шаг 6 — Payload сканера
`managed_scanner.py:659-677`: `"bounding_box": finding.bounding_box` → **None (JSON null)**.
Сканер корректен.

### Шаг 7 — `__pycache__`
`filesystem.cpython-313.pyc` (18:36) новее `filesystem.py` (18:35) — stale-кэша нет, H1 исключена.
Дополнительно: единственный `filesystem.py` (`scanner/connectors/`), H7 исключена.

### Шаг 8 — REPL на реальном .png
`FilesystemConnector` + `PiiClassifier` на `C:\test\scanner_clean\images\screenshot_clean.png`
→ `TOTAL: 0` (в беспримесной копии картинки OCR не находит PII), без ошибок.
Покрытие фикса сканера подтверждено unit-тестом (`test_ocr_finding_bbox_is_none`).

## Фикс (TASK-044)

`manager/src/api/scanner.py` — дефолт убран:

```python
# BUG-077 (TASK-044, v3.13.18): сканер шлёт bounding_box=None для OCR ...
bounding_box=finding_data.get("bounding_box"),
```

## Проверки

- `python -m py_compile manager/src/api/scanner.py` → OK
- `python -m pytest tests/unit/test_ocr_bbox_v31317.py -v` → **4 passed** (+2 fallback)
- `python -m pytest tests/unit/ -q` → **146 passed** (144 + 2)
- Параметр `fragment_type=image_region` в `GET /api/findings` API не фильтрует (известное
  поведение), поэтому выборка делалась по строкам: OCR-findings (1415/1416) видны в списке.

## Live-подтверждение (task 38)

```
DELETE FROM findings WHERE task_id IN (36, 37);   -- 29 удалено (дедупликация мешала)
task 38: status=completed, findings_count=29, files_scanned=7, files_failed=0

SELECT id, category, fragment_type, detector, bounding_box
FROM findings WHERE task_id = 38 AND fragment_type = 'image_region';
  id  | category | fragment_type | detector | bounding_box
 1415 | email    | image_region  | ocr      | null
 1416 | phone    | image_region  | ocr      | null

SELECT category, detector, COUNT(*)... → 15 категорий, 29 findings (идентично task 35)

API detail finding 1415: bounding_box=[], has_fragment=True, file_path=C:\test\scanner_clean\images\screenshot_clean.png
```

**Критерий 4.3 (`/fragment` → 200 + X-Fragment-Mode: full-image)** — в Docker-окружении
не выполняем без монтирования хостового пути: Manager-контейнер не видит
`C:\test\...` (пути хоста от сканера), fallback корректно возвращает 404. Поведение
fallback покрыто unit-тестом `TestFragmentFallback` (200 + full-image при наличии файла,
404 при его отсутствии). Для полного live-провода `/fragment` требуется запуск Manager
на хосте (или монтирование папок сканирования в контейнер).

## Коммиты

```
14079d9 fix: BUG-077 diag — причина H3: Manager дефолтил bounding_box={0,0,0,0} для image_region, v3.13.18
```

## Пересборка контейнеров

```
$env:VERSION="3.13.18"; docker compose build manager webui celery_worker celery_beat
$env:VERSION="3.13.18"; docker compose up -d manager webui celery_worker celery_beat
GET /api/health → {"status":"healthy","version":"3.13.18"}
docker compose ps → manager/webui/celery_worker/celery_beat (healthy, 3.13.18)
```

## Док-правки

- `docs/admin-guide/10-troubleshooting.md` — создан (ТЗ §Дополнительно: «Код сканера не
  влияет на findings», stub __pycache__, bbox={0,0,0,0}, устаревшая версия, зависшие контейнеры).
- `STATE.md` → v3.13.18, день 47.4, BUG-077 ✅ live.
- `CHANGELOG.md` → секция [3.13.18].

## Статус BUG-077

**BUG-077 → ✅ подтверждён в live (task 38, bounding_box = NULL).** BACKLOG-085 (полный
OCR-пайплайн с bbox) — 📋 v3.1.0.