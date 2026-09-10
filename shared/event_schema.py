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


# Категории находок сканера (день 34.5).
# Находки передаются в metadata["findings"][*]["subcategory"].
SCANNER_CREDENTIAL_SUBCATEGORIES = [
    "CRED_API_KEY",
    "CRED_AWS_ACCESS_KEY",
    "CRED_AWS_SECRET_KEY",
    "CRED_JWT_TOKEN",
    "CRED_PASSWORD",
    "CRED_DATABASE_URL",
    "CRED_SSH_PRIVATE_KEY",
    "CRED_GITHUB_TOKEN",
    "CRED_GITHUB_TOKEN_OLD",
    "CRED_SLACK_TOKEN",
    "CRED_DISCORD_TOKEN",
    "CRED_GENERIC_TOKEN",
    "CRED_GENERIC_SECRET",
    "CRED_BEARER_TOKEN",
    "CRED_BASIC_AUTH",
    "CRED_HIGH_ENTROPY",
    "CRED_SSH_PRIVATE_KEY",
    "CRED_POSTGRES_PASSWORD",
    "CRED_NETRC_CREDENTIALS",
    "CRED_KUBECONFIG",
    "CRED_JAAS_CREDENTIALS",
    "CRED_SECRETS_FILE",
    "CRED_ENV_FILE",
    "CRED_HTPASSWD_CREDENTIALS",
    "CRED_PASSWD_FILE",
    "CRED_SHADOW_FILE",
]


class UnifiedEvent(BaseModel):
    """Единый формат событий для Windows и Linux-агентов"""

    event_type: Literal["read", "write", "delete", "move", "rename", "unknown"] = Field(
        ..., description="Тип события"
    )

    event_source: Literal["windows_agent", "linux_agent", "scanner", "s3_agent"] = Field(
        ..., description="Источник события"
    )

    user: Optional[str] = Field(None, description="Пользователь, инициировавший событие")
    user_sid: Optional[str] = Field(None, description="SID пользователя (Windows)")

    file_path: str = Field(..., description="Путь к файлу")
    old_path: Optional[str] = Field(None, description="Старый путь (для move/rename)")

    source_host: Optional[str] = Field(None, description="Имя хоста-источника")

    metadata: Dict = Field(default_factory=dict, description="Дополнительные данные")

    created_at: Optional[str] = Field(None, description="Время события (ISO)")
