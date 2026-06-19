#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Базовый коннектор
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Iterator, Optional

from core.base import ISourceConnector, SourceType, FileContext


class BaseConnector(ISourceConnector, ABC):
    """Базовый класс для всех коннекторов"""
    
    def __init__(self):
        self.config: Dict[str, Any] = {}
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Настройка коннектора"""
        self.config = config
    
    @abstractmethod
    def list_files(self, source: str) -> Iterator[FileContext]:
        pass
    
    @abstractmethod
    def get_content(self, file_context: FileContext) -> Optional[FileContext]:
        pass