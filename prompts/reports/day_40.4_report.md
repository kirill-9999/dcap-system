# Отчёт — День 40.4 — Findings Refactor: Фрагменты + Экспорт (Этап 4, финал)

**Дата:** 12.09.2026
**Версия:** v3.12.0
**Ветка:** `feature/day_40.4_fragments_export`
**Предыдущая версия:** v3.11.0
**ТЗ:** `prompts/tz/day_40.4_fragments_export.md` → заархивировано в `prompts/archive/`

---

## 1. Цель дня

Завершить Findings Refactor:
- 🟡 **BACKLOG-058** — фрагменты изображений (bounding box) → PNG
- 🟢 **BACKLOG-059** — бинарные: hex-дамп
- 🟡 **BACKLOG-060** — экспорт с маскированием (CSV/JSON)
- 🟡 **BACKLOG-067** — X-Total-Count в list-ответе (сделан)

---

## 2. Что сделано

### 40.4.1 — Фрагменты (изображения + бинарные) ✅

- `GET /api/findings/{id}/fragment` (Viewer+):
  - `image_region` → PNG: готовый файл из `fragment_path` (если это PNG или нет `bounding_box`) или **crop на лету** через Pillow по `bounding_box` (`manager/src/core/image_fragment.py`), результат кэшируется рядом с исходником (`<name>_fragment_<id>.png`).
  - `?format=hex` (`byte_range`) → текстовый hex-дамп вокруг `byte_offset` с окном **±64 байта** (`manager/src/core/hex_dump.py`). Готовый `hex_preview` отдаётся как есть; иначе читается `fragment_path` с seek.
  - `text_line`/`text_context` → **400** (текст отдаётся в `GET /api/findings/{id}`).
  - `category=person` (PII без маски) → **403** для не-Auditor+.
  - 404 — если находка/файл отсутствует.
- WebUI `finding_detail.js`: для `image_region` — `<img src="/api/findings/{id}/fragment">` (`data-bbox`, fallback-текст при ошибке), для `byte_range` — `<pre class="finding-hex">` с hex_preview или подгрузкой `loadHexFragment()` (fetch `?format=hex`).
- CSS `.finding-image` / `.finding-hex` в `findings.css`.

**Реальное выполнение (не skip):** в БД тест-стека внесены 3 находки (text_line, image_region с jpg+bbox → crop ветка, byte_range с offset=0). Проверено live: `fragment(id=2)` → `200 image/png` + PNG-magic `\x89PNG\r\n\x1a\n` + `X-Bounding-Box`, crop-кэш создан (`frag_source_fragment_2.png`); `fragment(id=3)?format=hex` → `00000000 44 43 41 50... |DCAP-BINARY-SECR|`; `fragment(id=1)` → 400; аноним → 401.

### 40.4.2 — Экспорт (CSV/JSON) ✅

- `GET /api/findings/export?format=csv|json` (Auditor+):
  - По умолчанию **маскированное**; `?reveal=true` — расшифровка `match_text`/`line_text` из encrypted-колонок (**Auditor+**, иначе 403).
  - Фильтры: `status`, `finding_type`, `category`, `severity`, `task_id`, `resource_id` (legacy-маппинг категорий `pii/credentials/code` как в `list_findings`); `limit` до 100000.
  - **Аудит** в `audit_logs`: `event_type=findings_exported`, metadata: `{format, reveal, action: findings_exported_revealed|masked, count, filters}` (проверен live).
  - CSV: BOM `\ufeff`, `Content-Disposition: attachment`, `text/csv; charset=utf-8`, **CSV injection protection** (`manager/src/core/csv_utils.py`: префикс `'` для `= + - @ TAB CR`).
  - JSON: `ensure_ascii=False`, `indent=2`, даты — ISO.
- WebUI `findings.js` `showExportDialog()`: prompt формата (csv/json) + confirm reveal → `window.location.href=/api/findings/export?...` (браузер скачивает по `attachment`). Прокси `webui/api/routes.py` уже пробрасывал `Content-Disposition: attachment` через `StreamingResponse` (проверено live через :18001: PNG и CSV прошли).

### 40.4.3 — Пагинация: X-Total-Count ✅

- `GET /api/findings` теперь возвращает `Response` с заголовком `X-Total-Count` (общее число с учётом фильтров до offset/limit; datetime → ISO через `_json_default`).
- WebUI: `api.getWithMeta()` (новый метод в `api.js`, не меняет старый `get`), `findings.js` — пагинация с **номерами страниц** (окно 7), счётчик «Всего: N» (`#pagination-count` в `findings.html`).

### Общие правки

- `manager/requirements.txt` **не существует** — корневой `requirements.txt` уже содержит `Pillow>=10.0.0` (строка 41); в окружении установлен Pillow 11.1.0. Отдельный файл менеджера не заводил.
- `webui/api/routes.py` — правки **не потребовались** (catch-all `/api/*` + проброс attachment были готовы с 40.3).

---

## 3. Полный код файлов

### NEW `manager/src/core/hex_dump.py`

```python
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
```

### NEW `manager/src/core/image_fragment.py`

```python
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

    bounding_box: {"x", "y", "w", "h"}
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
```

### NEW `manager/src/core/csv_utils.py`

```python
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
```

### MODIFIED `manager/src/api/findings.py` — полный файл (705 строк)

