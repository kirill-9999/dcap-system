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
            source_type: "local", "remote" или "ad"
            **kwargs: параметры для коллектора
        
        Returns:
            PermissionCollector
        """
        if source_type is None:
            config = get_access_config()
            source_type = config.mode
        
        collector_class = cls._collectors.get(source_type)
        if not collector_class:
            raise ValueError(f"Unknown collector type: {source_type}")
        
        # Для удаленного режима нужен endpoint
        if source_type == "remote":
            config = get_access_config()
            if "scanner_endpoint" not in kwargs:
                kwargs["scanner_endpoint"] = config.scanner_endpoint or "http://scanner:8000"
            if "timeout" not in kwargs:
                kwargs["timeout"] = config.timeout_seconds
        
        collector = collector_class(**kwargs)
        
        if not collector.is_available():
            raise RuntimeError(f"Collector {source_type} is not available")
        
        return collector
    
    @classmethod
    def get_available_collectors(cls) -> Dict[str, Dict]:
        """Получить список доступных коллекторов с их статусом"""
        result = {}
        config = get_access_config()
        
        for name, collector_class in cls._collectors.items():
            try:
                if name == "remote":
                    collector = collector_class(
                        scanner_endpoint=config.scanner_endpoint or "http://scanner:8000"
                    )
                else:
                    collector = collector_class()
                
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