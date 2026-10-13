# manager/src/api/schemas_audit.py
"""Pydantic-схемы аудита (BUG-223, v3.13.39)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogDetail(BaseModel):
    """Полное аудит-событие (включая metadata_json).

    BUG-223 (v3.13.39): GET /api/audit/{id} раньше отсутствовал, содержимое
    metadata_json конкретного события нельзя было прочитать из WebUI/SIEM.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: Optional[int] = None
    event_type: str
    event_source: Optional[str] = None
    user: Optional[str] = None
    user_sid: Optional[str] = None
    file_path: str
    old_path: Optional[str] = None
    source_host: Optional[str] = None
    metadata_json: Optional[dict] = None
    created_at: Optional[datetime] = None