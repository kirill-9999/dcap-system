# manager/src/connectors/permissions/factory.py

from typing import Optional, Type, Dict, Any
import logging
from .base import PermissionCollector
from .local import LocalPermissionCollector
from .remote import RemotePermissionCollector
from .ad import ADPermissionCollector
from manager.src.services.access_config import get_access_config  # ← абсолютный импорт

logger = logging.getLogger(__name__)


class PermissionCollectorFactory:
    """Фабрика для создания коллекторов прав доступа"""
    
    _collectors: Dict[str, Type[PermissionCollector]] = {
        "local": LocalPermissionCollector,
        "remote": RemotePermissionCollector,
        "ad": ADPermissionCollector,
    }
    
    @classmethod
    def get_collector(cls, source_type: Optional[str] = None, **kwargs) -> PermissionCollector:
        """
        Получить коллектор по типу
        
        Если source_type не указан — берется из конфига.
        
        Args:
            source_type: "local", "remote", "ad" или "mixed"
            **kwargs: параметры для коллектора
        
        Returns:
            PermissionCollector
        """
        if source_type is None:
            config = get_access_config()
            source_type = config.mode
        
        # Режим mixed собирает данные и из AD, и локально (fallback)
        if source_type == "mixed":
            return cls._build_mixed(**kwargs)
        
        collector_class = cls._collectors.get(source_type)
        if not collector_class:
            raise ValueError(f"Unknown collector type: {source_type}")
        
        config = get_access_config()
        
        # Для удаленного режима нужен endpoint
        if source_type == "remote":
            if "scanner_endpoint" not in kwargs:
                kwargs["scanner_endpoint"] = config.scanner_endpoint or "http://scanner:8000"
            if "timeout" not in kwargs:
                kwargs["timeout"] = config.timeout_seconds
        
        # Для AD-режима подставляем конфигурацию AD из конфига
        if source_type == "ad":
            kwargs = cls._merge_ad_config(kwargs, config)
        
        collector = collector_class(**kwargs)
        
        if not collector.is_available():
            raise RuntimeError(f"Collector {source_type} is not available")
        
        return collector
    
    @classmethod
    def _merge_ad_config(cls, kwargs: Dict[str, Any], config: Any) -> Dict[str, Any]:
        """Слить переданные аргументы с конфигом AD из access_config"""
        ad = getattr(config, "ad", None)
        if ad is None:
            return kwargs
        merged = {
            "server": ad.server,
            "domain": ad.domain,
            "base_dn": ad.base_dn,
            "username": ad.username,
            "password": ad.password,
            "use_ssl": ad.use_ssl,
            "ldap_port": ad.ldap_port,
            "timeout": ad.timeout,
            "cache_ttl": ad.cache_ttl,
            "redis_url": ad.redis_url,
        }
        for k, v in kwargs.items():
            if v is not None:
                merged[k] = v
        return merged
    
    @classmethod
    def _build_mixed(cls, **kwargs) -> "MixedPermissionCollector":
        """Создать mixed-коллектор (AD поверх local)"""
        try:
            from .ad import MixedPermissionCollector
        except ImportError:  # pragma: no cover
            from manager.src.connectors.permissions.ad import MixedPermissionCollector
        
        config = get_access_config()
        ad_kwargs = cls._merge_ad_config(dict(kwargs), config)
        return MixedPermissionCollector(ad_kwargs=ad_kwargs)
    
    @classmethod
    def get_available_collectors(cls) -> Dict[str, Dict]:
        """Получить список доступных коллекторов с их статусом"""
        result = {}
        config = get_access_config()
        
        collectors_to_check = ["local", "remote", "ad", "mixed"]
        
        for name in collectors_to_check:
            try:
                collector = cls.get_collector(name)
                result[name] = {
                    "available": collector.is_available(),
                    "source_type": collector.get_source_type()
                }
            except Exception as e:
                result[name] = {
                    "available": False,
                    "error": str(e)
                }
        
        return result
    
    @classmethod
    def register_collector(cls, name: str, collector_class: Type[PermissionCollector]):
        """Зарегистрировать новый коллектор (для расширяемости)"""
        if not issubclass(collector_class, PermissionCollector):
            raise TypeError("collector_class must be subclass of PermissionCollector")
        cls._collectors[name] = collector_class
        logger.info(f"Registered collector: {name}")