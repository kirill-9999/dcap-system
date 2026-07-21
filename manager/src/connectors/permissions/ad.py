# manager/src/connectors/permissions/ad.py

from typing import List, Dict, Optional
from .base import PermissionCollector


class ADPermissionCollector(PermissionCollector):
    """
    Коллектор для Active Directory
    ПОКА НЕ РЕАЛИЗОВАН — заглушка для будущего расширения
    
    Будет реализован в будущих версиях для интеграции с AD.
    В текущей версии (v2.0.0) используем LocalPermissionCollector.
    """
    
    def __init__(self, domain: str = None, server: str = None, 
                 username: str = None, password: str = None):
        self.domain = domain
        self.server = server
        self.username = username
        self.password = password
        self._source_type = "ad"
        self._available = False  # Пока недоступен
        
        # Проверяем, есть ли необходимые параметры
        if domain and server:
            self._available = True  # В будущем здесь будет проверка подключения
    
    def collect(self, resource_path: str) -> List[Dict]:
        """
        Сбор прав через AD (не реализован)
        
        В будущей версии будет использовать:
        - Active Directory PowerShell модуль
        - LDAP запросы
        - SID History
        - Group Policy Object (GPO) анализ
        """
        if not self.is_available():
            raise RuntimeError(
                "AD collector not available. Please check connection settings."
            )
        
        raise NotImplementedError(
            "AD collector not implemented yet. "
            "Use LocalPermissionCollector for Windows 10 without AD."
        )
    
    def get_effective_permissions(self, resource_path: str, principal: str) -> List[str]:
        """Получить эффективные права через AD (не реализован)"""
        raise NotImplementedError(
            "AD collector not implemented yet. "
            "Use LocalPermissionCollector for Windows 10 without AD."
        )
    
    def get_principals(self) -> List[Dict]:
        """
        Получить список субъектов из AD (не реализован)
        
        Будет возвращать:
        - Пользователей AD
        - Группы AD
        - Групповые политики
        """
        raise NotImplementedError(
            "AD collector not implemented yet. "
            "Use LocalPermissionCollector for Windows 10 without AD."
        )
    
    def get_principal_groups(self, principal: str) -> List[str]:
        """
        Получить группы AD для пользователя (не реализован)
        
        Будет учитывать:
        - Прямое членство в группах
        - Вложенные группы
        - Глобальные и универсальные группы
        """
        raise NotImplementedError(
            "AD collector not implemented yet. "
            "Use LocalPermissionCollector for Windows 10 without AD."
        )
    
    def get_source_type(self) -> str:
        return "ad"
    
    def is_available(self) -> bool:
        """
        Проверка доступности AD
        
        В будущем будет проверять:
        - Подключение к контроллеру домена
        - Аутентификацию
        - Доступность необходимых модулей
        """
        return self._available