"""Pydantic-схемы для API находок."""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


FindingStatus = Literal["new", "confirmed", "false_positive", "archived"]
FragmentType = Literal["text_line", "text_context", "image_region", "byte_range"]


class FindingResponse(BaseModel):
    """Находка в ответе API (маскированное)."""
    id: int
    resource_id: int
    task_id: Optional[int] = None

    finding_type: str
    category: str
    severity: str

    fragment_type: str
    line_number: Optional[int] = None
    match_text: Optional[str] = None          # masked
    line_text: Optional[str] = None           # masked
    context_before: Optional[str] = None
    context_after: Optional[str] = None

    # Не-текстовые
    has_fragment: bool = False
    bounding_box: Optional[dict] = None
    byte_offset: Optional[int] = None
    byte_length: Optional[int] = None

    # legacy-поля (backward compat с v3.8.0, WebUI)
    file_path: Optional[str] = None
    value: Optional[str] = None

    # Статус
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    comment: Optional[str] = None

    # Метаданные
    confidence: Optional[float] = None
    detector: Optional[str] = None

    first_seen_at: datetime
    last_seen_at: datetime

    # Возможности
    has_encrypted: bool = False
    can_reveal: bool = False
    encryption_key_id: Optional[str] = None

    class Config:
        from_attributes = True


class FindingRevealResponse(BaseModel):
    """Ответ на reveal (расшифровка)."""
    id: int
    match_text: str
    line_text: Optional[str] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    revealed_at: datetime
    revealed_by: str


class FindingUpdateRequest(BaseModel):
    """Обновление статуса находки."""
    status: FindingStatus
    comment: Optional[str] = None


class FindingBulkUpdateRequest(BaseModel):
    """Массовое обновление."""
    finding_ids: list[int] = Field(..., min_length=1, max_length=1000)
    status: FindingStatus
    comment: Optional[str] = None


class FindingBulkUpdateResponse(BaseModel):
    updated: int
    skipped: int
    errors: list[str] = []


class FindingStatsResponse(BaseModel):
    """Статистика по находкам."""
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_category: dict[str, int]
    by_severity: dict[str, int]


class FalsePositiveResponse(BaseModel):
    """Ложное срабатывание (для аудита)."""
    id: int
    resource_id: int
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    match_text_masked: Optional[str] = None
    category: str
    finding_type: str
    comment: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_by_username: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class CheckFingerprintsRequest(BaseModel):
    """Проверка fingerprints (для сканера)."""
    fingerprints: list[str] = Field(..., max_length=10000)


class CheckFingerprintsResponse(BaseModel):
    """Результат проверки."""
    false_positives: list[str] = []
    confirmed: list[str] = []
    new: list[str] = []