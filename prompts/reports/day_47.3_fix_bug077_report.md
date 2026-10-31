# Отчёт: День 47.3 — BUG-077 (TZ_FIX_BUG077.md) — v3.13.17

**Дата:** 25.09.2026
**Версия:** v3.13.16 → **v3.13.17**
**Ветка:** `fix/scanner_deep`
**ТЗ:** `prompts/tz/TZ_FIX_BUG077.md` (перенесён в `prompts/archive/` после выполнения)

---

## Что сделано

### TASK-041 (BUG-077) — `bounding_box = None` вместо `{0,0,0,0}`

Файл: `scanner/connectors/filesystem.py`, OCR-блок `scan_file`.

OCR-finding'и получали захардкоженный `bounding_box = {"x":0,"y":0,"width":0,"height":0}`.
Координаты никогда не вычисляются (Tesseract вызывается без `--psm/tsv`, только текст),
поэтому `{0,0,0,0}` вводил в заблуждение API/WebUI/аудит — они считали, что координаты
есть, а вырезать нечего. Заменён на `None` (Вариант C). Полный OCR-пайплайн с реальным
bbox — **BACKLOG-085 (v3.1.0)**.

```python
for f in findings:
    f.fragment_type = "image_region"
    f.detector = "ocr"
    f.bounding_box = None
```

### TASK-042 (BUG-077) — fallback в endpoint `/fragment` (Вариант 1)

Файл: `manager/src/api/findings.py`, `_get_image_fragment`.

Если `fragment_type = "image_region"` и `bounding_box IS NULL` — возвращается **весь PNG**
(не обрезанный) с заголовком `X-Fragment-Mode: full-image`. Файл недоступен → 404.
Порядок проверки: путь из `fragment_path`; у OCR-находок `fragment_path` заполняется
через `_scan_text` (L380/408) → `has_fragment = True` остаётся корректным.

```python
if finding.fragment_type == "image_region" and not finding.bounding_box:
    with open(path, "rb") as f:
        data = f.read()
    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="finding_{finding.id}.png"',
            "X-Fragment-Mode": "full-image",
        },
    )
```

### TASK-043 (косметика) — синхронизация VERSION агентов

`docker-compose.yml`: `s3_agent` (203) и `audit_agent_linux` (231): `${VERSION:-3.13.12}` → `${VERSION:-3.13.16}`.
`.env.example` не тронут (там уже `3.13.16`).

### Релиз v3.13.17

`docker-compose.yml`: manager/webui → `3.13.17`.

---

## Проверка

- `python -m py_compile scanner/connectors/filesystem.py manager/src/api/findings.py` → OK
- `python -m pytest tests/unit/test_ocr_bbox_v31317.py -v` → **2 passed**
- `python -m pytest tests/unit/ -q` → **144 passed** (142 + 2 новых)

> ⚠️ Нюанс реализации теста: в ТЗ тест патчил `FileSystemConnector` (грубый обходной коннектор,
> методы `scan_file`/`_extract_document`/`_scan_text` у него отсутствуют). Реальный построчный
> коннектор — `FilesystemConnector`. Тест исправлен: используется `FilesystemConnector({})`,
> а для `if not p.exists(): return []` создаёт реальные `dummy.png`/`dummy.txt` через `tmp_path`.

## Коммиты

```
2c22324 fix: BUG-077 (TASK-041,042) — bounding_box=None для OCR + fallback full-image в /fragment, v3.13.17
```

## Пересборка контейнеров

```
$env:VERSION="3.13.17"; docker compose build manager
$env:VERSION="3.13.17"; docker compose build webui
$env:VERSION="3.13.17"; docker compose up -d
# celery_worker завис при рекреации → docker stop/rm по celery_worker, повторный up -d
docker compose ps → manager/webui/celery_worker/celery_beat (healthy), images dcap/manager|webui:3.13.17
GET http://127.0.0.1:8000/api/health → {"status":"healthy","version":"3.13.17"}
```

## Критерии приёмки ТЗ №8

| Критерий | Статус |
|----------|--------|
| py_compile filesystem.py + findings.py — OK | ✅ |
| pytest test_ocr_bbox_v31317.py — 2 passed | ✅ |
| pytest tests/unit/ — 144 passed (регрессий нет) | ✅ |
| Manager /api/health → 3.13.17 | ✅ |
| docker-compose.yml агентов → 3.13.16 | ✅ |
| Manager/WebUI → 3.13.17 | ✅ |
| Очистка findings task 35 + live-прогон task 36 (bbox=NULL, 29 findings, /fragment full-image) | ⏳ live-прогон (нужен пользователь) |
| STATE.md, ROADMAP.md (BUG-077 → ✅, BACKLOG-085 добавлен), ARCHITECTURE.md, STATE_TEST_SESSION.md | ✅ |

## Последние использованные файлы

- `scanner/connectors/filesystem.py` — TASK-041 (bbox=None для OCR)
- `manager/src/api/findings.py` — TASK-042 (fallback full-image + X-Fragment-Mode)
- `docker-compose.yml` — TASK-043 (агенты 3.13.16) + релиз (manager/webui 3.13.17)
- `tests/unit/test_ocr_bbox_v31317.py` — новые smoke-тесты (2)
- `STATE.md`, `ROADMAP.md`, `STATE_TEST_SESSION.md`, `CHANGELOG.md`, `ARCHITECTURE.md` — обновлены