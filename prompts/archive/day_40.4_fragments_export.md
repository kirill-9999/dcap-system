📋 ТЗ: День 40.4 — Findings Refactor: Фрагменты + Экспорт (Этап 4)
Дата: 12.09.2026
Роль: Кодер
Версия (целевая): v3.12.0
Ветка: feature/day_40.4_fragments_export
Предыдущая версия: v3.11.0
Этап: 4 из 4 (Findings Refactor) — финальный

🎯 Цель дня
Завершить Findings Refactor — добавить работу с не-текстовыми фрагментами (изображения, бинарные данные) и экспорт находок с маскированием.

Ключевые задачи:

🟡 BACKLOG-058 — Фрагменты изображений (bounding box) → PNG

🟢 BACKLOG-059 — Бинарные: hex-дамп

🟡 BACKLOG-060 — Экспорт с маскированием (CSV/JSON)

🟡 BACKLOG-067 (опционально) — Пагинация находок: total в list-ответе

ВАЖНО: это финальный этап Findings Refactor. После 40.4 → админ-руководство (42.1-42.4) → GitHub (42) → релиз v3.0.0 (43).

📐 Контекст (из ARCHITECTURE.md)
Типы фрагментов
Тип	Для чего	Что показывать
text_line	Текстовые файлы	Строка с совпадением (готово в 40.1-40.3)
text_context	Текстовые файлы	Строка + N строк контекста (готово)
image_region	Изображения, PDF-сканы	Вырезанный фрагмент (PNG) + bounding box
byte_range	Бинарные	Hex-дамп вокруг offset
Поля модели Finding (уже есть в БД, 40.1)
python
fragment_type    = Column(String(20))   # image_region | byte_range
fragment_path    = Column(String(500))  # путь к вырезанному фрагменту (PNG)
bounding_box     = Column(JSON)         # {x, y, w, h}
byte_offset      = Column(Integer)
byte_length      = Column(Integer)
hex_preview      = Column(Text)         # hex-дамп (masked)
API (задекларирован в ARCHITECTURE.md)
Метод	Эндпоинт	Роль	Назначение
GET	/api/findings/{id}/fragment	Viewer+	Фрагмент (изображение/hex)
GET	/api/findings/export	Auditor+	Экспорт (CSV/JSON)
📦 Под-день 40.4.1 — Фрагменты: изображения + бинарные
Версия: v3.12.0
Цель: пользователь видит вырезанный фрагмент изображения (PNG) или hex-дамп бинарного файла.

Задачи
#	Задача	Артефакт
1	Эндпоинт GET /api/findings/{id}/fragment (PNG)	manager/src/api/findings.py
2	Эндпоинт GET /api/findings/{id}/fragment?format=hex	manager/src/api/findings.py
3	Crop через Pillow (fallback)	manager/src/core/image_fragment.py (NEW)
4	Форматтер hex-дампа	manager/src/core/hex_dump.py (NEW)
5	WebUI: <img> для image_region	webui/static/js/finding_detail.js
6	WebUI: <pre> для byte_range	webui/static/js/finding_detail.js
7	Тесты	tests/e2e/test_finding_fragments.py (NEW)
tests/unit/test_hex_dump.py (NEW)
1. Эндпоинт GET /api/findings/{id}/fragment
MODIFIED: manager/src/api/findings.py

python
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from PIL import Image
import io
import os

@router.get("/{finding_id}/fragment")
async def get_finding_fragment(
    finding_id: int,
    format: str = Query("png", regex="^(png|hex)$"),
    db: Session = Depends(get_db),
    current_user = Depends(require_viewer),
):
    """
    Вернуть фрагмент находки.

    - image_region → PNG (crop по bounding_box)
    - byte_range   → hex-дамп (format=hex)
    - text_line/text_context → 400 (текст отдаётся в /api/findings/{id})
    """
    finding = db.query(models.Finding).filter(models.Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    if finding.fragment_type == "image_region":
        # PII без маски (person) — только Auditor+
        if finding.category == "person" and not can_reveal(current_user):
            raise HTTPException(403, "Reveal required for this fragment")
        return await _get_image_fragment(finding)

    if finding.fragment_type == "byte_range":
        return await _get_hex_fragment(finding)

    raise HTTPException(400, f"Fragment not available for type: {finding.fragment_type}")
Логика для image_region (вариант A + B):

python
async def _get_image_fragment(finding) -> Response:
    """Отдать PNG-фрагмент."""
    # A: уже вырезан — отдать напрямую
    if finding.fragment_path and os.path.exists(finding.fragment_path):
        with open(finding.fragment_path, "rb") as f:
            data = f.read()
    # B: fallback — вырезать через Pillow
    elif finding.bounding_box:
        data = crop_image(finding.bounding_box)
        # Кэшировать
        if finding.fragment_path:
            os.makedirs(os.path.dirname(finding.fragment_path), exist_ok=True)
            with open(finding.fragment_path, "wb") as f:
                f.write(data)
    else:
        raise HTTPException(404, "Fragment not available")

    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="finding_{finding.id}.png"',
            "X-Bounding-Box": json.dumps(finding.bounding_box or {}),
        },
    )