```python
"""
API находок: список, детали, reveal, bulk, stats, FP.

Хранение: гибрид (masked + encrypted).
Расшифровка — только Auditor, с аудитом.
"""
import csv
import io
import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from manager.src.db.session import get_db
from manager.src.db.models import Finding
from manager.src.auth.models import User
from manager.src.auth.dependencies import (
    require_auth, require_auditor, require_admin, require_viewer
)
from manager.src.core.encryption import get_encryption
from manager.src.core.image_fragment import crop_image
from manager.src.core.hex_dump import format_hex_dump
from manager.src.core.csv_utils import sanitize_csv_cell
from manager.src.api.schemas_findings import (
    FindingResponse, FindingRevealResponse, FindingUpdateRequest,
    FindingBulkUpdateRequest, FindingBulkUpdateResponse,
    FindingStatsResponse, FalsePositiveResponse,
    CheckFingerprintsRequest, CheckFingerprintsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/findings", tags=["findings"])


def _json_default(o):
    """Сериализация datetime и пр. для HTTP-ответов (День 40.4)."""
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)


# ========== ВСПОМОГАТЕЛЬНЫЕ ==========

def _finding_to_response(
    finding: Finding,
    user: Optional[User] = None,
    reveal: bool = False,
) -> dict:
    """Преобразует Finding в ответ (masked или revealed)."""
    enc = get_encryption()

    can_reveal = bool(user and user.has_role("auditor")) or bool(
        user and user.has_role("admin")
    )

    data = {
        "id": finding.id,
        "resource_id": finding.resource_id,
        "task_id": finding.task_id,
        "finding_type": finding.finding_type,
        "category": finding.category,
        "severity": finding.severity,
        "fragment_type": finding.fragment_type,
        "line_number": finding.line_number,
        "match_text": finding.match_text_masked,
        "line_text": finding.line_text_masked,
        "context_before": finding.context_before_masked,
        "context_after": finding.context_after_masked,
        "has_fragment": bool(finding.fragment_path),
        "bounding_box": finding.bounding_box,
        "byte_offset": finding.byte_offset,
        "byte_length": finding.byte_length,
        "status": finding.status,
        "reviewed_by": finding.reviewed_by,
        "reviewed_at": finding.reviewed_at,
        "comment": finding.comment,
        "confidence": finding.confidence,
        "detector": finding.detector,
        "first_seen_at": finding.first_seen_at,
        "last_seen_at": finding.last_seen_at,
        "has_encrypted": bool(finding.match_text_encrypted or finding.line_text_encrypted),
        "can_reveal": can_reveal,
        # legacy-поля (backward compat с v3.8.0)
        "file_path": finding.fragment_path,
        "value": finding.match_text_masked,
    }

    # Reveal (только если явно запрошен и есть права)
    if reveal and can_reveal:
        if finding.match_text_encrypted:
            data["match_text"] = enc.decrypt(finding.match_text_encrypted)
        if finding.line_text_encrypted:
            data["line_text"] = enc.decrypt(finding.line_text_encrypted)

    return data


# ========== LIST / GET ==========

@router.get("", response_model=list[FindingResponse])
def list_findings(
    resource_id: Optional[int] = None,
    task_id: Optional[int] = None,
    status: Optional[str] = None,
    finding_type: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    order_by: str = Query("first_seen_at", pattern="^(first_seen_at|last_seen_at|severity|line_number)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Список находок (маскированное)."""
    q = db.query(Finding)

    if resource_id:
        q = q.filter(Finding.resource_id == resource_id)
    if task_id:
        q = q.filter(Finding.task_id == task_id)
    if status:
        q = q.filter(Finding.status == status)
    if finding_type:
        q = q.filter(Finding.finding_type == finding_type)
    if category:
        # legacy-backward compat: старые категории pii/credentials/code
        if category in ("pii", "credentials", "code"):
            q = q.filter(Finding.finding_type == category)
        else:
            q = q.filter(Finding.category == category)
    if severity:
        q = q.filter(Finding.severity == severity)

    col = getattr(Finding, order_by)
    q = q.order_by(desc(col) if order == "desc" else col)

    total = q.count()
    findings = q.offset(offset).limit(limit).all()
    payload = [_finding_to_response(f, user) for f in findings]
    return Response(
        content=json.dumps(payload, ensure_ascii=False, default=_json_default),
        media_type="application/json; charset=utf-8",
        headers={"X-Total-Count": str(total)},
    )


@router.get("/stats", response_model=FindingStatsResponse)
def get_stats(
    task_id: Optional[int] = None,
    resource_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Статистика по находкам."""
    q = db.query(Finding)
    if task_id:
        q = q.filter(Finding.task_id == task_id)
    if resource_id:
        q = q.filter(Finding.resource_id == resource_id)

    total = q.count()

    filters = []
    if task_id:
        filters.append(Finding.task_id == task_id)
    if resource_id:
        filters.append(Finding.resource_id == resource_id)

    def _group_counts(col, f):
        sub = db.query(col, func.count(Finding.id))
        for flt in filters:
            sub = sub.filter(flt)
        return dict(sub.group_by(col).all())

    by_status = _group_counts(Finding.status, filters)
    by_type = _group_counts(Finding.finding_type, filters)
    by_category = _group_counts(Finding.category, filters)
    by_severity = _group_counts(Finding.severity, filters)

    return {
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "by_category": by_category,
        "by_severity": by_severity,
    }


@router.get("/count")
def get_findings_count_legacy(
    category: Optional[str] = None,
    file_path: Optional[str] = None,
    scanner_id: Optional[int] = None,
    task_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Количество находок с фильтрацией (WebUI-формат, legacy)."""
    from manager.src.db.models import ScanTask
    q = db.query(Finding)
    if category:
        if category in ("pii", "credentials", "code"):
            q = q.filter(Finding.finding_type == category)
        else:
            q = q.filter(Finding.category == category)
    if file_path:
        q = q.filter(Finding.fragment_path.ilike(f"%{file_path}%"))
    if scanner_id:
        q = q.filter(
            Finding.task_id.in_(
                db.query(ScanTask.id).filter(ScanTask.scanner_id == scanner_id)
            )
        )
    if task_id:
        q = q.filter(Finding.task_id == task_id)
    return {"count": q.count()}


@router.get("/false-positives", response_model=list[FalsePositiveResponse])
def list_false_positives(
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Список ложных срабатываний (для аудита)."""
    findings = (
        db.query(Finding)
        .filter(Finding.status == "false_positive")
        .order_by(desc(Finding.reviewed_at))
        .offset(offset).limit(limit).all()
    )
    return [
        {
            "id": f.id,
            "resource_id": f.resource_id,
            "line_number": f.line_number,
            "match_text_masked": f.match_text_masked,
            "category": f.category,
            "finding_type": f.finding_type,
            "comment": f.comment,
            "reviewed_by": f.reviewed_by,
            "reviewed_at": f.reviewed_at,
        }
        for f in findings
    ]


# ========== EXPORT ==========

@router.get("/export")
async def export_findings(
    format: str = Query("csv", pattern="^(csv|json)$"),
    reveal: bool = Query(False),
    status: Optional[str] = None,
    finding_type: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    task_id: Optional[int] = None,
    resource_id: Optional[int] = None,
    limit: int = Query(10000, le=100000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auditor),
):
    """
    Экспорт находок.

    - format=csv|json (по умолчанию csv)
    - reveal=true → расшифровка (только Auditor+, с аудитом)
    - По умолчанию — маскированное
    """
    if reveal and not _is_auditor(current_user):
        raise HTTPException(403, "Reveal requires Auditor role")

    q = db.query(Finding)
    if status:
        q = q.filter(Finding.status == status)
    if finding_type:
        q = q.filter(Finding.finding_type == finding_type)
    if category:
        if category in ("pii", "credentials", "code"):
            q = q.filter(Finding.finding_type == category)
        else:
            q = q.filter(Finding.category == category)
    if severity:
        q = q.filter(Finding.severity == severity)
    if task_id:
        q = q.filter(Finding.task_id == task_id)
    if resource_id:
        q = q.filter(Finding.resource_id == resource_id)

    findings = q.order_by(desc(Finding.first_seen_at)).limit(limit).all()

    # Аудит
    _log_export(db, current_user, format, reveal, findings, {
        "status": status, "finding_type": finding_type,
        "category": category, "severity": severity,
        "task_id": task_id, "resource_id": resource_id,
    })

    if format == "csv":
        return _export_csv(findings, reveal)
    return _export_json(findings, reveal)


def _log_export(db, user, export_format, reveal, findings, filters):
    """Пишет запись в audit_logs (findings_exported)."""
    try:
        from manager.src.db.models import AuditLog
        log = AuditLog(
            event_type="findings_exported",
            event_source="api",
            user=user.username,
            file_path="/",
            metadata_json={
                "format": export_format,
                "reveal": reveal,
                "action": "findings_exported_revealed" if reveal else "findings_exported_masked",
                "count": len(findings),
                "filters": filters,
            },
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("Failed to log findings export: %s", e)
        db.rollback()


def _resolve_text(finding: Finding, field: str, reveal: bool) -> str:
    """masked → reveal при необходимости."""
    if reveal:
        encrypted = getattr(finding, f"{field}_encrypted", None)
        if encrypted:
            return get_encryption().decrypt(encrypted)
    return getattr(finding, f"{field}_masked", "") or ""


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


def _finding_to_export_dict(finding: Finding, reveal: bool) -> dict:
    return {
        "id": finding.id,
        "resource_id": finding.resource_id,
        "task_id": finding.task_id,
        "file_path": finding.fragment_path,
        "line_number": finding.line_number,
        "finding_type": finding.finding_type,
        "category": finding.category,
        "severity": finding.severity,
        "status": finding.status,
        "fragment_type": finding.fragment_type,
        "bounding_box": finding.bounding_box,
        "byte_offset": finding.byte_offset,
        "byte_length": finding.byte_length,
        "match_text": _resolve_text(finding, "match_text", reveal),
        "line_text": _resolve_text(finding, "line_text", reveal),
        "first_seen_at": finding.first_seen_at.isoformat() if finding.first_seen_at else None,
        "last_seen_at": finding.last_seen_at.isoformat() if finding.last_seen_at else None,
    }


def _export_json(findings, reveal: bool) -> Response:
    data = [_finding_to_export_dict(f, reveal) for f in findings]
    filename = f"findings_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{finding_id}", response_model=FindingResponse)
def get_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Детали находки (маскированное)."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")
    return _finding_to_response(finding, user)


# ========== FRAGMENT ==========

def _is_auditor(user: User) -> bool:
    """Права Auditor+ (расшифровка PII без маски)."""
    return bool(user and (user.has_role("auditor") or user.has_role("admin")))


@router.get("/{finding_id}/fragment")
async def get_finding_fragment(
    finding_id: int,
    format: str = Query("png", pattern="^(png|hex)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    """
    Вернуть фрагмент находки.

    - image_region → PNG (вырезанный или crop по bounding_box)
    - byte_range   → hex-дамп (format=hex)
    - text_line/text_context → 400 (текст отдаётся в /api/findings/{id})
    """
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    # PII без маски (person) — только Auditor+
    if finding.category == "person" and not _is_auditor(current_user):
        raise HTTPException(403, "Reveal required for this fragment")

    if finding.fragment_type == "image_region":
        return _get_image_fragment(finding)

    if finding.fragment_type == "byte_range":
        return _get_hex_fragment(finding)

    raise HTTPException(400, f"Fragment not available for type: {finding.fragment_type}")


def _get_image_fragment(finding: Finding) -> Response:
    """Отдать PNG-фрагмент (уже вырезанный или crop на лету)."""
    path = finding.fragment_path if finding.fragment_path else None

    if path and os.path.isfile(path):
        # A: файл уже вырезанного фрагмента (нет box / это PNG) — отдать напрямую
        if not finding.bounding_box or path.lower().endswith(".png"):
            with open(path, "rb") as f:
                data = f.read()
            return Response(
                content=data,
                media_type="image/png",
                headers={
                    "Content-Disposition": f'inline; filename="finding_{finding.id}.png"',
                    "X-Bounding-Box": json.dumps(finding.bounding_box or {}),
                },
            )
        # B: исходник + bounding_box — вырезаем через Pillow
        try:
            data = crop_image(path, finding.bounding_box)
        except Exception:
            logger.exception("Crop failed for finding %s", finding.id)
            raise HTTPException(404, "Fragment not available")
        # Кэшировать рядом с исходником
        cache_path = f"{os.path.splitext(path)[0]}_fragment_{finding.id}.png"
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "wb") as f:
                f.write(data)
        except Exception:
            logger.warning("Failed to cache fragment for finding %s", finding.id)
        return Response(
            content=data,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="finding_{finding.id}.png"',
                "X-Bounding-Box": json.dumps(finding.bounding_box or {}),
            },
        )

    raise HTTPException(404, "Fragment not available")


def _get_hex_fragment(finding: Finding, window: int = 64) -> Response:
    """Hex-дамп вокруг byte_offset."""
    if finding.hex_preview:
        return Response(
            content=finding.hex_preview,
            media_type="text/plain; charset=utf-8",
        )

    if not finding.fragment_path or not os.path.isfile(finding.fragment_path):
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


# ========== REVEAL ==========

@router.post("/{finding_id}/reveal", response_model=FindingRevealResponse)
def reveal_finding(
    finding_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """
    Расшифровка находки. Только Auditor+. Логируется в audit_logs.
    """
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    enc = get_encryption()

    try:
        match_text = enc.decrypt(finding.match_text_encrypted) if finding.match_text_encrypted else None
        line_text = enc.decrypt(finding.line_text_encrypted) if finding.line_text_encrypted else None
    except ValueError:
        raise HTTPException(500, "Decryption failed")

    revealed_at = datetime.utcnow()

    # Аудит
    _log_reveal(db, user, finding, revealed_at, request)

    return {
        "id": finding.id,
        "match_text": match_text or "",
        "line_text": line_text,
        "context_before": finding.context_before_masked,  # контекст только masked
        "context_after": finding.context_after_masked,
        "revealed_at": revealed_at,
        "revealed_by": user.username,
    }


def _log_reveal(db, user, finding, revealed_at, request):
    """Пишет запись в audit_logs."""
    try:
        from manager.src.db.models import AuditLog
        log = AuditLog(
            event_type="finding_reveal",
            event_source="api",
            user=user.username,
            file_path=finding.fragment_path or f"finding:{finding.id}",
            source_host=request.client.host if request.client else None,
            metadata_json={
                "finding_id": finding.id,
                "category": finding.category,
                "finding_type": finding.finding_type,
                "action": "finding_revealed",
            },
            created_at=revealed_at,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning("Failed to log reveal: %s", e)
        db.rollback()


# ========== UPDATE ==========

@router.patch("/{finding_id}", response_model=FindingResponse)
def update_finding(
    finding_id: int,
    body: FindingUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Обновить статус находки (confirmed / false_positive)."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    finding.status = body.status
    finding.comment = body.comment
    finding.reviewed_by = user.id
    finding.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(finding)

    return _finding_to_response(finding, user)


@router.post("/bulk", response_model=FindingBulkUpdateResponse)
def bulk_update(
    body: FindingBulkUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_auditor),
):
    """Массовое обновление статуса."""
    updated = 0
    skipped = 0
    errors = []

    findings = db.query(Finding).filter(Finding.id.in_(body.finding_ids)).all()
    found_ids = {f.id for f in findings}
    missing = set(body.finding_ids) - found_ids

    for f in findings:
        try:
            f.status = body.status
            f.comment = body.comment
            f.reviewed_by = user.id
            f.reviewed_at = datetime.utcnow()
            updated += 1
        except Exception as e:
            errors.append(f"Finding {f.id}: {e}")

    skipped = len(missing)
    for mid in missing:
        errors.append(f"Finding {mid}: not found")

    db.commit()
    return {"updated": updated, "skipped": skipped, "errors": errors}


# ========== DELETE ==========

@router.delete("/{finding_id}")
def delete_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Удалить находку (только Admin)."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(404, "Finding not found")

    # Удалить фрагмент (если есть)
    if finding.fragment_path:
        try:
            import os
            if os.path.exists(finding.fragment_path):
                os.remove(finding.fragment_path)
        except Exception as e:
            logger.warning("Failed to remove fragment: %s", e)

    db.delete(finding)
    db.commit()
    return {"deleted": finding_id}


# ========== CHECK FINGERPRINTS (для сканера) ==========

@router.post("/check-fingerprints", response_model=CheckFingerprintsResponse)
def check_fingerprints(
    body: CheckFingerprintsRequest,
    db: Session = Depends(get_db),
):
    """
    Проверка fingerprints перед отправкой находок (для сканера).
    Публичный (machine-эндпоинт, без JWT).
    """
    if not body.fingerprints:
        return {"false_positives": [], "confirmed": [], "new": []}

    existing = (
        db.query(Finding.fingerprint, Finding.status)
        .filter(Finding.fingerprint.in_(body.fingerprints))
        .all()
    )

    status_map = {fp: st for fp, st in existing}

    false_positives = [fp for fp in body.fingerprints if status_map.get(fp) == "false_positive"]
    confirmed = [fp for fp in body.fingerprints if status_map.get(fp) == "confirmed"]
    new = [fp for fp in body.fingerprints if fp not in status_map]

    return {
        "false_positives": false_positives,
        "confirmed": confirmed,
        "new": new,
    }
```

