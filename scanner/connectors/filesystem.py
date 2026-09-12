#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Коннектор к файловой системе
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Iterator, Optional, List, Callable

from core.base import SourceType, FileContext
from connectors.base import BaseConnector

from scanner.src.finding import Finding


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


# Текстовые расширения по умолчанию для построчного сканирования (день 40.2)
DEFAULT_TEXT_EXTENSIONS = {
    'txt', 'csv', 'log', 'json', 'yaml', 'yml', 'xml', 'toml', 'ini', 'cfg', 'conf',
    'env', 'envrc', 'properties', 'py', 'js', 'ts', 'tsx', 'jsx', 'java', 'c', 'cpp',
    'h', 'hpp', 'go', 'rs', 'sh', 'bash', 'zsh', 'ps1', 'cmd', 'bat', 'sql', 'php',
    'rb', 'pl', 'lua', 'r', 'swift', 'kt', 'md', 'rst', 'html', 'css', 'scss',
    'dockerfile', 'makefile', 'tf', 'hcl',
    'pem', 'key', 'crt', 'csr', 'cert', 'p12', 'pfx', 'jks',
}

DEFAULT_SKIP_DIRS = {
    '$Recycle.Bin', 'System Volume Information', 'tmp', 'temp', 'cache',
    '.git', '__pycache__', 'venv', 'node_modules', 'logs', 'models',
    '.hg', '.svn', 'vendor', 'dist', 'build', 'target', '.idea', '.vscode',
    '_example', 'sample', 'template', 'examples', 'samples', 'templates',
    'test_data', 'fixtures', 'mocks',
}

_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx'}
_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'}


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