Логика для byte_range (hex):

python
async def _get_hex_fragment(finding, window: int = 64) -> Response:
    """Hex-дамп вокруг byte_offset."""
    if finding.hex_preview:
        return Response(content=finding.hex_preview, media_type="text/plain")

    if not finding.fragment_path or not os.path.exists(finding.fragment_path):
        raise HTTPException(404, "Fragment not available")

    offset = finding.byte_offset or 0
    length = finding.byte_length or 0
    start = max(0, offset - window)
    end = offset + length + window

    with open(finding.fragment_path, "rb") as f:
        f.seek(start)
        data = f.read(end - start)

    dump = format_hex_dump(data, base_offset=start)
    return Response(content=dump, media_type="text/plain; charset=utf-8")
2. Crop через Pillow
NEW: manager/src/core/image_fragment.py

python
"""Crop фрагмента изображения по bounding_box (День 40.4)."""
import io
from PIL import Image


def crop_image(
    image_path: str,
    bounding_box: dict,
    output_format: str = "PNG",
) -> bytes:
    """
    Вырезать фрагмент изображения.

    bounding_box: {"x": int, "y": int, "w": int, "h": int}
    Возвращает bytes (PNG).
    """
    img = Image.open(image_path)
    x = bounding_box.get("x", 0)
    y = bounding_box.get("y", 0)
    w = bounding_box.get("w", img.width)
    h = bounding_box.get("h", img.height)

    # Защита от выхода за пределы
    x = max(0, min(x, img.width))
    y = max(0, min(y, img.height))
    w = max(1, min(w, img.width - x))
    h = max(1, min(h, img.height - y))

    cropped = img.crop((x, y, x + w, y + h))

    buf = io.BytesIO()
    cropped.save(buf, format=output_format)
    return buf.getvalue()
Примечание: Pillow>=10.0.0 добавить в manager/requirements.txt (если ещё нет).

3. Форматтер hex-дампа
NEW: manager/src/core/hex_dump.py

python
"""Форматтер hex-дампа (День 40.4)."""


def format_hex_dump(data: bytes, base_offset: int = 0, width: int = 16) -> str:
    """
    Классический hex-дамп:

    00000000  48 65 6c 6c 6f 20 57 6f  72 6c 64 21 0a 00 00 00  |Hello World!....|
    """
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        offset_str = f"{base_offset + i:08x}"
        hex_str = " ".join(f"{b:02x}" for b in chunk).ljust(width * 3 - 1)
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{offset_str}  {hex_str}  |{ascii_str}|")
    return "\n".join(lines)
4. WebUI — finding_detail.js
MODIFIED: webui/static/js/finding_detail.js

Добавить в renderFragment(f):

javascript
renderFragment(f) {
    if (f.fragment_type === 'image_region') {
        return `<img src="/api/findings/${f.id}/fragment"
                     class="img-fluid finding-image"
                     alt="Фрагмент находки #${f.id}"
                     data-bbox='${JSON.stringify(f.bounding_box || {})}'>`;
    }
    if (f.fragment_type === 'byte_range') {
        return f.hex_preview
            ? `<pre class="finding-hex">${escapeHtml(f.hex_preview)}</pre>`
            : `<pre class="finding-hex" id="hex-dump">Загрузка…</pre>`;
    }
    // text_line / text_context
    const lines = [];
    if (f.context_before) lines.push(`<span class="text-muted">${escapeHtml(f.context_before)}</span>`);
    if (f.line_text) lines.push(`<mark>${escapeHtml(f.line_text)}</mark>`);
    if (f.context_after) lines.push(`<span class="text-muted">${escapeHtml(f.context_after)}</span>`);
    return lines.join('\n');
}
Дозагрузка hex (если hex_preview пуст):