### MODIFIED `webui/static/js/api.js` — добавлен `getWithMeta`

```javascript
const api = {
    _headers() {
        const headers = { 'Content-Type': 'application/json' };
        if (typeof Auth !== 'undefined') Object.assign(headers, Auth.authHeaders());
        return headers;
    },

    async request(method, endpoint, data) {
        const opts = { method, headers: this._headers() };
        if (data !== undefined) opts.body = JSON.stringify(data);
        const r = await fetch(endpoint, opts);
        if (r.status === 401) {
            if (typeof Auth !== 'undefined') Auth.setToken(null);
            if (window.location.pathname !== '/login') window.location.href = '/login';
        }
        if (!r.ok) {
            const err = await r.json().catch(() => ({ detail: r.statusText || ('HTTP ' + r.status) }));
            throw new Error(err.detail || ('HTTP ' + r.status));
        }
        return r.json();
    },

    async get(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(k => {
            if (params[k] !== null && params[k] !== undefined && params[k] !== '')
                url.searchParams.append(k, params[k]);
        });
        return this.request('GET', url.toString());
    },

    /** GET с метаданными ответа (X-Total-Count), День 40.4. */
    async getWithMeta(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(k => {
            if (params[k] !== null && params[k] !== undefined && params[k] !== '')
                url.searchParams.append(k, params[k]);
        });
        const r = await fetch(url.toString(), { headers: this._headers() });
        if (r.status === 401) {
            if (typeof Auth !== 'undefined') Auth.setToken(null);
            if (window.location.pathname !== '/login') window.location.href = '/login';
        }
        if (!r.ok) {
            const err = await r.json().catch(() => ({ detail: r.statusText || ('HTTP ' + r.status) }));
            throw new Error(err.detail || ('HTTP ' + r.status));
        }
        const text = await r.text();
        let data = [];
        try { data = JSON.parse(text); } catch (e) { /* не JSON — вернём пусто */ }
        return { data, total: parseInt(r.headers.get('X-Total-Count') || '0', 10) };
    },

    async post(endpoint, data = {}) {
        return this.request('POST', endpoint, data);
    },
    async put(endpoint, data = {}) {
        return this.request('PUT', endpoint, data);
    },
    async patch(endpoint, data = {}) {
        return this.request('PATCH', endpoint, data);
    },
    async delete(endpoint) {
        return this.request('DELETE', endpoint);
    }
};

function showSuccess(msg) { showToast(msg, 'success'); }
function showError(msg) { showToast(msg, 'error'); }
function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}
```

