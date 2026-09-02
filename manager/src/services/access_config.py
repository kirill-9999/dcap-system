# manager/src/services/access_config.py

from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ADConfig(BaseModel):
    """Конфигурация подключения к Active Directory (День 33)"""
    
    server: str = Field(default="localhost", description="Адрес контроллера домена")
    domain: str = Field(default="SAMDOM", description="NETBIOS-домен")
    base_dn: Optional[str] = Field(
        default=None,
        description="Базовый DN (например, DC=SAMDOM,DC=EXAMPLE,DC=COM)"
    )
    username: Optional[str] = Field(
        default=None, description="Имя служебной учётной записи"
    )
    password: Optional[str] = Field(
        default=None, description="Пароль служебной учётной записи (env)"
    )
    use_ssl: bool = Field(default=False, description="Использовать LDAPS")
    ldap_port: int = Field(default=389, description="Порт LDAP (636 для LDAPS)")
    timeout: int = Field(default=10, description="Таймаут подключения (сек)")
    cache_ttl: int = Field(default=300, description="TTL кэша AD-запросов (сек)")
    redis_url: Optional[str] = Field(default=None, description="URL Redis для кэша")


class AccessConfig(BaseModel):
    """Конфигурация модуля управления доступом"""
    
    # Режим сбора прав: local, ad, mixed или remote
    mode: Literal["local", "remote", "ad", "mixed"] = Field(
        default="local",
        description="Режим сбора прав: local, ad, mixed или remote (через Scanner)"
    )
    
    # Настройки для удаленного режима
    scanner_endpoint: Optional[str] = Field(
        default=None,
        description="Endpoint Scanner для сбора прав (например, http://scanner:8000)"
    )
    
    # Таймауты
    timeout_seconds: int = Field(
        default=30,
        description="Таймаут для сбора прав"
    )
    
    # Параметры анализа
    excessive_days_threshold: int = Field(
        default=90,
        description="Количество дней без проверки для определения 'orphaned' прав"
    )
    
    # Включение/отключение
    alerts_enabled: bool = Field(
        default=True,
        description="Включить генерацию алертов"
    )
    
    auto_sync_on_scan: bool = Field(
        default=True,
        description="Автоматическая синхронизация прав при запуске сканирования"
    )
    
    # Настройки Active Directory (используются в режимах ad/mixed)
    ad: ADConfig = Field(default_factory=ADConfig, description="Настройки AD")


def load_access_config(config_path: Optional[Path] = None) -> AccessConfig:
    """
    Загрузить конфигурацию из файла или использовать значения по умолчанию
    
    Args:
        config_path: Путь к JSON-файлу конфигурации
    
    Returns:
        AccessConfig
    """
    if config_path and config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return AccessConfig(**data.get("access_management", {}))
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
    
    return AccessConfig()


def get_access_config() -> AccessConfig:
    """Глобальная конфигурация (singleton)"""
    if not hasattr(get_access_config, "_instance"):
        # Ищем конфиг в стандартных местах
        config_paths = [
            Path("config/access_config.json"),
            Path("access_config.json"),
            Path("../config/access_config.json"),
            Path("../../config/access_config.json"),
        ]
        for path in config_paths:
            if path.exists():
                setattr(get_access_config, "_instance", load_access_config(path))
                logger.info(f"Loaded access config from {path}")
                break
        else:
            setattr(get_access_config, "_instance", load_access_config())
            logger.info("Using default access config")
    
    return getattr(get_access_config, "_instance")