javascript
async loadHexFragment() {
    const el = document.getElementById('hex-dump');
    if (!el) return;
    try {
        const r = await fetch(`/api/findings/${window.FINDING_ID}/fragment?format=hex`,
                              { headers: api._headers() });
        el.textContent = await r.text();
    } catch (e) {
        el.textContent = 'Ошибка загрузки: ' + e.message;
    }
}
CSS (webui/static/css/findings.css):

css
.finding-image { max-width: 100%; border: 1px solid #dee2e6; border-radius: 4px; }
.finding-hex {
    font-family: var(--font-mono, ui-monospace, Consolas, monospace);
    font-size: 12px;
    line-height: 1.4;
    white-space: pre;
    overflow-x: auto;
}
5. Тесты
NEW: tests/e2e/test_finding_fragments.py

python
"""E2E-тесты фрагментов находок (День 40.4)."""
import pytest
import requests

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


def test_image_region_fragment(manager_url, api_client):
    """image_region → PNG."""
    r = api_client.get(f"{manager_url}/api/findings/1/fragment")
    if r.status_code == 404:
        pytest.skip("No image_region finding in test data")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_byte_range_hex(manager_url, api_client):
    """byte_range → hex-дамп."""
    r = api_client.get(f"{manager_url}/api/findings/1/fragment?format=hex")
    if r.status_code == 404:
        pytest.skip("No byte_range finding in test data")
    assert r.status_code == 200
    assert "00000000" in r.text


def test_text_fragment_rejected(manager_url, api_client):
    """text_line → 400."""
    r = api_client.get(f"{manager_url}/api/findings/1/fragment")
    if r.status_code == 404:
        pytest.skip("No text_line finding")
    assert r.status_code == 400


def test_fragment_requires_auth(manager_url):
    """Без токена → 401."""
    r = requests.get(f"{manager_url}/api/findings/1/fragment", timeout=5)
    assert r.status_code == 401
NEW: tests/unit/test_hex_dump.py

python
"""Unit-тесты hex-дампа."""
from manager.src.core.hex_dump import format_hex_dump


def test_hex_dump_format():
    data = b"Hello World!"
    dump = format_hex_dump(data, base_offset=0)
    assert "00000000" in dump
    assert "48 65 6c 6c 6f" in dump
    assert "|Hello World!|" in dump


def test_hex_dump_non_printable():
    data = b"\x00\x01\x02abc"
    dump = format_hex_dump(data)
    assert "|...abc|" in dump


def test_hex_dump_offset():
    data = b"ABCD"
    dump = format_hex_dump(data, base_offset=0x100)
    assert "00000100" in dump
✅ Тестирование 40.4.1
bash
# 1. API — фрагмент
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/findings/1/fragment -o fragment.png
file fragment.png  # → PNG image data

# 2. Hex
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/findings/1/fragment?format=hex
# → 00000000  48 65 6c 6c 6f ...

# 3. Тесты
pytest tests/e2e/test_finding_fragments.py tests/unit/test_hex_dump.py -v
📦 Под-день 40.4.2 — Экспорт находок (CSV/JSON)
Цель: Auditor+ экспортирует находки с маскированием (по умолчанию) или reveal (с аудитом).

Задачи
#	Задача	Артефакт
1	Эндпоинт GET /api/findings/export	manager/src/api/findings.py
2	Логика masked/reveal	manager/src/core/encryption.py
3	CSV injection protection	manager/src/core/csv_utils.py (NEW)
4	WebUI: кнопка «Экспорт»	webui/static/js/findings.js
5	Тесты	tests/e2e/test_findings_export.py (NEW)
1. Эндпоинт GET /api/findings/export
MODIFIED: manager/src/api/findings.py

python
import csv
import io
from datetime import datetime
from fastapi import Query, Response

@router.get("/export")
async def export_findings(
    format: str = Query("csv", regex="^(csv|json)$"),
    reveal: bool = Query(False),
    status: Optional[str] = None,
    finding_type: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    task_id: Optional[int] = None,
    limit: int = Query(10000, le=100000),
    db: Session = Depends(get_db),
    current_user = Depends(require_auditor),
):
    """
    Экспорт находок.

    - format=csv|json
    - reveal=true → расшифровка (только Auditor+, с аудитом)
    - По умолчанию — маскированное
    """
    if reveal and not can_reveal(current_user):
        raise HTTPException(403, "Reveal requires Auditor role")

    q = db.query(models.Finding)
    if status:       q = q.filter(models.Finding.status == status)
    if finding_type: q = q.filter(models.Finding.finding_type == finding_type)
    if category:     q = q.filter(models.Finding.category == category)
    if severity:     q = q.filter(models.Finding.severity == severity)
    if task_id:      q = q.filter(models.Finding.task_id == task_id)

    findings = q.limit(limit).all()

    # Аудит
    log_action(db, current_user, "findings_exported", {
        "format": format,
        "reveal": reveal,
        "count": len(findings),
        "filters": {
            "status": status, "finding_type": finding_type,
            "category": category, "severity": severity, "task_id": task_id,
        },
    })

    if format == "csv":
        return _export_csv(findings, reveal)
    return _export_json(findings, reveal)
2. Логика CSV / JSON
python
def _export_csv(findings, reveal: bool) -> Response:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "file_path", "line_number", "finding_type", "category",
        "severity", "status", "match_text", "line_text",
        "first_seen_at", "last_seen_at",
    ])
    for f in findings:
        match = _resolve_text(f, "match_text", reveal)
        line = _resolve_text(f, "line_text", reveal)
        writer.writerow([
            f.id,
            sanitize_csv_cell(f.fragment_path or ""),
            f.line_number or "",
            f.finding_type, f.category, f.severity, f.status,
            sanitize_csv_cell(match), sanitize_csv_cell(line),
            f.first_seen_at.isoformat() if f.first_seen_at else "",
            f.last_seen_at.isoformat() if f.last_seen_at else "",
        ])
    content = "\ufeff" + output.getvalue()  # BOM для Excel
    filename = f"findings_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _export_json(findings, reveal: bool) -> Response:
    data = [_finding_to_export_dict(f, reveal) for f in findings]
    filename = f"findings_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _resolve_text(finding, field: str, reveal: bool) -> str:
    """masked → reveal при необходимости."""
    if reveal:
        encrypted = getattr(finding, f"{field}_encrypted", None)
        if encrypted:
            return decrypt(encrypted)
    return getattr(finding, f"{field}_masked", "") or ""