### MODIFIED `webui/static/js/finding_detail.js` — изображения/hex (полный файл)

```javascript
/**
 * Детали находки: фрагмент, контекст, reveal, смена статуса (День 40.3).
 */
const FindingDetail = {
  finding: null,

  async init() {
    try {
      this.finding = await api.get(`/api/findings/${window.FINDING_ID}`);
      this.render();
    } catch (e) {
      document.getElementById('finding-detail').innerHTML =
        `<div class="alert alert-danger">Ошибка: ${escapeHtml(e.message)}</div>`;
    }
  },

  render() {
    const f = this.finding;
    const html = `
      <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
          <h4 class="mb-0">Находка #${f.id}</h4>
          <span class="badge bg-${this.statusColor(f.status)}">${escapeHtml(f.status)}</span>
        </div>
        <div class="card-body">
          <dl class="row">
            <dt class="col-sm-3">Файл</dt>
            <dd class="col-sm-9"><code>${escapeHtml(f.file_path || '—')}</code></dd>

            <dt class="col-sm-3">Строка</dt>
            <dd class="col-sm-9">${f.line_number || '—'}</dd>

            <dt class="col-sm-3">Тип / категория</dt>
            <dd class="col-sm-9">${escapeHtml(f.finding_type)} / ${escapeHtml(f.category || '—')}</dd>

            <dt class="col-sm-3">Severity</dt>
            <dd class="col-sm-9">${escapeHtml(f.severity)}</dd>

            <dt class="col-sm-3">Детектор</dt>
            <dd class="col-sm-9">${escapeHtml(f.detector || '—')} (confidence: ${f.confidence || '—'})</dd>

            <dt class="col-sm-3">Ресурс / задание</dt>
            <dd class="col-sm-9">#${f.resource_id || '—'} / #${f.task_id || '—'}</dd>

            <dt class="col-sm-3">Впервые замечено</dt>
            <dd class="col-sm-9">${f.first_seen_at ? new Date(f.first_seen_at).toLocaleString('ru-RU') : '—'}</dd>
          </dl>

          <h5>Фрагмент</h5>
          <pre class="bg-light p-3 finding-context" id="fragment">${this.renderFragment(f)}</pre>

          <div class="mt-3">
            ${f.can_reveal ? `<button class="btn btn-outline-primary" id="reveal-btn"><i class="fas fa-eye me-1"></i>Показать оригинал</button>` : ''}
          </div>
        </div>
        <div class="card-footer">
          <h5>Обработка</h5>
          <div class="mb-2">
            <textarea class="form-control" id="comment" placeholder="Комментарий (опционально)" rows="2">${escapeHtml(f.comment || '')}</textarea>
          </div>
          <button class="btn btn-success" id="confirm-btn"><i class="fas fa-check me-1"></i>Подтвердить</button>
          <button class="btn btn-danger" id="fp-btn"><i class="fas fa-times me-1"></i>Ложное срабатывание</button>
        </div>
      </div>
    `;
    document.getElementById('finding-detail').innerHTML = html;
    if (document.getElementById('hex-dump')) this.loadHexFragment();
    this.bindEvents();
  },

  async loadHexFragment() {
    const el = document.getElementById('hex-dump');
    if (!el) return;
    try {
      const r = await fetch(`/api/findings/${window.FINDING_ID}/fragment?format=hex`,
                            { headers: api._headers() });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      el.textContent = await r.text();
    } catch (e) {
      el.textContent = 'Ошибка загрузки: ' + e.message;
    }
  },

  renderFragment(f) {
    if (f.fragment_type === 'image_region') {
      return f.has_fragment || f.bounding_box
        ? `<img src="/api/findings/${f.id}/fragment"
                 class="img-fluid finding-image"
                 alt="Фрагмент находки #${f.id}"
                 data-bbox='${JSON.stringify(f.bounding_box || {})}'
                 onerror="this.style.display='none'; this.insertAdjacentHTML('afterend','<div class=\'alert alert-warning\'>Фрагмент недоступен</div>')">`
        : '<span class="text-muted">(изображение без вырезанного фрагмента)</span>';
    }
    if (f.fragment_type === 'byte_range') {
      return f.hex_preview
        ? `<pre class="finding-hex">${escapeHtml(f.hex_preview)}</pre>`
        : (f.has_fragment || f.byte_offset !== null && f.byte_offset !== undefined
            ? `<pre class="finding-hex" id="hex-dump">Загрузка…</pre>`
            : '<span class="text-muted">(hex-фрагмент недоступен)</span>');
    }
    const lines = [];
    if (f.context_before) lines.push(`<span class="text-muted">${escapeHtml(f.context_before)}</span>`);
    if (f.line_text) lines.push(`<mark>${escapeHtml(f.line_text)}</mark>`);
    if (f.context_after) lines.push(`<span class="text-muted">${escapeHtml(f.context_after)}</span>`);
    return lines.join('\n');
  },

  bindEvents() {
    const revealBtn = document.getElementById('reveal-btn');
    if (revealBtn) {
      revealBtn.addEventListener('click', async () => {
        try {
          const r = await api.post(`/api/findings/${window.FINDING_ID}/reveal`);
          document.getElementById('fragment').innerHTML =
            `<mark>${escapeHtml(r.line_text || '')}</mark>\n\nОригинал: ${escapeHtml(r.match_text)}`;
        } catch (e) {
          showError(e.message);
        }
      });
    }

    document.getElementById('confirm-btn').addEventListener('click', () => this.update('confirmed'));
    document.getElementById('fp-btn').addEventListener('click', () => this.update('false_positive'));
  },

  async update(status) {
    const comment = document.getElementById('comment').value;
    try {
      await api.patch(`/api/findings/${window.FINDING_ID}`, { status, comment });
      showSuccess('Сохранено');
      await this.init();
    } catch (e) {
      showError(e.message);
    }
  },

  statusColor(s) {
    return { new: 'primary', confirmed: 'success', false_positive: 'danger', archived: 'secondary' }[s] || 'secondary';
  },
};

document.addEventListener('DOMContentLoaded', () => FindingDetail.init());
```

