# CHANGELOG

## v3.12.0 (2026-09-12)

### Findings Refactor — Этап 4 (финал)
- BACKLOG-058: фрагменты изображений — `GET /api/findings/{id}/fragment` → PNG
  (вырезанный из `fragment_path` или crop по `bounding_box` через Pillow, кэширование)
- BACKLOG-059: hex-дамп бинарных фрагментов — `?format=hex` вокруг `byte_offset`
  (окно ±64 байта, `manager/src/core/hex_dump.py`)
- BACKLOG-060: экспорт CSV/JSON с маскированием + reveal (Auditor+),
  аудит `findings_exported`, CSV injection protection (`csv_utils.py`), BOM для Excel
- BACKLOG-067: `X-Total-Count` в `GET /api/findings`; пагинация с номерами страниц в WebUI
- WebUI: `<img>` для image_region, `<pre>` для byte_range (finding_detail.js),
  кнопка «Экспорт» с диалогом формата/reveal (findings.js), `api.getWithMeta`
- Тесты: `tests/e2e/test_finding_fragments.py`, `tests/e2e/test_findings_export.py`,
  `tests/unit/test_hex_dump.py`, `tests/unit/test_csv_utils.py`