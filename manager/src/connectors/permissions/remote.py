# manager/src/services/collectors/remote.py

import requests
from typing import List, Dict, Optional
from .base import PermissionCollector


class RemotePermissionCollector(PermissionCollector):
    """
    Удаленный коллектор прав доступа
    
    Собирает права через API Сканера:
    GET /api/scanner/permissions?path={resource_path}
    """
    
    def __init__(self, scanner_endpoint: str, timeout: int = 30):
        """
        Args:
            scanner_endpoint: URL Сканера (например, http://scanner:8000)
            timeout: Таймаут запроса
        """
        self.scanner_endpoint = scanner_endpoint.rstrip('/')
        self.timeout = timeout
        self._source_type = "remote"
        self._available = self._check_availability()
    
    def _check_availability(self) -> bool:
        """Проверить доступность Сканера"""
        try:
            response = requests.get(
                f"{self.scanner_endpoint}/api/health",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def collect(self, resource_path: str) -> List[Dict]:
        """
        Собрать права через API Сканера
        
        Args:
            resource_path: Путь к ресурсу
        
        Returns:
            List[Dict]: Список записей прав доступа
        """
        if not self.is_available():
            raise RuntimeError(f"Scanner {self.scanner_endpoint} is not available")
        
        try:
            response = requests.get(
                f"{self.scanner_endpoint}/api/scanner/permissions",
                params={"path": resource_path},
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"Scanner returned {response.status_code}: {response.text}")
            
            data = response.json()
            
            # Конвертируем формат Сканера в универсальный
            return self._convert_entries(data.get("entries", []))
            
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Scanner timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Cannot connect to Scanner {self.scanner_endpoint}")
        except Exception as e:
            raise RuntimeError(f"Failed to collect permissions from Scanner: {e}")
    
    def _convert_entries(self, entries: List[Dict]) -> List[Dict]:
        """Конвертировать формат Сканера в универсальный"""
        result = []
        for entry in entries:
            result.append({
                "principal": entry.get("principal", ""),
                "principal_type": entry.get("principal_type", "unknown"),
                "principal_sid": entry.get("principal_sid"),
                "principal_domain": entry.get("principal_domain"),
                "permissions": entry.get("permissions", []),
                "is_inherited": entry.get("is_inherited", False),
                "inherited_from": entry.get("inherited_from"),
                "collector_source": "remote"
            })
        return result
    
    def get_effective_permissions(self, resource_path: str, principal: str) -> List[str]:
        """Получить эффективные права через Сканер"""
        if not self.is_available():
            return []
        
        try:
            response = requests.get(
                f"{self.scanner_endpoint}/api/scanner/permissions/effective",
                params={
                    "path": resource_path,
                    "principal": principal
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json().get("permissions", [])
        except:
            pass
        
        return []
    
    def get_principals(self) -> List[Dict]:
        """Получить список субъектов через Сканер"""
        if not self.is_available():
            return []
        
        try:
            response = requests.get(
                f"{self.scanner_endpoint}/api/scanner/principals",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json().get("principals", [])
        except:
            pass
        
        return []
    
    def get_source_type(self) -> str:
        return "remote"
    
    def is_available(self) -> bool:
        return self._available