### MODIFIED `webui/static/js/findings.js` — экспорт-диалог + пагинация по total (полный файл)

```javascript
/**
 * Находки: список, фильтры, пагинация, массовые операции (День 40.3).
 */
const FindingsPage = {
  page: 0,
  limit: 50,
  total: 0,
  selected: new Set(),
  findings: [],
  filters: {},

  async init() {
    this.limit = parseInt(new URLSearchParams(location.search).get('limit') || '50', 10);
    this.bindEvents();
    await this.load();
  },

  bindEvents() {
    document.getElementById('apply-filters').addEventListener('click', () => {
      this.page = 0;
      this.load();
    });

    document.getElementById('filter-status').addEventListener('change', () => { this.page = 0; this.load(); });
    document.getElementById('filter-type').addEventListener('change', () => { this.page = 0; this.load(); });
    document.getElementById('filter-severity').addEventListener('change', () => { this.page = 0; this.load(); });

    document.getElementById('bulk-confirm').addEventListener('click', () => this.bulkUpdate('confirmed'));
    document.getElementById('bulk-fp').addEventListener('click', () => this.bulkUpdate('false_positive'));
    document.getElementById('bulk-clear').addEventListener('click', () => {
      this.selected.clear();
      this.render();
    });

    document.getElementById('export-btn').addEventListener('click', () => this.showExportDialog());
  },

  collectFilters() {
    return {
      status: document.getElementById('filter-status').value,
      finding_type: document.getElementById('filter-type').value,
      category: document.getElementById('filter-category').value,
      severity: document.getElementById('filter-severity').value,
      task_id: document.getElementById('filter-task').value,
    };
  },

  async load() {
    const params = {
      ...this.collectFilters(),
      limit: this.limit,
      offset: this.page * this.limit,
      order_by: 'first_seen_at',
      order: 'desc',
    };

    try {
      const r = await api.getWithMeta('/api/findings', params);
      this.findings = Array.isArray(r.data) ? r.data : [];
      this.total = r.total || 0;
      this.render();
    } catch (e) {
      document.getElementById('findings-list').innerHTML =
        `<div class="alert alert-danger">Не удалось загрузить находки: ${escapeHtml(e.message)}</div>`;
    }
  },

  render() {
    const list = document.getElementById('findings-list');
    if (!this.findings || this.findings.length === 0) {
      list.innerHTML = '<div class="alert alert-info">Находок не найдено</div>';
      this.renderPagination(false, 0);
      this.updateBulkBar();
      return;
    }

    list.innerHTML = this.findings.map(f => this.renderItem(f)).join('');
    this.renderPagination(this.findings.length >= this.limit, this.total);
    this.updateBulkBar();

    list.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = btn.dataset.action;
        const id = parseInt(btn.dataset.id, 10);
        this.handleAction(action, id);
      });
    });

    list.querySelectorAll('.finding-checkbox').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const id = parseInt(cb.dataset.id, 10);
        if (cb.checked) this.selected.add(id);
        else this.selected.delete(id);
        this.updateBulkBar();
      });
    });

    list.querySelectorAll('.finding-row').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.type === 'checkbox' || e.target.dataset.action) return;
        window.location.href = `/findings/${row.dataset.id}`;
      });
    });
  },

  renderPagination(hasMore, total) {
    const wrap = document.getElementById('pagination-wrap');
    const ul = document.getElementById('pagination');
    const totalPages = Math.max(1, Math.ceil((total || 0) / this.limit));
    if (this.page === 0 && !hasMore && totalPages <= 1) { wrap.style.display = 'none'; return; }
    wrap.style.display = 'block';
    ul.innerHTML = '';

    const mkItem = (label, pageIdx, active, disabled, onClick) => {
      const li = document.createElement('li');
      li.className = 'page-item' + (active ? ' active' : '') + (disabled ? ' disabled' : '');
      if (active) li.innerHTML = `<span class="page-link">${label}</span>`;
      else {
        li.innerHTML = `<a class="page-link" href="#">${label}</a>`;
        li.addEventListener('click', (e) => { e.preventDefault(); if (!disabled) onClick(pageIdx); });
      }
      ul.appendChild(li);
    };

    mkItem('« Назад', this.page - 1, false, this.page === 0, (p) => { this.page = p; this.load(); });

    // Окно из номеров страниц (максимум 7)
    const win = 7;
    let start = Math.max(0, this.page - Math.floor(win / 2));
    let end = Math.min(totalPages - 1, start + win - 1);
    start = Math.max(0, end - win + 1);
    for (let p = start; p <= end; p++) {
      mkItem(String(p + 1), p, p === this.page, false, (idx) => { this.page = idx; this.load(); });
    }

    mkItem('Вперёд »', this.page + 1, false, this.page >= totalPages - 1, (p) => { this.page = p; this.load(); });

    const count = document.getElementById('pagination-count');
    if (count) count.textContent = `Всего: ${total}`;
  },

  renderItem(f) {
    const statusBadge = {
      new: '<span class="badge bg-primary">🆕 new</span>',
      confirmed: '<span class="badge bg-success">✅ confirmed</span>',
      false_positive: '<span class="badge bg-danger">❌ false_positive</span>',
      archived: '<span class="badge bg-secondary">📦 archived</span>',
    }[f.status] || escapeHtml(f.status);

    const typeBadge = {
      pii: '<span class="badge bg-info text-dark">PII</span>',
      credentials: '<span class="badge bg-warning text-dark">Cred</span>',
      code: '<span class="badge bg-secondary">Code</span>',
    }[f.finding_type] || escapeHtml(f.finding_type);

    const severityClass = {
      critical: 'danger', high: 'warning', medium: 'info', low: 'secondary',
    }[f.severity] || 'secondary';

    const lineInfo = f.line_number
      ? `${f.file_path || 'файл'}:${f.line_number}`
      : (f.file_path || '—');

    return `
      <div class="card mb-2 finding-row" data-id="${f.id}">
        <div class="card-body py-2">
          <div class="d-flex align-items-start">
            <input type="checkbox" class="form-check-input me-2 finding-checkbox"
                   data-id="${f.id}" ${this.selected.has(f.id) ? 'checked' : ''}>
            <div class="flex-grow-1">
              <div class="d-flex flex-wrap justify-content-between align-items-center">
                <div>
                  <span class="finding-id">#${f.id}</span>
                  <code class="text-muted small">${escapeHtml(lineInfo)}</code>
                  <span class="ms-2">${typeBadge}</span>
                  <span class="badge bg-${severityClass}">${escapeHtml(f.severity)}</span>
                  <span class="badge bg-light text-dark">${escapeHtml(f.category)}</span>
                </div>
                <div>${statusBadge}</div>
              </div>
              <div class="mt-1">
                <code class="finding-match">${escapeHtml(f.match_text || '(masked)')}</code>
              </div>
              ${f.context_before ? `
                <details class="mt-1">
                  <summary class="small text-muted">Контекст</summary>
                  <pre class="small bg-light p-2 finding-context">${escapeHtml(f.context_before)}\n${escapeHtml(f.line_text || '')}\n${escapeHtml(f.context_after || '')}</pre>
                </details>
              ` : ''}
              <div class="mt-2">
                ${f.status === 'new' ? `
                  <button class="btn btn-sm btn-success" data-action="confirm" data-id="${f.id}" title="Подтвердить">✅</button>
                  <button class="btn btn-sm btn-danger" data-action="fp" data-id="${f.id}" title="Ложное">❌</button>
                ` : ''}
                ${f.can_reveal ? `
                  <button class="btn btn-sm btn-outline-primary" data-action="reveal" data-id="${f.id}" title="Показать оригинал">👁️ Reveal</button>
                ` : ''}
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  },

  async handleAction(action, id) {
    try {
      if (action === 'confirm') {
        await api.patch(`/api/findings/${id}`, { status: 'confirmed' });
        showSuccess('Подтверждено');
      } else if (action === 'fp') {
        await api.patch(`/api/findings/${id}`, { status: 'false_positive' });
        showSuccess('Помечено как ложное');
      } else if (action === 'reveal') {
        const r = await api.post(`/api/findings/${id}/reveal`);
        alert(`Оригинал:\n${r.match_text}\n\nСтрока:\n${r.line_text || '(нет)'}`);
      }
      await this.load();
    } catch (e) {
      showError(e.message);
    }
  },

  async bulkUpdate(status) {
    if (this.selected.size === 0) return;
    if (!confirm(`Обновить ${this.selected.size} находок на статус "${status}"?`)) return;

    try {
      const r = await api.post('/api/findings/bulk', {
        finding_ids: [...this.selected],
        status,
      });
      showSuccess(`Обновлено: ${r.updated}, пропущено: ${r.skipped}`);
      this.selected.clear();
      await this.load();
    } catch (e) {
      showError(e.message);
    }
  },

  showExportDialog() {
    const fmt = prompt('Формат экспорта (csv/json):', 'csv');
    if (!fmt || !['csv', 'json'].includes(fmt)) return;

    const reveal = confirm('Показать оригиналы (только Auditor+)?\n\nOK = reveal, Отмена = masked');

    const params = new URLSearchParams({
      ...this.collectFilters(),
      format: fmt,
      reveal: reveal ? 'true' : 'false',
    });
    // Убрать пустые
    for (const [k, v] of [...params.entries()]) {
      if (!v || v === 'false') params.delete(k);
    }
    window.location.href = `/api/findings/export?${params}`;
  },

  updateBulkBar() {
    const bar = document.getElementById('bulk-actions');
    const count = this.selected.size;
    document.getElementById('selected-count').textContent = count;
    bar.style.display = count > 0 ? 'block' : 'none';
  },
};

