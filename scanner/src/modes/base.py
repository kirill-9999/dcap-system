#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Базовый класс для режимов работы Scanner
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path


class ScannerMode(ABC):
    """
    Базовый класс режима работы Scanner.
    Все режимы должны наследовать этот класс.
    """
    
    def __init__(self, name: str, data_dir: Path):
        self.name = name
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._running = False
        self.config: Dict[str, Any] = {}
    
    @abstractmethod
    async def start(self):
        """Запустить режим"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Остановить режим"""
        pass
    
    @abstractmethod
    def configure(self, config: Dict[str, Any]):
        """Настроить режим"""
        self.config = config
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Получить статус режима"""
        return {
            "mode": self.name,
            "running": self._running
        }