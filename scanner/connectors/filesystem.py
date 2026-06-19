#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Коннектор к файловой системе
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Iterator, Optional

from core.base import SourceType, FileContext
from connectors.base import BaseConnector


class FileSystemConnector(BaseConnector):
    """Коннектор к локальной файловой системе"""
    
    @property
    def connector_type(self) -> SourceType:
        return SourceType.FILESYSTEM
    
    def configure(self, config: Dict[str, Any]) -> None:
        super().configure(config)
        self._extensions = config.get("extensions", [
            "txt", "csv", "log", "json", "pdf", "docx", "doc", "xlsx", "xls",
            "png", "jpg", "jpeg", "gif", "bmp"
        ])
        self._skip_dirs = config.get("skip_dirs", [
            '$Recycle.Bin', 'System Volume Information', 'tmp', 'temp', 'cache',
            '.git', '__pycache__', 'venv', 'node_modules', 'logs', 'models'
        ])
        self._max_file_size_mb = config.get("max_file_size_mb", 50)
        self._recursive = config.get("recursive", True)
    
    def list_files(self, source: str) -> Iterator[FileContext]:
        folder = Path(source)
        if not folder.exists():
            return
        
        for root, dirs, files in os.walk(folder):
            if not self._recursive:
                dirs.clear()
            dirs[:] = [d for d in dirs if d not in self._skip_dirs]
            
            for file in files:
                file_path = Path(root) / file
                ext = file_path.suffix.lower().lstrip('.')
                
                if ext not in self._extensions:
                    continue
                
                size_mb = file_path.stat().st_size / (1024 * 1024)
                if size_mb > self._max_file_size_mb:
                    continue
                
                yield FileContext(
                    id=str(file_path.absolute()),
                    path=str(file_path.absolute()),
                    source_type=SourceType.FILESYSTEM,
                    size_bytes=file_path.stat().st_size,
                    modified_time=datetime.fromtimestamp(file_path.stat().st_mtime),
                    metadata={"extension": ext, "filename": file}
                )
    
    def get_content(self, file_context: FileContext) -> Optional[FileContext]:
        try:
            with open(file_context.path, 'rb') as f:
                file_context.content = f.read()
            return file_context
        except Exception as e:
            print(f"[FS] Ошибка загрузки {file_context.path}: {e}")
            return None


__all__ = ['FileSystemConnector']