document.addEventListener('DOMContentLoaded', () => FindingsPage.init());
```

### MODIFIED `webui/static/css/findings.css` — дополнения

```css
/* Фрагменты изображений и hex-дампы (День 40.4). */
.finding-image {
    max-width: 100%;
    border: 1px solid #dee2e6;
    border-radius: 4px;
}

.finding-hex {
    font-family: var(--font-mono, ui-monospace, SFMono-Regular, Consolas, monospace);
    font-size: 12px;
    line-height: 1.4;
    white-space: pre;
    overflow-x: auto;
}
```

### MODIFIED `webui/templates/findings.html` — счётчик пагинации

```html
<nav class="mt-3" id="pagination-wrap" style="display:none;">
    <p class="text-center text-muted small mb-1" id="pagination-count">Всего: 0</p>
    <ul class="pagination justify-content-center" id="pagination"></ul>
  </nav>
```

### NEW `tests/unit/test_hex_dump.py`

```python
"""Unit-тесты hex-дампа (День 40.4)."""
import pytest

pytestmark = pytest.mark.unit

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


def test_hex_dump_empty():
    assert format_hex_dump(b"") == ""
```

### NEW `tests/unit/test_csv_utils.py`

```python
"""Unit-тесты CSV-утилит: защита от CSV injection (День 40.4)."""
import pytest

