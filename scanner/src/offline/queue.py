#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Оффлайн-очередь находок (SQLite)
Сохраняет находки локально, когда Manager недоступен
"""

import sqlite3
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class OfflineFinding:
    """Находка в оффлайн-очереди"""
    id: str
    task_id: str
    scanner_id: str
    file_path: str
    classifier_name: str
    category: str
    subcategory: str
    value: str
    confidence: float
    detection_method: str
    context: str
    file_hash: str
    file_size: int
    file_modified: Optional[str]
    created_at: str
    synced: bool = False
    sync_attempts: int = 0
    last_sync_attempt: Optional[str] = None


class OfflineQueue:
    """
    Локальная очередь находок для оффлайн-режима.
    Использует SQLite для хранения данных.
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.data_dir / "offline_queue.db"
        self._lock = threading.Lock()
        self._init_db()
        
        print(f"[OFFLINE_QUEUE] Инициализирована: {self.db_path}")
    
    def _init_db(self):
        """Инициализация БД"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    scanner_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    classifier_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    detection_method TEXT NOT NULL,
                    context TEXT,
                    file_hash TEXT,
                    file_size INTEGER,
                    file_modified TEXT,
                    created_at TEXT NOT NULL,
                    synced INTEGER DEFAULT 0,
                    sync_attempts INTEGER DEFAULT 0,
                    last_sync_attempt TEXT
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_findings_synced 
                ON findings(synced)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_findings_created 
                ON findings(created_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_findings_task 
                ON findings(task_id)
            """)
            
            conn.commit()
            conn.close()
    
    def add(self, finding: OfflineFinding) -> bool:
        """Добавить находку в очередь"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO findings (
                        id, task_id, scanner_id, file_path, classifier_name,
                        category, subcategory, value, confidence, detection_method,
                        context, file_hash, file_size, file_modified, created_at,
                        synced, sync_attempts, last_sync_attempt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    finding.id,
                    finding.task_id,
                    finding.scanner_id,
                    finding.file_path,
                    finding.classifier_name,
                    finding.category,
                    finding.subcategory,
                    finding.value,
                    finding.confidence,
                    finding.detection_method,
                    finding.context,
                    finding.file_hash,
                    finding.file_size,
                    finding.file_modified,
                    finding.created_at,
                    0,  # synced
                    0,  # sync_attempts
                    None  # last_sync_attempt
                ))
                
                conn.commit()
                conn.close()
                return True
                
        except Exception as e:
            print(f"[OFFLINE_QUEUE] Ошибка добавления находки: {e}")
            return False
    
    def add_batch(self, findings: List[OfflineFinding]) -> int:
        """Добавить несколько находок в очередь"""
        added = 0
        for finding in findings:
            if self.add(finding):
                added += 1
        return added
    
    def get_pending(self, limit: int = 1000) -> List[OfflineFinding]:
        """Получить несинхронизированные находки"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM findings 
                    WHERE synced = 0 
                    ORDER BY created_at ASC 
                    LIMIT ?
                """, (limit,))
                
                rows = cursor.fetchall()
                conn.close()
                
                return [self._row_to_finding(row) for row in rows]
                
        except Exception as e:
            print(f"[OFFLINE_QUEUE] Ошибка получения находок: {e}")
            return []
    
    def mark_synced(self, finding_ids: List[str]) -> int:
        """Отметить находки как синхронизированные"""
        if not finding_ids:
            return 0
        
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                placeholders = ','.join(['?'] * len(finding_ids))
                cursor.execute(f"""
                    UPDATE findings 
                    SET synced = 1, last_sync_attempt = datetime('now')
                    WHERE id IN ({placeholders})
                """, finding_ids)
                
                affected = cursor.rowcount
                conn.commit()
                conn.close()
                return affected
                
        except Exception as e:
            print(f"[OFFLINE_QUEUE] Ошибка отметки синхронизации: {e}")
            return 0
    
    def mark_sync_failed(self, finding_ids: List[str]) -> int:
        """Отметить находки как неудачно синхронизированные"""
        if not finding_ids:
            return 0
        
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                placeholders = ','.join(['?'] * len(finding_ids))
                cursor.execute(f"""
                    UPDATE findings 
                    SET sync_attempts = sync_attempts + 1,
                        last_sync_attempt = datetime('now')
                    WHERE id IN ({placeholders})
                """, finding_ids)
                
                affected = cursor.rowcount
                conn.commit()
                conn.close()
                return affected
                
        except Exception as e:
            print(f"[OFFLINE_QUEUE] Ошибка отметки неудачной синхронизации: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику очереди"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                # Всего находок
                cursor.execute("SELECT COUNT(*) FROM findings")
                total = cursor.fetchone()[0]
                
                # Несинхронизированных
                cursor.execute("SELECT COUNT(*) FROM findings WHERE synced = 0")
                pending = cursor.fetchone()[0]
                
                # Синхронизированных
                cursor.execute("SELECT COUNT(*) FROM findings WHERE synced = 1")
                synced = cursor.fetchone()[0]
                
                # По категориям
                cursor.execute("""
                    SELECT category, COUNT(*) 
                    FROM findings 
                    WHERE synced = 0 
                    GROUP BY category
                """)
                by_category = dict(cursor.fetchall())
                
                conn.close()
                
                return {
                    "total": total,
                    "pending": pending,
                    "synced": synced,
                    "by_category": by_category
                }
                
        except Exception as e:
            print(f"[OFFLINE_QUEUE] Ошибка получения статистики: {e}")
            return {"total": 0, "pending": 0, "synced": 0, "by_category": {}}
    
    def clear_synced(self) -> int:
        """Очистить синхронизированные находки (экономия места)"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM findings WHERE synced = 1")
                affected = cursor.rowcount
                conn.commit()
                conn.close()
                return affected
                
        except Exception as e:
            print(f"[OFFLINE_QUEUE] Ошибка очистки: {e}")
            return 0
    
    def _row_to_finding(self, row) -> OfflineFinding:
        """Преобразовать строку БД в объект"""
        return OfflineFinding(
            id=row['id'],
            task_id=row['task_id'],
            scanner_id=row['scanner_id'],
            file_path=row['file_path'],
            classifier_name=row['classifier_name'],
            category=row['category'],
            subcategory=row['subcategory'],
            value=row['value'],
            confidence=row['confidence'],
            detection_method=row['detection_method'],
            context=row['context'] or '',
            file_hash=row['file_hash'] or '',
            file_size=row['file_size'] or 0,
            file_modified=row['file_modified'],
            created_at=row['created_at'],
            synced=bool(row['synced']),
            sync_attempts=row['sync_attempts'] or 0,
            last_sync_attempt=row['last_sync_attempt']
        )