class FilesystemConnector:
    """
    Построчный коннектор файловой системы (день 40.2).

    Читает файлы построчно, прогоняет каждую строку через классификаторы
    (scan_line), дополняет находки контекстом (context_before/after).
    Не заменяет FileSystemConnector (Orchestrator) — работает параллельно.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}

        self._text_extensions = set(
            config.get("text_extensions", list(DEFAULT_TEXT_EXTENSIONS))
        ) | DEFAULT_TEXT_EXTENSIONS
        self._skip_dirs = set(config.get("skip_dirs", list(DEFAULT_SKIP_DIRS)))
        self._cred_filenames = CRED_FILENAMES
        self._recursive = config.get("recursive", True)
        self._context_lines = int(config.get("context_lines", 2))
        self._max_file_size_mb = int(config.get("max_file_size_mb", 50))
        self._max_text_chars = int(config.get("max_text_chars", 200000))
        self._buffer_size = int(config.get("buffer_size", 1024 * 1024))

    # =====================================================================
    # Обход каталога
    # =====================================================================

    def _discover_files(self, root: str) -> List[str]:
        folder = Path(root)
        if not folder.exists():
            return []
        if folder.is_file():
            return [str(folder.absolute())]

        result = []
        for r, dirs, files in os.walk(str(folder)):
            if not self._recursive:
                dirs.clear()
            dirs[:] = [d for d in dirs if d not in self._skip_dirs]
            for f in files:
                file_path = Path(r) / f
                # Расширение в списке или имя файла в credential-именах
                if self._is_supported(file_path):
                    result.append(str(file_path.absolute()))
        return result

    def _is_supported(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower().lstrip('.')
        if ext in self._text_extensions:
            return True
        if ext in _DOCUMENT_EXTENSIONS or ext in _IMAGE_EXTENSIONS:
            return True
        if file_path.name.lower() in self._cred_filenames:
            return True
        return False

    def _within_size(self, file_path) -> bool:
        try:
            p = file_path if isinstance(file_path, Path) else Path(file_path)
            return p.stat().st_size / (1024 * 1024) <= self._max_file_size_mb
        except Exception:
            return False

    # =====================================================================
    # Сканирование
    # =====================================================================

    def scan_path(
        self,
        path: str,
        classifiers: List[Any],
        progress_callback: Optional[Callable[[int, int, int, str], None]] = None,
    ) -> List[Finding]:
        """
        Сканирует папку (или файл). Возвращает список Finding.
        progress_callback(stage, current, total, file_path): stage 0=обход, 1=скан.
        """
        findings: List[Finding] = []
        files = self._discover_files(path)
        if not files:
            if progress_callback:
                progress_callback(1, 0, 0, path)
            return findings

        total = len(files)
        for i, file_path in enumerate(files, start=1):
            if progress_callback:
                progress_callback(1, i, total, file_path)
            if not self._within_size(file_path):
                continue
            try:
                file_findings = self.scan_file(file_path, classifiers)
                findings.extend(file_findings)
            except Exception as e:
                print(f"[FS] Ошибка сканирования {file_path}: {e}", flush=True)
                import traceback
                traceback.print_exc()

        return findings

    def scan_file(self, file_path: str, classifiers: List[Any]) -> List[Finding]:
        """Сканирует один файл построчно, возвращает список Finding."""
        p = Path(file_path)
        if not p.exists():
            return []

        ext = p.suffix.lower().lstrip('.')

        # Текст — построчно
        if ext in self._text_extensions or p.name.lower() in self._cred_filenames:
            text = self._read_text(str(p))
            if text is None:
                return []
            return self._scan_text(text, classifiers, str(p))

        # Документы — извлекаем текст и сканируем построчно
        if ext in _DOCUMENT_EXTENSIONS:
            text = self._extract_document(str(p), ext)
            if not text:
                return []
            return self._scan_text(text, classifiers, str(p))

        # Изображения — не сканируем построчно (stub, день 40.2)
        if ext in _IMAGE_EXTENSIONS:
            return []

        return []

    def _scan_text(self, text: str, classifiers: List[Any], file_path: str) -> List[Finding]:
        """Делит текст на строки, прогоняет через scan_line классификаторов."""
        if len(text) > self._max_text_chars:
            text = text[: self._max_text_chars]

        lines = text.splitlines()
        context_lines = self._context_lines
        findings: List[Finding] = []
        line_end = len(lines)

        for idx in range(line_end):
            line = lines[idx]
            line_num = idx + 1

            # Контекст вокруг строки
            before_start = max(0, idx - context_lines)
            after_end = min(line_end, idx + context_lines + 1)
            context_before = "\n".join(lines[before_start:idx])
            context_after = "\n".join(lines[idx + 1:after_end])

            for classifier in classifiers:
                try:
                    line_findings = classifier.scan_line(line, line_num)
                except Exception as e:
                    func = getattr(classifier, "classifier_name", type(classifier).__name__)
                    print(f"[FS] scan_line error {func} at {file_path}:{line_num}: {e}")
                    continue

                for finding in line_findings:
                    finding.line_text = line
                    finding.context_before = context_before
                    finding.context_after = context_after
                    finding.fragment_path = file_path
                    findings.append(finding)

        return findings

    def _read_text(self, file_path: str) -> Optional[str]:
        """Буферизованное чтение текста (максимум self._max_text_chars символов)."""
        try:
            chunks = []
            total = 0
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(self._buffer_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= self._max_text_chars:
                        break
            content = b''.join(chunks)
            # Двоичный мусор без текстовых признаков — пропускаем
            if content[:4096] and b'\x00' in content[:4096]:
                return None
            for encoding in ('utf-8', 'cp1251'):
                try:
                    return content.decode(encoding, errors='ignore')
                except Exception:
                    continue
            return content.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"[FS] Не удалось прочитать {file_path}: {e}")
            return None

    def _extract_document(self, file_path: str, ext: str) -> Optional[str]:
        """Извлечение текста из PDF/Office-документов."""
        try:
            from utils.document_extractor import DocumentExtractor
            import tempfile as _tf
            with open(file_path, 'rb') as f:
                content = f.read()
            extractor = DocumentExtractor(
                temp_dir=Path(_tf.gettempdir()),
                ocr_enabled=False,
            )
            result, error = extractor.extract_text(
                content, ext, Path(file_path).name
            )
            return result
        except Exception as e:
            print(f"[FS] Не удалось извлечь текст из {file_path}: {e}")
            return None


__all__ = ['FileSystemConnector', 'FilesystemConnector']