pytestmark = pytest.mark.unit

from manager.src.core.csv_utils import sanitize_csv_cell


def test_excel_formula_prefixed():
    assert sanitize_csv_cell("=cmd|' /C calc'!A0").startswith("'=")


def test_plus_prefixed():
    assert sanitize_csv_cell("+1234").startswith("'+")


def test_at_prefixed():
    assert sanitize_csv_cell("@SUM(1)").startswith("'@")


def test_hyphen_prefixed():
    assert sanitize_csv_cell("-1+2").startswith("'-")


def test_tab_prefixed():
    assert sanitize_csv_cell("\t=SUM(1)").startswith("'\t")


def test_normal_unchanged():
    assert sanitize_csv_cell("normal value") == "normal value"


def test_empty_unchanged():
    assert sanitize_csv_cell("") == ""
```

### NEW `tests/e2e/test_finding_fragments.py`

```python
"""E2E-тесты фрагментов находок (День 40.4)."""
import pytest
import requests

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


def _find_fragment_id(api_client, manager_url, fragment_type, with_hex=False):
    """Ищет находку нужного fragment_type в /api/findings (admin)."""
    r = api_client.get(f"{manager_url}/api/findings", params={"limit": 1000}, timeout=10)
    if r.status_code != 200:
        return None
    for f in r.json() or []:
        if f.get("fragment_type") != fragment_type:
            continue
        if with_hex and not f.get("hex_preview") and not (f.get("has_fragment") and f.get("byte_offset") is not None):
            continue
        return f["id"]
    return None


def test_image_region_fragment(manager_url, api_client):
    """image_region → PNG."""
    fid = _find_fragment_id(api_client, manager_url, "image_region")
    if fid is None:
        pytest.skip("No image_region finding in test data")
    r = api_client.get(f"{manager_url}/api/findings/{fid}/fragment")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_byte_range_hex(manager_url, api_client):
    """byte_range → hex-дамп."""
    fid = _find_fragment_id(api_client, manager_url, "byte_range", with_hex=True)
    if fid is None:
        pytest.skip("No byte_range finding in test data")
    r = api_client.get(f"{manager_url}/api/findings/{fid}/fragment?format=hex")
    assert r.status_code == 200
    assert "00000000" in r.text or "|" in r.text


def test_text_fragment_rejected(manager_url, api_client):
    """text_line → 400."""
    fid = _find_fragment_id(api_client, manager_url, "text_line")
    if fid is None:
        pytest.skip("No text_line finding")
    r = api_client.get(f"{manager_url}/api/findings/{fid}/fragment")
    assert r.status_code == 400


def test_fragment_requires_auth(manager_url):
    """Без токена → 401."""
    r = requests.get(f"{manager_url}/api/findings/1/fragment", timeout=5)
    assert r.status_code == 401
```

### NEW `tests/e2e/test_findings_export.py`

```python
"""E2E-тесты экспорта находок (День 40.4)."""
import csv
import io
import pytest
import requests

from fixtures.auth import login

pytestmark = [pytest.mark.e2e, pytest.mark.requires_manager]


@pytest.fixture
def viewer_client(manager_url):
    """Сессия под viewer-пользователем (создаётся через admin при необходимости)."""
    username, password = "e2e_viewer", "viewer12345"
    admin = login(manager_url)
    r = admin.get(f"{manager_url}/api/auth/users", params={"search": username}, timeout=10)
    exists = (r.status_code == 200 and any(
        u.get("username") == username for u in (r.json() or {}).get("items", [])
    ))
    if not exists:
        r = admin.post(f"{manager_url}/api/auth/users", timeout=10, json={
            "username": username,
            "password": password,
            "full_name": "E2E Viewer",
            "auth_source": "local",
            "is_active": True,
            "roles": ["viewer"],
        })
        if r.status_code not in (200, 201, 400):
            raise RuntimeError(f"create viewer user: {r.status_code} {r.text}")
    admin.close()

    session = login(manager_url, username=username, password=password)
    yield session
    session.close()


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
```

---

## 4. Тестирование

| Группа | Команда | Результат |
|--------|--------|-----------|
| Новые unit+e2e | `pytest tests/unit/test_hex_dump.py tests/unit/test_csv_utils.py tests/e2e/test_finding_fragments.py tests/e2e/test_findings_export.py` | **20 passed** |
| Все unit | `pytest tests/unit` | **50 passed** |
| WebUI regression | `pytest tests/e2e/test_webui_findings.py tests/e2e/test_webui_proxy.py` | **8 passed** |
| Полный e2e | `pytest tests/e2e -m "e2e and not requires_scanner and not requires_docker"` | **30 passed, 4 deselected** |

Дополнительно:
- `py_compile` всех py-файлов (включая тесты) — OK; `node --check` 3 JS-файлов — OK.
- Live-проверка API (тест-стек :18000): PNG-magic фрагмента, hex `00000000 44 43 41 50...`, 400 для text, 401 аноним, CSV BOM + `attachment`, JSON список, `X-Total-Count: 3`, WebUI-прокси PNG и CSV.
- Аудит распискрытия: `audit_logs` → `event_type=findings_exported`, metadata `action=findings_exported_revealed`, `count`, `filters`.
- Тест-стек: Manager uvicorn :18000 (env `AUTH_LOGIN_MAX_ATTEMPTS=1000`, `DATABASE_URL=sqlite:///e:/Temp/opencode/dcapstack/manager_test.db`, конфиг `config_highlimit.json`), WebUI :18001.

**Найден и исправлен баг при разработке:** первый вариант `_log_export` писал `file_path=None`, а колонка `audit_logs.file_path` имеет `nullable=False` → запись молча откатывалась. Исправлено на `file_path="/"`. После фикса аудит проверен live (`findings_exported_revealed` присутствует).

---

## 5. Отклонения от ТЗ (выполнено иначе)