3. CSV injection protection
NEW: manager/src/core/csv_utils.py

python
"""CSV-утилиты (День 40.4)."""

_CSV_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: str) -> str:
    """
    Защита от CSV injection (формулы в Excel/LibreOffice).

    Если значение начинается с =, +, -, @, TAB, CR — префиксуем апострофом.
    """
    if value and value[0] in _CSV_DANGEROUS:
        return "'" + value
    return value
4. WebUI — кнопка «Экспорт»
MODIFIED: webui/static/js/findings.js

javascript
bindEvents() {
    // ... существующие ...
    document.getElementById('export-btn').addEventListener('click', () => this.showExportDialog());
},

showExportDialog() {
    const fmt = prompt("Формат экспорта (csv/json):", "csv");
    if (!fmt || !["csv", "json"].includes(fmt)) return;

    const reveal = confirm("Показать оригиналы (только Auditor+)?\n\nOK = reveal, Отмена = masked");

    const params = new URLSearchParams({
        ...this.collectFilters(),
        format: fmt,
        reveal: reveal ? "true" : "false",
    });
    // Убрать пустые
    for (const [k, v] of [...params.entries()]) {
        if (!v || v === "false") params.delete(k);
    }
    window.location.href = `/api/findings/export?${params}`;
}
Примечание: window.location.href — чтобы браузер скачал файл с Content-Disposition: attachment. Прокси WebUI должен пропускать этот заголовок (проверить в webui/api/routes.py).

5. Тесты
NEW: tests/e2e/test_findings_export.py

python
"""E2E-тесты экспорта находок (День 40.4)."""
import csv
import io
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


