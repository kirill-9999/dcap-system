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


# Имена файлов-носителей учётных данных (сканируются даже без расширения
# в списке: .netrc, kubeconfig, .env.local и т.п. не имеют суффикса файла).
CRED_FILENAMES = {
    'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519',
    '.pgpass', '.netrc', '_netrc', 'kubeconfig', '.kubeconfig', 'jaas.conf',
    'kafka_client_jaas.conf', 'secrets', 'secrets.json', 'secrets.yaml',
    'secrets.yml', 'secret', '.env', '.envrc', '.env.local', '.env.production',
    '.htpasswd', 'passwd', 'shadow', '.npmrc', '.pypirc', '.gemrc', '.boto',
    '.my.cnf', '.my.ini', '.dockerignore', '.gitignore', '.gitattributes',
}


class FileSystemConnector(BaseConnector):
    """Коннектор к локальной файловой системе"""
    
    @property
    def connector_type(self) -> SourceType:
        return SourceType.FILESYSTEM
    
    def configure(self, config: Dict[str, Any]) -> None:
        super().configure(config)
        self._extensions = config.get("extensions", [
            "txt", "csv", "log", "json", "yaml", "yml", "xml", "toml", "ini", "cfg", "conf",
            "env", "envrc", "properties", "py", "js", "ts", "tsx", "java", "c", "cpp", "h",
            "hpp", "go", "rs", "sh", "bash", "zsh", "ps1", "cmd", "bat", "sql", "php", "rb",
            "lua", "r", "swift", "kt", "md", "rst", "html", "css", "scss", "dockerfile",
            "makefile", "tf", "hcl",
            "pem", "key", "crt", "csr", "cert", "p12", "pfx", "jks",
            "doc", "docx", "xls", "xlsx",
            "pdf", "png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp",
        ])
        self._skip_dirs = config.get("skip_dirs", [
            '$Recycle.Bin', 'System Volume Information', 'tmp', 'temp', 'cache',
            '.git', '__pycache__', 'venv', 'node_modules', 'logs', 'models',
            '.hg', '.svn', 'vendor', 'dist', 'build', 'target', '.idea', '.vscode',
            '_example', 'sample', 'template', 'examples', 'samples', 'templates',
            'test_data', 'fixtures', 'mocks',
        ])
        self._max_file_size_mb = config.get("max_file_size_mb", 50)
        self._recursive = config.get("recursive", True)
        self._buffer_size = config.get("buffer_size", 1024 * 1024)
        self._max_text_chars = config.get("max_text_chars", 200000)
        self._cred_filenames = CRED_FILENAMES
        self._text_extensions = {
            'txt', 'csv', 'log', 'json', 'yaml', 'yml', 'xml', 'toml', 'ini', 'cfg', 'conf',
            'env', 'envrc', 'properties', 'py', 'js', 'ts', 'tsx', 'jsx', 'java', 'c', 'cpp',
            'h', 'hpp', 'go', 'rs', 'sh', 'bash', 'zsh', 'ps1', 'cmd', 'bat', 'sql', 'php',
            'rb', 'pl', 'lua', 'r', 'swift', 'kt', 'md', 'rst', 'html', 'css', 'scss',
            'dockerfile', 'makefile', 'tf', 'hcl',
            'pem', 'key', 'crt', 'csr', 'cert', 'p12', 'pfx', 'jks',
        }
    
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
                
                # Файлы-носители учётных данных сканируются по имени (без расширения)
                if ext not in self._extensions and file.lower() not in self._cred_filenames:
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
        """Чтение файла с буферизацией (день 34.5).
        
        Для текстовых форматов чтение останавливается после накопления
        max_text_chars байт — дальнейший контент не нужен классификатору.
        """
        try:
            ext = file_context.path.replace('\\', '/').rsplit('.', 1)[-1].lower() \
                if '.' in file_context.path else ''
            limit = self._max_text_chars if ext in self._text_extensions else None

            chunks = []
            total = 0
            with open(file_context.path, 'rb') as f:
                while True:
                    chunk = f.read(self._buffer_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if limit is not None and total >= limit:
                        break
            file_context.content = b''.join(chunks)
            return file_context
        except Exception as e:
            print(f"[FS] Ошибка загрузки {file_context.path}: {e}")
            return None


__all__ = ['FileSystemConnector']