#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Синхронизация оффлайн-находок с Manager
"""

import time
import threading
import grpc
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Добавляем путь для импорта
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc

from scanner.src.offline.queue import OfflineQueue, OfflineFinding
from scanner.src.offline.detector import ManagerDetector


class OfflineSync:
    """
    Синхронизация оффлайн-находок с Manager.
    Отправляет накопленные находки при восстановлении связи.
    """
    
    def __init__(self, queue: OfflineQueue, detector: ManagerDetector,
                 scanner_id: str, batch_size: int = 100):
        self.queue = queue
        self.detector = detector
        self.scanner_id = scanner_id
        self.batch_size = batch_size
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Статистика
        self.total_synced = 0
        self.total_failed = 0
        self.sync_errors = 0
        
        # Подписываемся на изменения статуса Manager
        self.detector.on_change(self._on_manager_status_change)
        
        print(f"[OFFLINE_SYNC] Инициализирован (batch_size={batch_size})")
    
    def start(self):
        """Запустить фоновую синхронизацию"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[OFFLINE_SYNC] Запущен")
    
    def stop(self):
        """Остановить синхронизацию"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        print("[OFFLINE_SYNC] Остановлен")
    
    def _run(self):
        """Основной цикл синхронизации"""
        while self._running:
            # Синхронизируем только если Manager доступен
            if self.detector.is_available():
                try:
                    self._sync_batch()
                except Exception as e:
                    print(f"[OFFLINE_SYNC] Ошибка синхронизации: {e}")
                    self.sync_errors += 1
            else:
                # Ждём, когда Manager станет доступен
                time.sleep(5)
            
            # Небольшая пауза между синхронизациями
            time.sleep(2)
    
    def _sync_batch(self):
        """Синхронизировать одну пачку находок"""
        # Получаем pending находки
        findings = self.queue.get_pending(limit=self.batch_size)
        
        if not findings:
            return
        
        print(f"[OFFLINE_SYNC] Найдено {len(findings)} находок для синхронизации")
        
        # Группируем по task_id
        grouped = {}
        for finding in findings:
            if finding.task_id not in grouped:
                grouped[finding.task_id] = []
            grouped[finding.task_id].append(finding)
        
        synced_ids = []
        failed_ids = []
        
        for task_id, task_findings in grouped.items():
            try:
                # Отправляем в Manager
                if self._send_findings(task_id, task_findings):
                    synced_ids.extend([f.id for f in task_findings])
                    self.total_synced += len(task_findings)
                    print(f"[OFFLINE_SYNC] ✅ Синхронизировано {len(task_findings)} находок для task {task_id}")
                else:
                    failed_ids.extend([f.id for f in task_findings])
                    self.total_failed += len(task_findings)
                    
            except Exception as e:
                print(f"[OFFLINE_SYNC] ❌ Ошибка синхронизации task {task_id}: {e}")
                failed_ids.extend([f.id for f in task_findings])
                self.total_failed += len(task_findings)
        
        # Отмечаем синхронизированные
        if synced_ids:
            self.queue.mark_synced(synced_ids)
        
        # Отмечаем неудачные (для повторных попыток)
        if failed_ids:
            self.queue.mark_sync_failed(failed_ids)
        
        # Периодически очищаем синхронизированные
        if self.total_synced % 1000 == 0:
            cleared = self.queue.clear_synced()
            print(f"[OFFLINE_SYNC] Очищено {cleared} синхронизированных находок")
    
    def _send_findings(self, task_id: str, findings: List[OfflineFinding]) -> bool:
        """Отправить находки в Manager"""
        try:
            channel = grpc.insecure_channel(self.detector.endpoint)
            stub = manager_pb2_grpc.ManagerStub(channel)
            
            # Преобразуем в protobuf
            pb_findings = []
            for f in findings:
                pb_findings.append(manager_pb2.Finding(
                    file_path=f.file_path,
                    file_hash=f.file_hash,
                    file_size=f.file_size,
                    file_modified=f.file_modified or "",
                    classifier_name=f.classifier_name,
                    category=f.category,
                    subcategory=f.subcategory,
                    value=f.value,
                    confidence=f.confidence,
                    detection_method=f.detection_method,
                    context=f.context
                ))
            
            # Отправляем через ReportBatch
            chunk = manager_pb2.ReportChunk(
                scanner_id=self.scanner_id,
                task_id=task_id,
                findings=pb_findings,
                catalog=[],  # TODO: добавить каталог
                failed=[]
            )
            
            response = stub.ReportBatch(iter([chunk]), timeout=30)
            channel.close()
            
            return response.success
            
        except Exception as e:
            print(f"[OFFLINE_SYNC] Ошибка отправки: {e}")
            return False
    
    def _on_manager_status_change(self, available: bool):
        """Обработчик изменения статуса Manager"""
        if available:
            print("[OFFLINE_SYNC] Manager доступен, начинаем синхронизацию")
        else:
            print("[OFFLINE_SYNC] Manager недоступен, находки сохраняются локально")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику синхронизации"""
        queue_stats = self.queue.get_stats()
        
        return {
            "total_synced": self.total_synced,
            "total_failed": self.total_failed,
            "sync_errors": self.sync_errors,
            "pending_in_queue": queue_stats["pending"],
            "total_in_queue": queue_stats["total"],
            "queue_by_category": queue_stats["by_category"]
        }
    
    def force_sync(self) -> Dict[str, Any]:
        """Принудительная синхронизация"""
        print("[OFFLINE_SYNC] Принудительная синхронизация...")
        
        synced = 0
        failed = 0
        
        while True:
            findings = self.queue.get_pending(limit=self.batch_size)
            if not findings:
                break
            
            # Отправляем напрямую (без проверки доступности)
            try:
                # Группируем по task_id
                grouped = {}
                for f in findings:
                    if f.task_id not in grouped:
                        grouped[f.task_id] = []
                    grouped[f.task_id].append(f)
                
                for task_id, task_findings in grouped.items():
                    if self._send_findings(task_id, task_findings):
                        synced += len(task_findings)
                        self.queue.mark_synced([f.id for f in task_findings])
                    else:
                        failed += len(task_findings)
                        self.queue.mark_sync_failed([f.id for f in task_findings])
                        
            except Exception as e:
                print(f"[OFFLINE_SYNC] Ошибка принудительной синхронизации: {e}")
                failed += len(findings)
                break
        
        return {
            "synced": synced,
            "failed": failed,
            "total": synced + failed
        }