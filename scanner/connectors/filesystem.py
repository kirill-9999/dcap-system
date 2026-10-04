#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Коннектор к файловой системе
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Iterator, Optional, List, Callable

from core.base import SourceType, FileContext
from connectors.base import BaseConnector

from scanner.src.finding import Finding
# День 53.1b (BACKLOG-097): общий построчный пайплайн вынесен в _text_scanner,
# чтобы S3LineConnector (53.2) переиспользовал ту же логику без копипасты.
from scanner.connectors._text_scanner import (
    CRED_FILENAMES,
    DEFAULT_TEXT_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    decode_text_bytes,
    extract_document_text,
    is_supported_file,
    scan_text as shared_scan_text,
)

logger = logging.getLogger("dcap-scanner")

DEFAULT_SKIP_DIRS = {
    '$Recycle.Bin', 'System Volume Information', 'tmp', 'temp', 'cache',
    '.git', '__pycache__', 'venv', 'node_modules', 'logs', 'models',
    '.hg', '.svn', 'vendor', 'dist', 'build', 'target', '.idea', '.vscode',
    '_example', 'sample', 'template', 'examples', 'samples', 'templates',
    'test_data', 'fixtures', 'mocks',
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
        # Параллельное сканирование файлов (день 42); 1 = последовательный режим
        self._max_workers = int(config.get("max_parallel_files", 1) or 1)

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
        return is_supported_file(
            ext, file_path.name,
            text_extensions=self._text_extensions,
            cred_filenames=self._cred_filenames,
        )

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
        stop_event: Optional[Any] = None,
    ) -> List[Finding]:
        """
        Сканирует папку (или файл). Возвращает список Finding.
        progress_callback(stage, current, total, file_path): stage 0=обход, 1=скан.
        stop_event (день 42.5+): threading.Event — при установке сканирование
        останавливается после текущих файлов (Ctrl+C, scanner.stop()).
        """
        findings: List[Finding] = []
        files = self._discover_files(path)
        if not files:
            if progress_callback:
                progress_callback(1, 0, 0, path)
            return findings

        total = len(files)
        max_workers = self._max_workers

        def _stopped() -> bool:
            return stop_event is not None and stop_event.is_set()

        def _scan_one(file_path: str) -> List[Finding]:
            """Сканирование одного файла (общий код для seq/parallel)."""
            if not self._within_size(file_path):
                return []
            try:
                return self.scan_file(file_path, classifiers)
            except Exception as e:
                print(f"[FS] Ошибка сканирования {file_path}: {e}", flush=True)
                import traceback
                traceback.print_exc()
                return []

        if max_workers <= 1:
            # Последовательный режим (как раньше, день 40.2)
            for i, file_path in enumerate(files, start=1):
                if _stopped():
                    logger.info("[FS] Сканирование остановлено (stop_event) на %d/%d", i, total)
                    break
                if progress_callback:
                    progress_callback(1, i, total, file_path)
                findings.extend(_scan_one(file_path))
            return findings

        # Параллельный режим (день 42): ThreadPoolExecutor.
        # Прогресс — монотонный счётчик; findings собираем в порядке завершения.
        import threading
        from concurrent.futures import ThreadPoolExecutor

        lock = threading.Lock()
        done_counter = [0]

        def _work(file_path: str):
            if _stopped():
                return []
            result = _scan_one(file_path)
            with lock:
                done_counter[0] += 1
                current = done_counter[0]
            if progress_callback:
                progress_callback(1, current, total, file_path)
            return result

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for result in ex.map(_work, files):
                findings.extend(result)
                if _stopped():
                    logger.info("[FS] Сканирование остановлено (stop_event)")
                    break

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
            return shared_scan_text(
                text, classifiers, str(p), self._context_lines, self._max_text_chars
            )

        # Документы — извлекаем текст и сканируем построчно
        if ext in DOCUMENT_EXTENSIONS:
            content = self._read_bytes(p, file_path)
            if content is None:
                return []
            text = extract_document_text(
                content, ext, p.name, ocr_enabled=self.config.get("ocr_enabled", False)
            )
            if not text:
                return []
            return shared_scan_text(
                text, classifiers, str(p), self._context_lines, self._max_text_chars
            )

        # Изображения — OCR (TASK-022, BUG-067): извлекаем текст через OCR
        if ext in IMAGE_EXTENSIONS:
            content = self._read_bytes(p, file_path)
            if content is None:
                return []
            text = extract_document_text(
                content, ext, p.name, ocr_enabled=self.config.get("ocr_enabled", False)
            )
            if not text:
                return []
            findings = shared_scan_text(
                text, classifiers, str(p), self._context_lines, self._max_text_chars
            )
            # BUG-067d (TASK-034, день 46.8): findings из OCR-изображения
            # помечаем как image_region + detector=ocr.
            # BUG-077 (TASK-041, v3.13.17): реальные координаты OCR не вычисляются
            # (Tesseract вызывается без --psm/tsv, только текст). Ставим None,
            # чтобы API/WebUI не пытались вырезать несуществующий регион.
            # Полный OCR-пайплайн с bbox — BACKLOG-085 (v3.1.0).
            for f in findings:
                f.fragment_type = "image_region"
                f.detector = "ocr"
                f.bounding_box = None
            return findings

        return []

    def _read_bytes(self, p: Path, file_path: str) -> Optional[bytes]:
        """Прочитать файл целиком (для DocumentExtractor, который ждёт байты)."""
        try:
            with open(p, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.warning("[FS] Не удалось открыть %s: %s", file_path, e)
            return None

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
            # Двоичный мусор без текстовых признаков — пропускаем
            return decode_text_bytes(b''.join(chunks))
        except Exception as e:
            logger.warning("[FS] Не удалось прочитать %s: %s", file_path, e)
            return None


__all__ = ['FileSystemConnector', 'FilesystemConnector']

# Регистрация в фабрике (день 53.1b)
from scanner.connectors.factory import register_line_connector  # noqa: E402

register_line_connector("filesystem", lambda cfg: FilesystemConnector(cfg))