"""
Единый формат событий аудита для DCAP System.

Используется:
- Windows-агент (audit-agent) → event_source="windows_agent"
- Linux-агент (audit-agent-linux) → event_source="linux_agent"
- Сканер (scanner) → event_source="scanner"

Manager API принимает события в этом формате.
"""

from typing import Optional, Dict, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class UnifiedEvent(BaseModel):
    """Единый формат событий для Windows и Linux-агентов"""

    event_type: Literal["read", "write", "delete", "move", "rename", "unknown"] = Field(
        ..., description="Тип события"
    )

    event_source: Literal["windows_agent", "linux_agent", "scanner"] = Field(
        ..., description="Источник события"
    )

    user: Optional[str] = Field(None, description="Пользователь, инициировавший событие")
    user_sid: Optional[str] = Field(None, description="SID пользователя (Windows)")

    file_path: str = Field(..., description="Путь к файлу")
    old_path: Optional[str] = Field(None, description="Старый путь (для move/rename)")

    source_host: Optional[str] = Field(None, description="Имя хоста-источника")

    metadata: Dict = Field(default_factory=dict, description="Дополнительные данные")

    created_at: Optional[str] = Field(None, description="Время события (ISO)")