def test_export_csv_masked(manager_url, api_client):
    r = api_client.get(f"{manager_url}/api/findings/export?format=csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["Content-Type"]
    assert "attachment" in r.headers["Content-Disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf")  # BOM
    reader = csv.reader(io.StringIO(r.content.decode("utf-8-sig")))
    headers = next(reader)
    assert "id" in headers and "match_text" in headers


def test_export_json_masked(manager_url, api_client):
    r = api_client.get(f"{manager_url}/api/findings/export?format=json")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_export_reveal_requires_auditor(manager_url, viewer_client):
    r = viewer_client.get(f"{manager_url}/api/findings/export?reveal=true")
    assert r.status_code == 403


def test_export_filters(manager_url, api_client):
    r = api_client.get(f"{manager_url}/api/findings/export?format=json&status=new")
    assert r.status_code == 200
    for item in r.json():
        assert item["status"] == "new"


def test_csv_injection_sanitized():
    from manager.src.core.csv_utils import sanitize_csv_cell
    assert sanitize_csv_cell("=cmd|' /C calc'!A0").startswith("'=")
    assert sanitize_csv_cell("+1234").startswith("'+")
    assert sanitize_csv_cell("@SUM(1)").startswith("'@")
    assert sanitize_csv_cell("normal") == "normal"
✅ Тестирование 40.4.2
bash
# 1. CSV (masked)
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8000/api/findings/export?format=csv" \
     -o findings.csv
head findings.csv  # BOM + headers

# 2. JSON (masked)
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8000/api/findings/export?format=json" | jq '. | length'

# 3. Reveal (Auditor+)
curl -H "Authorization: Bearer $AUDITOR_TOKEN" \
     "http://localhost:8000/api/findings/export?format=json&reveal=true"

# 4. Тесты
pytest tests/e2e/test_findings_export.py tests/unit/test_hex_dump.py -v
📦 Под-день 40.4.3 (опционально) — Пагинация: total в list-ответе
BACKLOG-067 — X-Total-Count в GET /api/findings.

MODIFIED: manager/src/api/findings.py

python
@router.get("")
async def list_findings(...):
    q = db.query(models.Finding)
    # ... фильтры ...
    total = q.count()
    findings = q.offset(offset).limit(limit).all()
    return Response(
        content=json.dumps([f.to_dict() for f in findings]),
        media_type="application/json",
        headers={"X-Total-Count": str(total)},
    )
MODIFIED: webui/static/js/findings.js — renderPagination(hasMore, total) с номерами страниц.

Приоритет: 🟡 если успеваешь — делай. Если нет — переносим на v3.0.0.

📦 Часть 4. Общие правки
4.1. manager/requirements.txt
text
Pillow>=10.0.0
4.2. Прокси WebUI
Проверить webui/api/routes.py:

/api/findings/{id}/fragment — проксируется catch-all?

/api/findings/export — Content-Disposition: attachment пробрасывается?

Если нет — добавить (см. образец 40.3).

📦 Часть 5. Тесты (сводка)
Тест	Что проверяет
tests/e2e/test_finding_fragments.py	PNG для image_region, hex для byte_range, 400 для text, 401 без токена
tests/e2e/test_findings_export.py	CSV/JSON masked, reveal для Auditor+, фильтры, CSV injection
tests/unit/test_hex_dump.py	Формат hex-дампа, non-printable, offset
Прогон:

bash
pytest tests/unit tests/e2e/test_finding_fragments.py tests/e2e/test_findings_export.py -v
📦 Часть 6. Документация
6.1. STATE.md (кодер обновит в конце)
Версия → v3.12.0

Текущий день → 40.4 ✅, следующий — 42.1

Последний отчёт → day_40.4_report.md

Закрытые: BACKLOG-058, 059, 060 (+067 если успел)

6.2. ROADMAP.md
День 40.4 ✅

BACKLOG-058, 059, 060 ✅

BACKLOG-067 ✅ (если сделан)

Статистика v3.0.0: 25/35 → 28/35 (80%)

ИТОГО: 52/86 → 55/86 (64%)

6.3. ARCHITECTURE.md
Обновить таблицу API находок (подтвердить fragment, export)

Раздел «Типы фрагментов» — примеры форматов ответа

6.4. CHANGELOG.md
markdown
## v3.12.0 (2026-09-12)
### Findings Refactor — Этап 4 (финал)
- BACKLOG-058: фрагменты изображений (PNG, bounding box)
- BACKLOG-059: hex-дамп бинарных фрагментов
- BACKLOG-060: экспорт CSV/JSON с маскированием + reveal (Auditor+)
- BACKLOG-067: X-Total-Count в /api/findings
6.5. docs/deployment.md
markdown
### Фрагменты и экспорт находок

- `GET /api/findings/{id}/fragment` — PNG (image_region) или hex (byte_range)
- `GET /api/findings/export?format=csv|json` — экспорт (Auditor+)
  - По умолчанию — маскированное
  - `?reveal=true` — расшифровка (Auditor+), с аудитом
✅ Критерии приёмки Дня 40.4
40.4.1 — Фрагменты
□ GET /api/findings/{id}/fragment → PNG для image_region
□ ?format=hex → hex-дамп для byte_range
□ 400 для text_line / text_context
□ 404 если не найдено, 403 если PII без маски
□ WebUI: <img> для изображений, <pre> для hex
□ Тесты: test_finding_fragments.py, test_hex_dump.py
40.4.2 — Экспорт
□ GET /api/findings/export?format=csv → CSV с masked
□ GET /api/findings/export?format=json → JSON с masked
□ ?reveal=true — только Auditor+, запись в audit_logs
□ Фильтры работают
□ CSV с BOM, Content-Disposition: attachment
□ CSV injection защита
□ WebUI: кнопка «Экспорт»
□ Тесты: test_findings_export.py
40.4.3 — Пагинация (опционально)
□ X-Total-Count в GET /api/findings
□ WebUI: renderPagination использует total
Общее
□ Все тесты проходят
□ STATE.md обновлён (v3.12.0)
□ ROADMAP.md — День 40.4 ✅, BACKLOG-058/059/060 ✅
□ ARCHITECTURE.md — обновлён
□ CHANGELOG.md — v3.12.0
□ Отчёт prompts/reports/day_40.4_report.md
📁 Артефакты (итог)
NEW:

manager/src/core/image_fragment.py

manager/src/core/hex_dump.py

manager/src/core/csv_utils.py

tests/e2e/test_finding_fragments.py

tests/e2e/test_findings_export.py

tests/unit/test_hex_dump.py

prompts/reports/day_40.4_report.md

MODIFIED:

manager/src/api/findings.py (fragment + export)

manager/requirements.txt (Pillow)

webui/static/js/finding_detail.js (image/hex render)

webui/static/js/findings.js (export button)

webui/static/css/findings.css (image/hex styles)

webui/api/routes.py (прокси, если нужно)

docs/deployment.md (фрагменты + экспорт)

STATE.md (v3.12.0)

ROADMAP.md (День 40.4 ✅)

ARCHITECTURE.md (API)

CHANGELOG.md (v3.12.0)

DELETED: —

🚀 Команда коммита
bash
git checkout -b feature/day_40.4_fragments_export
git add -A
git commit -m "feat: День 40.4 — Findings Refactor: Фрагменты + Экспорт (v3.12.0)

BACKLOG-058 — Фрагменты изображений (bounding box):
- GET /api/findings/{id}/fragment → PNG (crop по bounding_box)
- manager/src/core/image_fragment.py (Pillow)
- Кэширование в fragment_path

BACKLOG-059 — Hex-дамп бинарных:
- ?format=hex → hex-дамп вокруг byte_offset
- manager/src/core/hex_dump.py
- Окно ±64 байта

BACKLOG-060 — Экспорт с маскированием:
- GET /api/findings/export?format=csv|json
- По умолчанию masked, reveal (Auditor+) с аудитом
- CSV injection защита (csv_utils.py)
- BOM для Excel

BACKLOG-067 (опц.) — X-Total-Count в /api/findings

WebUI:
- finding_detail.js: <img> для image_region, <pre> для byte_range
- findings.js: кнопка «Экспорт» (CSV/JSON, reveal)
- findings.css: стили

Тесты:
- tests/e2e/test_finding_fragments.py
- tests/e2e/test_findings_export.py
- tests/unit/test_hex_dump.py

Docs:
- STATE.md → v3.12.0
- ROADMAP.md: День 40.4 ✅
- ARCHITECTURE.md, CHANGELOG.md, docs/deployment.md"
📝 Обратная связь архитектору (шаблон)
После выполнения — заполнить:

Что заработало / что нет — по под-дням

Фикстуры для фрагментов — как создавал image_region/byte_range в тестах

Pillow — версия, проблемы с установкой

Экспорт — размер CSV/JSON на 10k находок, производительность

Reveal в экспорте — проверен ли аудит (findings_exported_revealed)

BACKLOG-067 — сделан или отложен

Готовность к 42.1 (админ-руководство) — что документировать

⚠️ Важные замечания
Reveal только Auditor+ — проверять роль, аудит обязателен

CSV injection — критично для security-продукта

Path traversal — fragment_path валидировать (не выходить за пределы)

Изображения с PII (category=person) — только Auditor+, если не замаскированы

Pillow — добавить в requirements.txt, проверить на тест-стеке

Hex-дамп — ASCII-часть маскировать, если PII

BOM в CSV — Excel-friendly, но проверить, что не ломает парсинг в скриптах

Content-Disposition — WebUI-прокси должен пробрасывать (иначе браузер не скачает)