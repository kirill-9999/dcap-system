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

logger = logging.getLogger("dcap-scanner")


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
            return self._scan_text(text, classifiers, str(p))

        # Документы — извлекаем текст и сканируем построчно
        if ext in _DOCUMENT_EXTENSIONS:
            text = self._extract_document(str(p), ext)
            if not text:
                return []
            return self._scan_text(text, classifiers, str(p))

        # Изображения — OCR (TASK-022, BUG-067): извлекаем текст через OCR
        if ext in _IMAGE_EXTENSIONS:
            text = self._extract_document(str(p), ext)
            if not text:
                return []
            findings = self._scan_text(text, classifiers, str(p))
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

    def _scan_text(self, text: str, classifiers: List[Any], file_path: str) -> List[Finding]:
        """Сканирует текст классификаторами.

        Классификаторы с файловым анализом (scan_text) отрабатывают один раз на
        весь текст (день 42.5+); остальные — построчно через scan_line.
        """
        if len(text) > self._max_text_chars:
            text = text[: self._max_text_chars]

        # File-level prefilter (день 42): пропускаем файл целиком, если ни один
        # классификатор не видит быстрых признаков во всём содержимом.
        if not self._file_pass_prefilter(text, classifiers):
            return []

        lines = text.splitlines()
        context_lines = self._context_lines
        line_end = len(lines)
        findings: List[Finding] = []

        # Файловый путь: классификаторы, у которых есть scan_text(text), вызываем
        # один раз (PII — один вызов Presidio на весь файл, строки из offset).
        for classifier in classifiers:
            scan_text = getattr(classifier, "scan_text", None)
            if scan_text is None:
                continue
            try:
                file_findings = scan_text(text)
            except Exception as e:
                func = getattr(classifier, "classifier_name", type(classifier).__name__)
                print(f"[FS] scan_text error {func} at {file_path}: {e}")
                continue

            for finding in file_findings:
                ln = finding.line_number or 1
                idx = max(0, min(ln - 1, line_end - 1)) if line_end else 0
                if not finding.line_text:
                    finding.line_text = lines[idx] if lines else ""
                before_start = max(0, idx - context_lines)
                after_end = min(line_end, idx + context_lines + 1)
                finding.context_before = "\n".join(lines[before_start:idx]) if lines else ""
                finding.context_after = "\n".join(lines[idx + 1:after_end]) if lines else ""
                finding.fragment_path = file_path
                findings.append(finding)

        # Построчный путь: классификаторы без scan_text (Credentials, Code и т.п.)
        for idx in range(line_end):
            line = lines[idx]
            line_num = idx + 1

            # Контекст вокруг строки
            before_start = max(0, idx - context_lines)
            after_end = min(line_end, idx + context_lines + 1)
            context_before = "\n".join(lines[before_start:idx])
            context_after = "\n".join(lines[idx + 1:after_end])

            for classifier in classifiers:
                if hasattr(classifier, "scan_text"):
                    continue
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

    @staticmethod
    def _file_pass_prefilter(text: str, classifiers: List[Any]) -> bool:
        """File-level prefilter (день 42).

        True — файл сканировать (хотя бы один классификатор видит признаки),
        False — пропустить файл целиком (ни один классификатор ничего не видит).
        """
        if not classifiers:
            return False
        for classifier in classifiers:
            fp = getattr(classifier, "file_prefilter", None)
            if fp is None:
                # Классификатор без file_prefilter — не можем гарантировать
                # «ничего не видно», поэтому сканируем файл.
                return True
            if fp(text):
                return True
        return False

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
                ocr_enabled=self.config.get("ocr_enabled", False),
            )
            result, error = extractor.extract_text(
                content, ext, Path(file_path).name
            )
            return result
        except Exception as e:
            print(f"[FS] Не удалось извлечь текст из {file_path}: {e}")
            return None


__all__ = ['FileSystemConnector', 'FilesystemConnector']