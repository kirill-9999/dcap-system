#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автономный режим Scanner
Работает полностью независимо от Manager
"""

import asyncio
from pathlib import Path
from typing import Dict, Any

from scanner.src.modes.base import ScannerMode
from scanner.src.offline.queue import OfflineQueue
from scanner.src.offline.storage import OfflineStorage
from scanner.src.offline.detector import ManagerDetector


class StandaloneMode(ScannerMode):
    """
    Автономный режим.
    Scanner работает полностью независимо, без подключения к Manager.
    Находки сохраняются только в локальную очередь.
    """
    
    def __init__(self, data_dir: Path):
        super().__init__("standalone", data_dir)
        
        self.queue = OfflineQueue(data_dir / "queue")
        self.storage = OfflineStorage(data_dir / "storage")
        self.detector = ManagerDetector()
        
        self.scanner = None  # Будет установлен извне
        
        print(f"[STANDALONE] Инициализирован (data_dir={data_dir})")
    
    def configure(self, config: Dict[str, Any]):
        """Настройка автономного режима"""
        super().configure(config)
        
        # Настройка детектора (он не используется в автономном режиме)
        # Но сохраняем для совместимости
        endpoint = config.get("manager_endpoint", "localhost:50051")
        self.detector = ManagerDetector(endpoint)
        
        print(f"[STANDALONE] Настроен (manager_endpoint={endpoint})")
    
    async def start(self):
        """Запуск автономного режима"""
        if self._running:
            return
        
        self._running = True
        print("[STANDALONE] Запущен в автономном режиме")
        
        # Запускаем сканер в бесконечном цикле
        if self.scanner:
            # В автономном режиме сканер сканирует все ресурсы из конфига
            # и сохраняет находки в локальную очередь
            await self._run_scanner()
    
    async def _run_scanner(self):
        """Основной цикл сканирования в автономном режиме"""
        # Получаем ресурсы из конфига
        resources = self.config.get("resources", [])
        
        if not resources:
            print("[STANDALONE] Нет ресурсов для сканирования")
            return
        
        while self._running:
            for resource in resources:
                if not self._running:
                    break
                
                print(f"[STANDALONE] Сканирование ресурса: {resource}")
                
                try:
                    # Создаём сессию
                    session_id = self.storage.create_session(
                        resource_path=resource["path"],
                        resource_type=resource.get("type", "filesystem")
                    )
                    
                    # Сканируем (используем существующий orchestrator)
                    if self.scanner and hasattr(self.scanner, 'orchestrator'):
                        # TODO: реализовать сканирование через orchestrator
                        pass
                    
                    # Обновляем сессию
                    self.storage.update_session(
                        session_id=session_id,
                        completed=True
                    )
                    
                except Exception as e:
                    print(f"[STANDALONE] Ошибка сканирования {resource}: {e}")
            
            # Ждём следующего цикла
            interval = self.config.get("scan_interval", 3600)  # По умолчанию час
            await asyncio.sleep(interval)
    
    async def stop(self):
        """Остановка автономного режима"""
        self._running = False
        print("[STANDALONE] Остановлен")
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус"""
        status = super().get_status()
        
        status.update({
            "queue_stats": self.queue.get_stats(),
            "sessions_summary": self.storage.get_sessions_summary()
        })
        
        return status