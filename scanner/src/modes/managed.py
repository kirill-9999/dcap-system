#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Управляемый режим Scanner
Работает под управлением Manager, но использует оффлайн-очередь
для сохранения находок при недоступности Manager
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from scanner.src.modes.base import ScannerMode
from scanner.src.offline.queue import OfflineQueue
from scanner.src.offline.storage import OfflineStorage
from scanner.src.offline.detector import ManagerDetector
from scanner.src.offline.sync import OfflineSync


class ManagedMode(ScannerMode):
    """
    Управляемый режим.
    Scanner работает под управлением Manager, но сохраняет находки
    локально при недоступности Manager.
    """
    
    def __init__(self, data_dir: Path):
        super().__init__("managed", data_dir)
        
        self.queue = OfflineQueue(data_dir / "queue")
        self.storage = OfflineStorage(data_dir / "storage")
        self.detector = ManagerDetector()
        self.sync = OfflineSync(self.queue, self.detector, "", batch_size=100)
        
        self.scanner_id = None
        self.scanner = None  # Будет установлен извне
        
        print(f"[MANAGED] Инициализирован (data_dir={data_dir})")
    
    def configure(self, config: Dict[str, Any]):
        """Настройка управляемого режима"""
        super().configure(config)
        
        endpoint = config.get("manager_endpoint", "localhost:50051")
        scanner_id = config.get("scanner_id", "")
        
        self.detector = ManagerDetector(endpoint)
        self.sync = OfflineSync(self.queue, self.detector, scanner_id, batch_size=100)
        
        print(f"[MANAGED] Настроен (endpoint={endpoint}, scanner_id={scanner_id})")
    
    async def start(self):
        """Запуск управляемого режима"""
        if self._running:
            return
        
        self._running = True
        
        # Запускаем детектор
        self.detector.start()
        
        # Запускаем синхронизацию
        self.sync.start()
        
        print("[MANAGED] Запущен в управляемом режиме")
        
        # Основной цикл: получение заданий от Manager
        if self.scanner:
            await self._run_managed_loop()
    
    async def _run_managed_loop(self):
        """Основной цикл управляемого режима"""
        while self._running:
            # Проверяем доступность Manager
            if self.detector.is_available():
                # Получаем задание от Manager
                task = await self.scanner.get_task()
                
                if task:
                    # Выполняем задание
                    await self._execute_task(task)
                else:
                    # Нет заданий, ждём
                    await asyncio.sleep(5)
            else:
                # Manager недоступен, работаем в оффлайн-режиме
                print("[MANAGED] Manager недоступен, работаем в оффлайн-режиме")
                await asyncio.sleep(10)
    
    async def _execute_task(self, task):
        """Выполнить задание с сохранением в оффлайн-очередь"""
        print(f"[MANAGED] Выполнение задания: {task.task_id}")
        
        # Создаём сессию
        session_id = self.storage.create_session(
            resource_path=task.resource_path,
            resource_type=task.resource_type
        )
        
        try:
            # Выполняем сканирование через orchestrator
            # Находки сохраняются в оффлайн-очередь через специальный handler
            # TODO: реализовать OfflineHandler для сохранения в очередь
            
            # Обновляем сессию
            self.storage.update_session(
                session_id=session_id,
                completed=True
            )
            
            # Отправляем результаты в Manager (если доступен)
            if self.detector.is_available():
                await self.scanner.complete_task(
                    task_id=task.task_id,
                    files_scanned=0,  # TODO: реальные цифры
                    findings_count=0,
                    success=True
                )
            else:
                print(f"[MANAGED] Manager недоступен, результаты сохранены локально")
                
        except Exception as e:
            print(f"[MANAGED] Ошибка выполнения задания: {e}")
            self.storage.update_session(
                session_id=session_id,
                error=str(e)
            )
    
    async def stop(self):
        """Остановка управляемого режима"""
        self._running = False
        
        self.detector.stop()
        self.sync.stop()
        
        print("[MANAGED] Остановлен")
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус"""
        status = super().get_status()
        
        status.update({
            "manager_available": self.detector.is_available(),
            "queue_stats": self.queue.get_stats(),
            "sync_stats": self.sync.get_stats(),
            "sessions_summary": self.storage.get_sessions_summary()
        })
        
        return status