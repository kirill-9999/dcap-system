#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Детектор доступности Manager
Проверяет, доступен ли Manager для синхронизации
"""

import time
import threading
import grpc
from typing import Optional, Callable, Dict, Any

# Добавляем путь для импорта
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc


class ManagerDetector:
    """
    Обнаружение доступности Manager.
    Проверяет HealthCheck с экспоненциальной задержкой.
    """
    
    def __init__(self, endpoint: str = "localhost:50051", 
                 check_interval: int = 10,
                 max_interval: int = 300):
        """
        Args:
            endpoint: gRPC endpoint Manager
            check_interval: начальный интервал проверки (сек)
            max_interval: максимальный интервал проверки (сек)
        """
        self.endpoint = endpoint
        self.check_interval = check_interval
        self.max_interval = max_interval
        self.current_interval = check_interval
        
        self._is_available = False
        self._last_check = 0
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[bool], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        print(f"[DETECTOR] Инициализирован: {endpoint}")
    
    def start(self):
        """Запустить фоновую проверку"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[DETECTOR] Запущен")
    
    def stop(self):
        """Остановить проверку"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        print("[DETECTOR] Остановлен")
    
    def _run(self):
        """Основной цикл проверки"""
        while self._running:
            self.check()
            time.sleep(self.current_interval)
    
    def check(self) -> bool:
        """Проверить доступность Manager"""
        try:
            channel = grpc.insecure_channel(self.endpoint)
            
            # Устанавливаем таймаут
            try:
                grpc.channel_ready_future(channel).result(timeout=5)
            except grpc.FutureTimeoutError:
                channel.close()
                self._set_available(False)
                return False
            
            stub = manager_pb2_grpc.ManagerStub(channel)
            
            # HealthCheck
            request = manager_pb2.HealthCheckRequest(service="scanner")
            response = stub.HealthCheck(request, timeout=5)
            
            channel.close()
            
            available = response.healthy
            self._set_available(available)
            
            if available:
                print(f"[DETECTOR] ✅ Manager доступен")
            else:
                print(f"[DETECTOR] ⚠️ Manager отвечает, но нездоров: {response.status}")
            
            return available
            
        except grpc.RpcError as e:
            print(f"[DETECTOR] ❌ RPC ошибка: {e.code()}")
            self._set_available(False)
            return False
            
        except Exception as e:
            print(f"[DETECTOR] ❌ Ошибка: {e}")
            self._set_available(False)
            return False
    
    def _set_available(self, available: bool):
        """Установить статус доступности"""
        with self._lock:
            changed = self._is_available != available
            
            if available:
                self._consecutive_failures = 0
                self._consecutive_successes += 1
                
                # Уменьшаем интервал при стабильной связи
                if self._consecutive_successes > 3:
                    self.current_interval = max(5, self.check_interval)
            else:
                self._consecutive_successes = 0
                self._consecutive_failures += 1
                
                # Увеличиваем интервал при частых ошибках
                if self._consecutive_failures > 5:
                    self.current_interval = min(
                        self.max_interval,
                        self.current_interval * 1.5
                    )
                    print(f"[DETECTOR] Интервал увеличен до {self.current_interval}с")
            
            self._is_available = available
            
            if changed:
                print(f"[DETECTOR] Статус изменён: {available}")
                self._notify_callbacks(available)
    
    def is_available(self) -> bool:
        """Проверить текущий статус Manager"""
        with self._lock:
            return self._is_available
    
    def on_change(self, callback: Callable[[bool], None]):
        """Подписаться на изменения статуса"""
        with self._lock:
            self._callbacks.append(callback)
    
    def _notify_callbacks(self, available: bool):
        """Уведомить подписчиков"""
        for callback in self._callbacks:
            try:
                callback(available)
            except Exception as e:
                print(f"[DETECTOR] Ошибка в callback: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику"""
        return {
            "endpoint": self.endpoint,
            "available": self._is_available,
            "current_interval": self.current_interval,
            "consecutive_failures": self._consecutive_failures,
            "consecutive_successes": self._consecutive_successes
        }