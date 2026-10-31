# manager/src/services/collectors/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class PermissionCollector(ABC):
    """Базовый класс для всех коллекторов прав доступа"""
    
    @abstractmethod
    def collect(self, resource_path: str) -> List[Dict]:
        """
        Собрать права доступа для ресурса
        
        Args:
            resource_path: Путь к ресурсу (папка или файл)
        
        Returns:
            List[Dict]: Список записей прав доступа
            Каждая запись содержит:
            {
                "principal": "DOMAIN\\user",
                "principal_type": "user",  # user, group, local_user, ad_user, ad_group, system
                "principal_sid": "S-1-...",  # опционально
                "principal_domain": "DOMAIN",  # опционально
                "permissions": ["read", "write"],
                "is_inherited": False,
                "inherited_from": None,
                "collector_source": "local"
            }
        """
        pass
    
    @abstractmethod
    def get_effective_permissions(self, resource_path: str, principal: str) -> List[str]:
        """
        Получить эффективные права для пользователя/группы
        
        Args:
            resource_path: Путь к ресурсу
            principal: Имя пользователя или группы
        
        Returns:
            List[str]: Список прав (read, write, full_control, etc.)
        """
        pass
    
    @abstractmethod
    def get_principals(self) -> List[Dict]:
        """
        Получить список всех субъектов (пользователей/групп)
        
        Returns:
            List[Dict]: [
                {"name": "user1", "type": "local_user", "domain": "LOCAL", "sid": None}
            ]
        """
        pass
    
    @abstractmethod
    def get_source_type(self) -> str:
        """Вернуть тип источника: 'local', 'remote', 'ad', 'custom'"""
        pass
    
    def is_available(self) -> bool:
        """Проверить, доступен ли коллектор"""
        return True
    
    def get_principal_groups(self, principal: str) -> List[str]:
        """
        Получить группы, в которые входит субъект (опционально)
        Для local — только локальные группы через net user
        """
        return []