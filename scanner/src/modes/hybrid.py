#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Гибридный режим Scanner
Автоматически переключается между управляемым и автономным режимами
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from scanner.src.modes.base import ScannerMode
from scanner.src.modes.managed import ManagedMode
from scanner.src.modes.standalone import StandaloneMode
from scanner.src.offline.detector import ManagerDetector


class HybridMode(ScannerMode):
    """
    Гибридный режим.
    Автоматически переключается между управляемым и автономным режимами
    в зависимости от доступности Manager.
    """
    
    MODE_MANAGED = "managed"
    MODE_STANDALONE = "standalone"
    
    def __init__(self, data_dir: Path):
        super().__init__("hybrid", data_dir)
        
        self.data_dir = data_dir
        self.detector = ManagerDetector()
        
        self.managed_mode = ManagedMode(data_dir / "managed")
        self.standalone_mode = StandaloneMode(data_dir / "standalone")
        
        self.current_mode = None
        self.scanner = None  # Будет установлен извне
        
        print(f"[HYBRID] Инициализирован (data_dir={data_dir})")
    
    def configure(self, config: Dict[str, Any]):
        """Настройка гибридного режима"""
        super().configure(config)
        
        # Настраиваем оба режима
        managed_config = config.copy()
        managed_config["scanner_id"] = config.get("scanner_id", "")
        
        self.managed_mode.configure(managed_config)
        self.standalone_mode.configure(config)
        
        # Настраиваем детектор
        endpoint = config.get("manager_endpoint", "localhost:50051")
        self.detector = ManagerDetector(endpoint)
        
        print(f"[HYBRID] Настроен (endpoint={endpoint})")
    
    async def start(self):
        """Запуск гибридного режима"""
        if self._running:
            return
        
        self._running = True
        
        # Запускаем детектор
        self.detector.start()
        
        # Передаём сканер в режимы
        if self.scanner:
            self.managed_mode.scanner = self.scanner
            self.standalone_mode.scanner = self.scanner
        
        print("[HYBRID] Запущен")
        
        # Основной цикл: следим за доступностью Manager
        await self._run_hybrid_loop()
    
    async def _run_hybrid_loop(self):
        """Основной цикл гибридного режима"""
        while self._running:
            available = self.detector.is_available()
            
            if available and self.current_mode != self.MODE_MANAGED:
                # Переключаемся на управляемый режим
                await self._switch_to_managed()
                
            elif not available and self.current_mode != self.MODE_STANDALONE:
                # Переключаемся на автономный режим
                await self._switch_to_standalone()
            
            # Ждём следующей проверки
            await asyncio.sleep(5)
    
    async def _switch_to_managed(self):
        """Переключение на управляемый режим"""
        print("[HYBRID] Переключение на управляемый режим")
        
        # Останавливаем автономный режим
        await self.standalone_mode.stop()
        
        # Запускаем управляемый режим
        await self.managed_mode.start()
        
        self.current_mode = self.MODE_MANAGED
    
    async def _switch_to_standalone(self):
        """Переключение на автономный режим"""
        print("[HYBRID] Переключение на автономный режим")
        
        # Останавливаем управляемый режим
        await self.managed_mode.stop()
        
        # Запускаем автономный режим
        await self.standalone_mode.start()
        
        self.current_mode = self.MODE_STANDALONE
    
    async def stop(self):
        """Остановка гибридного режима"""
        self._running = False
        
        # Останавливаем оба режима
        await self.managed_mode.stop()
        await self.standalone_mode.stop()
        
        self.detector.stop()
        
        print("[HYBRID] Остановлен")
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус"""
        status = super().get_status()
        
        status.update({
            "current_mode": self.current_mode,
            "manager_available": self.detector.is_available(),
            "managed_status": self.managed_mode.get_status(),
            "standalone_status": self.standalone_mode.get_status()
        })
        
        return status