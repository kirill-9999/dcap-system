#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Коннектор к файловой системе
"""

import os
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable, Iterator

from scanner.src.finding import Finding
from scanner.connectors._text_scanner import (
    DEFAULT_TEXT_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    CRED_FILENAMES,
    is_supported_file,
    file_pass_prefilter,
    decode_text_bytes,
    scan_text as shared_scan_text,
    extract_document_text,
    _init_worker,
)

try:
    from core.base import FileContext, SourceType
except Exception:
    try:
        from scanner.core.base import FileContext, SourceType
    except Exception:

        class FileContext:
            def __init__(self, *args, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class SourceType:
            FILESYSTEM = "filesystem"


try:
    from utils.config import DEFAULT_SKIP_DIRS
except Exception:
    try:
        from scanner.utils.config import DEFAULT_SKIP_DIRS
    except Exception:
        DEFAULT_SKIP_DIRS = {
            '$Recycle.Bin', 'System Volume Information', 'tmp', 'temp', 'cache',
            '.git', '__pycache__', 'venv', 'node_modules', 'logs', 'models',
            '.hg', '.svn', 'vendor', 'dist', 'build', 'target', '.idea', '.vscode',
            '_example', 'sample', 'template', 'examples', 'samples', 'templates',
            'test_data', 'fixtures', 'mocks',
        }

logger = logging.getLogger("dcap-scanner")


# 53.4m (v3.14.11): для ProcessPoolExecutor функции должны быть верхнего
# уровня (spawn на Windows не умеет пиклить замыкания/методы). Классификаторы
# в воркер НЕ передаются экземплярами (singleton + spaCy-модели не picklable) —
# передаётся spec (имя + конфиг), а экземпляры создаются лениво при первом файле.
_WORKER_SELF = None
_WORKER_SPECS = None
_WORKER_CLASSIFIERS = None


def _process_worker_init(connector, specs):
    """Инициализатор воркера: свой temp_dir, connector и spec классификаторов."""
    global _WORKER_SELF, _WORKER_SPECS, _WORKER_CLASSIFIERS
    try:
        _init_worker()
    except Exception:
        pass
    _WORKER_SELF = connector
    _WORKER_SPECS = specs or []
    _WORKER_CLASSIFIERS = None


def _get_worker_classifiers():
    """Ленивое создание классификаторов в процессе-воркере (кеш на процесс)."""
    global _WORKER_CLASSIFIERS
    if _WORKER_CLASSIFIERS is None:
        from scanner.classifiers.factory import build_classifiers

        _WORKER_CLASSIFIERS = build_classifiers(_WORKER_SPECS)
    return _WORKER_CLASSIFIERS


def _process_scan_one(file_path):
    if _WORKER_SELF is None:
        return []
    try:
        if not _WORKER_SELF._within_size(file_path):
            return []
        return _WORKER_SELF.scan_file(file_path, _get_worker_classifiers())
    except Exception as e:
        print(f"[FS] Ошибка сканирования {file_path}: {e}", flush=True)
        import traceback

        traceback.print_exc()
        return []


try:
    from connectors.base import BaseConnector
except Exception:
    try:
        from scanner.connectors.base import BaseConnector
    except Exception:

        class BaseConnector:
            pass


class FileSystemConnector(BaseConnector):
    """Коннектор к локальной файловой системе"""

    @property
    def connector_type(self) -> SourceType:
        return SourceType.FILESYSTEM

    def configure(self, config: Dict[str, Any]) -> None:
        super().configure(config)
        self._extensions = config.get(
            "extensions",
            [
                "txt",
                "csv",
                "log",
                "json",
                "yaml",
                "yml",
                "xml",
                "toml",
                "ini",
                "cfg",
                "conf",
                "env",
                "envrc",
                "properties",
                "py",
                "js",
                "ts",
                "tsx",
                "java",
                "c",
                "cpp",
                "h",
                "hpp",
                "go",
                "rs",
                "sh",
                "bash",
                "zsh",
                "ps1",
                "cmd",
                "bat",
                "sql",
                "php",
                "rb",
                "lua",
                "r",
                "swift",
                "kt",
                "md",
                "rst",
                "html",
                "css",
                "scss",
                "dockerfile",
                "makefile",
                "tf",
                "hcl",
                "pem",
                "key",
                "crt",
                "csr",
                "cert",
                "p12",
                "pfx",
                "jks",
                "doc",
                "docx",
                "xls",
                "xlsx",
                "pdf",
                "png",
                "jpg",
                "jpeg",
                "gif",
                "bmp",
                "tiff",
                "webp",
            ],
        )
        self._skip_dirs = config.get(
            "skip_dirs",
            [
                "$Recycle.Bin",
                "System Volume Information",
                "tmp",
                "temp",
                "cache",
                ".git",
                "__pycache__",
                "venv",
                "node_modules",
                "logs",
                "models",
                ".hg",
                ".svn",
                "vendor",
                "dist",
                "build",
                "target",
                ".idea",
                ".vscode",
                "_example",
                "sample",
                "template",
                "examples",
                "samples",
                "templates",
                "test_data",
                "fixtures",
                "mocks",
            ],
        )
        self._max_file_size_mb = config.get("max_file_size_mb", 50)
        self._recursive = config.get("recursive", True)
        self._buffer_size = config.get("buffer_size", 1024 * 1024)
        self._max_text_chars = config.get("max_text_chars", 200000)
        self._cred_filenames = CRED_FILENAMES
        self._text_extensions = {
            "txt",
            "csv",
            "log",
            "json",
            "yaml",
            "yml",
            "xml",
            "toml",
            "ini",
            "cfg",
            "conf",
            "env",
            "envrc",
            "properties",
            "py",
            "js",
            "ts",
            "tsx",
            "jsx",
            "java",
            "c",
            "cpp",
            "h",
            "hpp",
            "go",
            "rs",
            "sh",
            "bash",
            "zsh",
            "ps1",
            "cmd",
            "bat",
            "sql",
            "php",
            "rb",
            "pl",
            "lua",
            "r",
            "swift",
            "kt",
            "md",
            "rst",
            "html",
            "css",
            "scss",
            "dockerfile",
            "makefile",
            "tf",
            "hcl",
            "pem",
            "key",
            "crt",
            "csr",
            "cert",
            "p12",
            "pfx",
            "jks",
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
                ext = file_path.suffix.lower().lstrip(".")

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
                    metadata={"extension": ext, "filename": file},
                )

    def get_content(self, file_context: FileContext) -> Optional[FileContext]:
        """Чтение файла с буферизацией (день 34.5).

        Для текстовых форматов чтение останавливается после накопления
        max_text_chars байт — дальнейший контент не нужен классификатору.
        """
        try:
            ext = (
                file_context.path.replace("\\", "/").rsplit(".", 1)[-1].lower()
                if "." in file_context.path
                else ""
            )
            limit = self._max_text_chars if ext in self._text_extensions else None

            chunks = []
            total = 0
            with open(file_context.path, "rb") as f:
                while True:
                    chunk = f.read(self._buffer_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if limit is not None and total >= limit:
                        break
            file_context.content = b"".join(chunks)
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

        self._text_extensions = (
            set(config.get("text_extensions", list(DEFAULT_TEXT_EXTENSIONS)))
            | DEFAULT_TEXT_EXTENSIONS
        )
        self._skip_dirs = set(config.get("skip_dirs", list(DEFAULT_SKIP_DIRS)))
        self._cred_filenames = CRED_FILENAMES
        self._recursive = config.get("recursive", True)
        self._context_lines = int(config.get("context_lines", 2))
        self._max_file_size_mb = int(config.get("max_file_size_mb", 50))
        self._max_text_chars = int(config.get("max_text_chars", 200000))
        self._buffer_size = int(config.get("buffer_size", 1024 * 1024))
        # Параллельное сканирование файлов (день 42); 1 = последовательный режим
        self._max_workers = int(config.get("max_parallel_files", 1) or 1)
        # 53.4m (v3.14.11): multiprocessing
        perf = config.get("performance") or {}
        self._executor_type = (
            str(config.get("executor") or perf.get("executor") or "process").strip().lower()
        )
        self._max_workers_proc = int(
            perf.get("max_workers") or config.get("max_workers") or self._max_workers or 4
        )
        self._chunk_size = int(perf.get("chunk_size") or 100)

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
        try:
            stack = [str(folder.absolute())]
            while stack:
                current = stack.pop()
                try:
                    with os.scandir(current) as it:
                        for entry in it:
                            try:
                                if entry.is_dir(follow_symlinks=False):
                                    name = entry.name
                                    if name in self._skip_dirs:
                                        continue
                                    if not self._recursive and current != str(folder.absolute()):
                                        continue
                                    stack.append(entry.path)
                                    continue
                                if entry.is_file(follow_symlinks=False):
                                    file_path = Path(entry.path)
                                    if self._is_supported(file_path):
                                        result.append(str(file_path.absolute()))
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception:
            # fallback
            for r, dirs, files in os.walk(str(folder)):
                if not self._recursive:
                    dirs.clear()
                dirs[:] = [d for d in dirs if d not in self._skip_dirs]
                for f in files:
                    file_path = Path(r) / f
                    if self._is_supported(file_path):
                        result.append(str(file_path.absolute()))
        return result

    def _is_supported(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower().lstrip(".")
        return is_supported_file(
            ext,
            file_path.name,
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

        # Параллельный режим (день 53.4m): ProcessPoolExecutor по умолчанию.
        # Вложенный executor не нужен — max_workers_proc процессов, каждый
        # обрабатывает один файл за раз (GIL на процесс).
        executor_type = str(getattr(self, "_executor_type", "process") or "process").lower()
        max_workers_proc = int(getattr(self, "_max_workers_proc", max_workers) or max_workers)
        chunk_size = int(getattr(self, "_chunk_size", 100) or 100)
        max_workers_proc = max(1, max_workers_proc)

        from concurrent.futures import (
            FIRST_COMPLETED,
            ProcessPoolExecutor,
            ThreadPoolExecutor,
            wait,
        )
        from concurrent.futures.process import BrokenProcessPool
        import threading

        lock = threading.Lock()
        done_counter = [0]

        ex = None
        submit = None
        if executor_type == "process":
            from scanner.classifiers.factory import classifier_specs, worker_specs

            specs = worker_specs(classifier_specs(classifiers))
            if specs is not None:
                try:
                    ex = ProcessPoolExecutor(
                        max_workers=max_workers_proc,
                        initializer=_process_worker_init,
                        initargs=(self, specs),
                    )
                    submit = lambda fp: ex.submit(_process_scan_one, fp)  # noqa: E731
                    logger.info(
                        "[FS] ProcessPoolExecutor: %d процессов, chunk=%d",
                        max_workers_proc,
                        chunk_size,
                    )
                except Exception as e:
                    logger.warning("[FS] ProcessPoolExecutor недоступен (%s) — thread", e)
                    ex = None
            else:
                logger.warning(
                    "[FS] Классификаторы не сериализуются — process-режим невозможен, thread"
                )

        if ex is None:
            ex = ThreadPoolExecutor(max_workers=max_workers_proc)
            submit = lambda fp: ex.submit(_scan_one, fp)  # noqa: E731
            logger.info("[FS] ThreadPoolExecutor: %d потоков", max_workers_proc)

        # Ограниченное окно задач: не держим в памяти futures на весь каталог
        # (2 000 000 файлов), но и не теряем параллелизм.
        in_flight_limit = max(1, max(max_workers_proc, chunk_size))

        def _on_done(file_path: str, result: List[Finding]) -> None:
            with lock:
                done_counter[0] += 1
                current = done_counter[0]
            if progress_callback:
                try:
                    progress_callback(1, current, total, file_path)
                except Exception:
                    pass

        try:
            pending = {}
            file_iter = iter(files)
            for _ in range(in_flight_limit):
                nxt = next(file_iter, None)
                if nxt is None:
                    break
                pending[submit(nxt)] = nxt

            while pending:
                if _stopped():
                    logger.info("[FS] Сканирование остановлено (stop_event)")
                    break
                done, _ = wait(list(pending), return_when=FIRST_COMPLETED)
                for future in done:
                    file_path = pending.pop(future)
                    try:
                        result = future.result() or []
                    except Exception as e:
                        logger.warning("[FS] Ошибка сканирования %s: %s", file_path, e)
                        result = []
                    findings.extend(result)
                    _on_done(file_path, result)
                if _stopped():
                    break
                for _ in done:
                    nxt = next(file_iter, None)
                    if nxt is None:
                        break
                    pending[submit(nxt)] = nxt
        except BrokenProcessPool as e:
            # Воркер упал (OOM/kill): не валим весь скан — забираем готовые
            # результаты и возвращаем то, что успели (53.4m).
            logger.error("[FS] Пул процессов сломан (%s) — скан прерван", e)
            for future in list(pending):
                if future.done() and not future.cancelled():
                    try:
                        findings.extend(future.result() or [])
                    except Exception:
                        pass
            pending.clear()
        except KeyboardInterrupt:
            logger.info("[FS] Ctrl+C — graceful shutdown (сохранено находок: %d)", len(findings))
            for future in list(pending):
                if future.done() and not future.cancelled():
                    try:
                        findings.extend(future.result() or [])
                    except Exception:
                        pass
                else:
                    future.cancel()
            pending.clear()
        finally:
            try:
                ex.shutdown(wait=True)
            except Exception:
                pass

        return findings

    def scan_file(self, file_path: str, classifiers: List[Any]) -> List[Finding]:
        """Сканирует один файл построчно, возвращает список Finding."""
        p = Path(file_path)
        if not p.exists():
            return []

        ext = p.suffix.lower().lstrip(".")

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
            with open(p, "rb") as f:
                return f.read()
        except Exception as e:
            logger.warning("[FS] Не удалось открыть %s: %s", file_path, e)
            return None

    def _read_text(self, file_path: str) -> Optional[str]:
        """Буферизованное чтение текста (максимум self._max_text_chars символов)."""
        try:
            chunks = []
            total = 0
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(self._buffer_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= self._max_text_chars:
                        break
            # Двоичный мусор без текстовых признаков — пропускаем
            return decode_text_bytes(b"".join(chunks))
        except Exception as e:
            logger.warning("[FS] Не удалось прочитать %s: %s", file_path, e)
            return None


__all__ = ["FileSystemConnector", "FilesystemConnector"]

# Регистрация в фабрике (день 53.1b)
from scanner.connectors.factory import register_line_connector  # noqa: E402

register_line_connector("filesystem", lambda cfg: FilesystemConnector(cfg))
