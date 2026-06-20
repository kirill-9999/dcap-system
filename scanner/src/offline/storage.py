#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Оффлайн-хранилище для Scanner
Хранит состояние сканирования и находки
"""

import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class ScanSession:
    """Сессия сканирования в оффлайн-режиме"""
    session_id: str
    resource_path: str
    resource_type: str
    started_at: str
    files_scanned: int = 0
    findings_count: int = 0
    completed_at: Optional[str] = None
    error: Optional[str] = None


class OfflineStorage:
    """
    Хранилище для оффлайн-режима.
    Сохраняет состояние сессий сканирования.
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.sessions_file = self.data_dir / "sessions.json"
        self.sessions: Dict[str, ScanSession] = {}
        self._load_sessions()
        
        print(f"[OFFLINE_STORAGE] Инициализировано: {self.data_dir}")
    
    def _load_sessions(self):
        """Загрузить сессии из файла"""
        if not self.sessions_file.exists():
            return
        
        try:
            with open(self.sessions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for session_id, session_data in data.items():
                    self.sessions[session_id] = ScanSession(**session_data)
            
            print(f"[OFFLINE_STORAGE] Загружено {len(self.sessions)} сессий")
            
        except Exception as e:
            print(f"[OFFLINE_STORAGE] Ошибка загрузки сессий: {e}")
    
    def _save_sessions(self):
        """Сохранить сессии в файл"""
        try:
            data = {}
            for session_id, session in self.sessions.items():
                data[session_id] = asdict(session)
            
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"[OFFLINE_STORAGE] Ошибка сохранения сессий: {e}")
    
    def create_session(self, resource_path: str, resource_type: str = "filesystem") -> str:
        """Создать новую сессию сканирования"""
        session_id = str(uuid.uuid4())
        
        session = ScanSession(
            session_id=session_id,
            resource_path=resource_path,
            resource_type=resource_type,
            started_at=datetime.now().isoformat()
        )
        
        self.sessions[session_id] = session
        self._save_sessions()
        
        print(f"[OFFLINE_STORAGE] Создана сессия: {session_id}")
        return session_id
    
    def update_session(self, session_id: str, files_scanned: int = None, 
                       findings_count: int = None, completed: bool = False,
                       error: str = None):
        """Обновить сессию"""
        if session_id not in self.sessions:
            return
        
        session = self.sessions[session_id]
        
        if files_scanned is not None:
            session.files_scanned = files_scanned
        if findings_count is not None:
            session.findings_count = findings_count
        if completed:
            session.completed_at = datetime.now().isoformat()
        if error:
            session.error = error
        
        self._save_sessions()
    
    def get_session(self, session_id: str) -> Optional[ScanSession]:
        """Получить сессию по ID"""
        return self.sessions.get(session_id)
    
    def get_all_sessions(self) -> List[ScanSession]:
        """Получить все сессии"""
        return list(self.sessions.values())
    
    def get_sessions_summary(self) -> Dict[str, Any]:
        """Получить сводку по сессиям"""
        total = len(self.sessions)
        completed = sum(1 for s in self.sessions.values() if s.completed_at)
        in_progress = total - completed
        total_files = sum(s.files_scanned for s in self.sessions.values())
        total_findings = sum(s.findings_count for s in self.sessions.values())
        
        return {
            "total_sessions": total,
            "completed": completed,
            "in_progress": in_progress,
            "total_files_scanned": total_files,
            "total_findings": total_findings
        }