1. **Crop fallback (40.4.1):** в ТЗ `crop_image(finding.bounding_box)` не передаёт путь к исходнику. В модели нет отдельного поля «путь к исходному изображению» (есть только `fragment_path`). Реализовано: `crop_image(path, finding.bounding_box)` — `fragment_path` используется и как исходник (jpg/gif и т.п. + bbox → crop на лету с кэшем `<name>_fragment_<id>.png`), и как уже вырезанный PNG (нет bbox или расширение .png → отдаётся как есть). Path traversal: читается только `os.path.isfile` реальных путей из БД (никто из клиентов не передаёт пути), url-параметров нет.
2. **`fragment` эндпоинт — `async`:** сигнатуры `_get_image_fragment`/`_get_hex_fragment` обычные (sync), т.к. реального I/O-асинка нет — поведение то же.
3. **Тесты фрагментов:** не жёсткий `id=1`, а поиск находки нужного `fragment_type` в `GET /api/findings`; при отсутствии данных — `skip` (как и в ТЗ). Для реального покрытия в БД тест-стека внесены тестовые находки (seed-скрипт в `e:\Temp\opencode\dcapstack\seed_fragments.py`, в репо не входит).
4. **`viewer_client`:** глобальной фикстуры нет; создана локально в `test_findings_export.py` (создание пользователя `e2e_viewer` через admin API при отсутствии, idempotent).
5. **Добавлен unit-тест `tests/unit/test_csv_utils.py`** (CSV injection — значимо для security; в ТЗ тест лежал в e2e, сохранил и там `test_csv_injection_sanitized`).
6. **ROADMAP.md / ARCHITECTURE.md** — не правились/не коммитились (файлы архитектора, в репо есть их незакоммиченные правки пользователя; правило «stage only day files»). Отмечено ниже для архитектора. CHANGELOG.md создан (в репо его не было).
7. **X-Total-Count:** `list_findings` переведён с `response_model=list[FindingResponse]` на ручной `Response` (`_json_default` → ISO-даты). Контракт JS/JSON не изменён (было проверено полным e2e).

---

## 6. Обратная связь архитектору

- **Что заработало / что нет — по под-дням:** 40.4.1 ✅ (PNG и hex; изображение показывается через `<img>`, hex через `<pre>` + ленивая загрузка). 40.4.2 ✅ (CSV/JSON, masked/reveal, BOM, attachment, CSV-injection, аудит). 40.4.3 ✅ (X-Total-Count + пагинация с номерами). Ничего не отложено.
- **Фикстуры для фрагментов:** тестовые `image_region`/`byte_range`/`text_line` внесены в БД тест-стека seed-скриптом (temp, не в репо). E2E-тесты ищут находки по `fragment_type` через API и **skip**, если данных нет (как в ТЗ); на тест-стеке все 9 новых тестов прошли **не** как skip.
- **Pillow:** уже был в корневом `requirements.txt` (`Pillow>=10.0.0`); в окружении 11.1.0. Проблем с установкой не было. `manager/requirements.txt` не существует — он в ТЗ указан ошибочно (корневой `requirements.txt` покрывает).
- **Экспорт — производительность:** на 3 находках мгновенно; на 10k оценка ~0.1–0.3 с (линейная выборка + StringIO, `limit` до 100000). Измерения на реальном 10k не проводил (для 42.4 можно добавить нагрузочный кейс).
- **Reveal в экспорте — аудит проверен:** `audit_logs.event_type=findings_exported`, `metadata.action=findings_exported_revealed`, `count`, `filters`. Есть и masked-вариант (`findings_exported_masked`).
- **BACKLOG-067 — сделан.**
- **Готовность к 42.1 (админ-руководство):** в `docs/deployment.md` добавлен раздел «Фрагменты и экспорт находок (День 40.4)»; для docs/admin-guide стоит документировать: эндпоинты `fragment`/`export`, поведение reveal и аудит, CSV-injection, X-Total-Count, `Pillow` в зависимостях, тест-данные фрагментов.
- **Прошу обработать:** ROADMAP.md (День 40.4 ✅, BACKLOG-058/059/060/067 ✅, статистика 25/35→28/35, 52/86→55/86) и ARCHITECTURE.md (таблица API находок: fragment/export; раздел «Типы фрагментов» с примерами ответов) — файлы архитектора, я их не редактировал по установленному правилу.

---

## 7. Команда коммита

```bash
git add STATE.md docs/deployment.md CHANGELOG.md
git add manager/src/api/findings.py manager/src/core/image_fragment.py manager/src/core/hex_dump.py manager/src/core/csv_utils.py
git add webui/static/js/api.js webui/static/js/finding_detail.js webui/static/js/findings.js
git add webui/static/css/findings.css webui/templates/findings.html
git add tests/unit/test_hex_dump.py tests/unit/test_csv_utils.py
git add tests/e2e/test_finding_fragments.py tests/e2e/test_findings_export.py
git add prompts/archive/day_40.4_fragments_export.md
git commit -m "feat: День 40.4 — Findings Refactor: Фрагменты + Экспорт (v3.12.0)

BACKLOG-058 — Фрагменты изображений (bounding box):
- GET /api/findings/{id}/fragment → PNG (crop по bounding_box через Pillow, кэш)
- manager/src/core/image_fragment.py; X-Bounding-Box; person → Auditor+

BACKLOG-059 — Hex-дамп бинарных:
- ?format=hex → hex-дамп вокруг byte_offset (окно ±64 байта)
- manager/src/core/hex_dump.py; hex_preview отдаётся как есть

BACKLOG-060 — Экспорт с маскированием:
- GET /api/findings/export?format=csv|json (Auditor+)
- masked по умолчанию, reveal (Auditor+) с аудитом findings_exported
- CSV injection protection (csv_utils.py), BOM, Content-Disposition: attachment

BACKLOG-067 — X-Total-Count в /api/findings + пагинация с номерами в WebUI

WebUI:
- finding_detail.js: <img> для image_region, <pre> для byte_range (+loadHexFragment)
- findings.js: кнопка «Экспорт» (диалог csv/json + reveal), renderPagination(total)
- api.js: getWithMeta; findings.css: стили; findings.html: счётчик

Тесты:
- tests/e2e/test_finding_fragments.py, test_findings_export.py
- tests/unit/test_hex_dump.py, test_csv_utils.py

Docs:
- STATE.md → v3.12.0; docs/deployment.md; CHANGELOG.md (v3.12.0)"
```

---

## 8. Инструкция по ручному тестированию

```powershell
# 1. Запуск стека (из корня репо)
python init_db.py
python run_all.py                      # Manager :8000 + WebUI :8001

# 2. Вход и получение токена
# WebUI: http://127.0.0.1:8001 → admin/admin123
$TOKEN = (curl -s -X POST http://127.0.0.1:8000/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"admin","password":"admin123"}' | ConvertFrom-Json).access_token

# 3. Фрагмент изображения (если есть image_region находка)
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/findings/2/fragment -o fragment.png
# → PNG; рядом с исходником появится <name>_fragment_<id>.png (кэш crop)

# 4. Hex-дамп бинарного фрагмента
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/findings/3/fragment?format=hex"
# → 00000000  44 43 41 50 2d 42 49 4e ...

# 5. Экспорт CSV (masked, скачает файл)
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/findings/export?format=csv" -o findings.csv
# Экспорт JSON + reveal (Auditor+): .../export?format=json&reveal=true

# 6. WebUI
# /findings → кнопка «Экспорт» (спросит csv/json и reveal)
# /findings/{id} → для image_region/byte_range покажется <img>/<pre>

# 7. Тесты
pytest tests/unit tests/e2e/test_finding_fragments.py tests/e2e/test_findings_export.py -v
```