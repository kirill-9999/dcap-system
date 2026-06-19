#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - State Manager
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class ProcessedFileInfo:
    file_id: str
    file_hash: str
    size_bytes: int
    processed_at: str
    findings_count: int
    bucket: Optional[str] = None
    key: Optional[str] = None


class StateManager:
    def __init__(self, state_file: str):
        if not state_file:
            raise ValueError("state_file обязателен")
        
        self.state_file = Path(state_file)
        self.processed_files: Dict[str, ProcessedFileInfo] = {}
        self._load()
    
    def _load(self) -> None:
        if not self.state_file.exists():
            return
        
        seen_files = set()  # Для дедупликации
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        file_id = data.get("file_id")
                        
                        # Дедупликация: сохраняем только первый встреченный
                        if file_id in seen_files:
                            continue
                        seen_files.add(file_id)
                        
                        info = ProcessedFileInfo(
                            file_id=data["file_id"],
                            file_hash=data["file_hash"],
                            size_bytes=data["size_bytes"],
                            processed_at=data["processed_at"],
                            findings_count=data.get("findings_count", 0),
                            bucket=data.get("bucket"),
                            key=data.get("key")
                        )
                        self.processed_files[info.file_id] = info
                    except json.JSONDecodeError:
                        continue
            
            if self.processed_files:
                print(f"[STATE] Загружено {len(self.processed_files)} обработанных файлов (уникальных)")
                
        except Exception as e:
            print(f"[STATE] Ошибка загрузки: {e}")
    
    def save(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                for info in self.processed_files.values():
                    data = {
                        "file_id": info.file_id,
                        "file_hash": info.file_hash,
                        "size_bytes": info.size_bytes,
                        "processed_at": info.processed_at,
                        "findings_count": info.findings_count
                    }
                    if info.bucket:
                        data["bucket"] = info.bucket
                    if info.key:
                        data["key"] = info.key
                    
                    f.write(json.dumps(data, ensure_ascii=False) + '\n')
                    
        except Exception as e:
            print(f"[STATE] Ошибка сохранения: {e}")
    
    def is_processed_and_unchanged(self, file_id: str, current_hash: str) -> bool:
        if file_id not in self.processed_files:
            return False
        if current_hash is None:
            # Если хеш не передан, считаем что файл уже обработан
            return True
        return self.processed_files[file_id].file_hash == current_hash
    
    def mark_processed(self, file_context, file_hash: str, findings_count: int) -> None:
        from core.base import SourceType
        
        file_id = file_context.id
        
        if file_context.source_type in [SourceType.S3, SourceType.MINIO]:
            info = ProcessedFileInfo(
                file_id=file_id,
                file_hash=file_hash,
                size_bytes=file_context.size_bytes,
                processed_at=datetime.now().isoformat(),
                findings_count=findings_count,
                bucket=file_context.bucket,
                key=file_context.key
            )
        else:
            info = ProcessedFileInfo(
                file_id=file_id,
                file_hash=file_hash,
                size_bytes=file_context.size_bytes,
                processed_at=datetime.now().isoformat(),
                findings_count=findings_count
            )
        
        self.processed_files[file_id] = info
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "processed_files_count": len(self.processed_files),
            "state_file": str(self.state_file)
        }
    
    def get_processed_count(self) -> int:
        return len(self.processed_files)
    
    def clear(self):
        """Очистка state (для тестов)"""
        self.processed_files.clear()
        if self.state_file.exists():
            self.state_file.unlink()


__all__ = ['StateManager', 'ProcessedFileInfo']