#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Общий построчный пайплайн для текстовых источников.

Вынесено из FilesystemConnector (день 53.1b, BACKLOG-097), чтобы S3LineConnector
(53.2) и другие будущие коннекторы переиспользовали одну и ту же логику:
построчный прогон через scan_line, контекст вокруг строки, префильтр,
диспетчер по расширению.

Здесь только функции — никакого состояния источника. Чтение конкретного
источника (FS/ S3/...) остаётся в коннекторе.
"""
import logging
import os
import tempfile
import threading
from typing import Any, Dict, List, Optional, Tuple

from scanner.src.finding import Finding

logger = logging.getLogger("dcap-scanner")

# 53.4k (v3.14.9): singleton DocumentExtractor для linewise-пути.
_EXTRACTOR_CACHE: dict = {}
_EXTRACTOR_CACHE_LOCK = threading.Lock()

# 53.4m (v3.14.11): temp_dir на процесс (нет race condition на ocr_* файлах).
WORKER_TEMP_DIR = None


def _init_worker():
    """Инициализация в каждом процессе (53.4m).

    logging базовый, temp_dir свой на процесс.
    Классификаторы и модели — лениво (get_classifier) при первом файле.
    """
    global WORKER_TEMP_DIR
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(process)d] %(levelname)s %(name)s: %(message)s",
    )
    try:
        WORKER_TEMP_DIR = tempfile.mkdtemp(prefix="dcap_worker_%s_" % os.getpid())
    except Exception:
        WORKER_TEMP_DIR = tempfile.gettempdir()


def _get_worker_temp_dir():
    global WORKER_TEMP_DIR
    if WORKER_TEMP_DIR is None:
        try:
            WORKER_TEMP_DIR = tempfile.mkdtemp(prefix="dcap_worker_%s_" % os.getpid())
        except Exception:
            WORKER_TEMP_DIR = tempfile.gettempdir()
    return WORKER_TEMP_DIR


def _get_executor(executor_type: str, max_workers: int):
    """Фабрика executor'ов (53.4m)."""
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

    etype = (executor_type or "process").strip().lower()
    try:
        mw = int(max_workers) if max_workers is not None else 4
    except Exception:
        mw = 4
    mw = max(1, mw)
    if etype == "process":
        return ProcessPoolExecutor(max_workers=mw, initializer=_init_worker)
    return ThreadPoolExecutor(max_workers=mw)


def _get_document_extractor(temp_dir, ocr_enabled: bool):
    """Вернуть (пере)используемый DocumentExtractor по ключу (temp_dir, ocr_enabled).

    В процесс-воркере (53.4m) temp_dir — свой на процесс (WORKER_TEMP_DIR).
    """
    from utils.document_extractor import DocumentExtractor

    try:
        import multiprocessing as _mp
        if _mp.current_process().name != "MainProcess":
            td = _get_worker_temp_dir()
            if td:
                temp_dir = td
    except Exception:
        pass

    key = (str(temp_dir), bool(ocr_enabled))
    ex = _EXTRACTOR_CACHE.get(key)
    if ex is not None:
        return ex
    with _EXTRACTOR_CACHE_LOCK:
        ex = _EXTRACTOR_CACHE.get(key)
        if ex is None:
            ex = DocumentExtractor(temp_dir=temp_dir, ocr_enabled=ocr_enabled)
            _EXTRACTOR_CACHE[key] = ex
    return ex


# Текстовые расширения по умолчанию (день 40.2)
DEFAULT_TEXT_EXTENSIONS = {
    'txt', 'csv', 'log', 'json', 'yaml', 'yml', 'xml', 'toml', 'ini', 'cfg', 'conf',
    'env', 'envrc', 'properties', 'py', 'js', 'ts', 'tsx', 'jsx', 'java', 'c', 'cpp',
    'h', 'hpp', 'go', 'rs', 'sh', 'bash', 'zsh', 'ps1', 'cmd', 'bat', 'sql', 'php',
    'rb', 'pl', 'lua', 'r', 'swift', 'kt', 'md', 'rst', 'html', 'css', 'scss',
    'dockerfile', 'makefile', 'tf', 'hcl',
    'pem', 'key', 'crt', 'csr', 'cert', 'p12', 'pfx', 'jks',
}

DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx'}
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'}

# Имена файлов-носителей учётных данных (сканируются по имени, без расширения)
CRED_FILENAMES = {
    'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519',
    '.pgpass', '.netrc', '_netrc', 'kubeconfig', '.kubeconfig', 'jaas.conf',
    'kafka_client_jaas.conf', 'secrets', 'secrets.json', 'secrets.yaml',
    'secrets.yml', 'secret', '.env', '.envrc', '.env.local', '.env.production',
    '.htpasswd', 'passwd', 'shadow', '.npmrc', '.pypirc', '.gemrc', '.boto',
    '.my.cnf', '.my.ini', '.dockerignore', '.gitignore', '.gitattributes',
}


def is_supported_file(
    ext: str,
    filename: str,
    text_extensions: Optional[set] = None,
    cred_filenames: Optional[set] = None,
) -> bool:
    """Файл поддерживается для сканирования (по расширению или credential-имени)."""
    text_ext = text_extensions if text_extensions is not None else DEFAULT_TEXT_EXTENSIONS
    cred = cred_filenames if cred_filenames is not None else CRED_FILENAMES
    e = (ext or "").lower().lstrip(".")
    if e in text_ext:
        return True
    if e in DOCUMENT_EXTENSIONS or e in IMAGE_EXTENSIONS:
        return True
    if (filename or "").lower() in cred:
        return True
    return False


def decode_text_bytes(content: bytes) -> Optional[str]:
    """Декодировать байты в текст (utf-8 strict → cp1251 strict → utf-8 ignore).

    Возвращает None, если это явно бинарный мусор (\x00 в первых 4 КБ).

    BUG-136 (день 53.2): раньше цикл использовал errors="ignore" на первой
    итерации (utf-8), из-за чего ветка cp1251 была недостижима — файлы в
    cp1251 декодировались в мусор («пустую строку»). Теперь — строгий декод,
    и только если оба провалились, fallback на utf-8 с errors="ignore".
    """
    if content[:4096] and b"\x00" in content[:4096]:
        return None
    for encoding in ("utf-8", "cp1251"):
        try:
            return content.decode(encoding)  # strict — падает на несовпадении
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def file_pass_prefilter(text: str, classifiers: List[Any]) -> bool:
    """File-level prefilter (день 42).

    True — файл сканировать; False — пропустить файл целиком (ни один
    классификатор не видит быстрых признаков).
    """
    if not classifiers:
        return False
    for classifier in classifiers:
        fp = getattr(classifier, "file_prefilter", None)
        if fp is None:
            # Классификатор без file_prefilter — не можем гарантировать
            # «ничего не видно», поэтому сканируем файл.
            return True
        try:
            if fp(text):
                return True
        except Exception as exc:
            logger.debug("file_prefilter error %s: %s", classifier, exc)
            return True
    return False


def dedup_findings_by_file(findings: List[Finding]) -> List[Finding]:
    """Дедуп находок в рамках одного файла (53.4l, v3.14.10).

    Одно и то же совпадение (category + match_text), встречающееся в файле
    многократно, схлопывается в одну находку. Все вхождения сохраняются в
    metadata["locations"] (line/context_before/context_after/start_pos/end_pos),
    line_number находки = первое вхождение.

    Зачем: без дедупа на синтетических PII-файлах («Иванов Иван, 12.05.1990,
    Москва») каждая строка даёт отдельную находку — до 600+ находок на файл
    (finding-взрыв). После дедупа — одна находка на уникальное совпадение.
    """
    if not findings:
        return findings

    groups: Dict[Tuple[str, str], List[Finding]] = {}
    for f in findings:
        key = (
            getattr(f, "category", "") or "",
            getattr(f, "match_text", "") or "",
        )
        groups.setdefault(key, []).append(f)

    deduped: List[Finding] = []
    for items in groups.values():
        try:
            first = min(
                items,
                key=lambda x: (
                    int(getattr(x, "line_number", 0) or 0),
                    int(getattr(x, "start_pos", 0) or 0),
                ),
            )
        except Exception:
            first = items[0]

        locations = []
        for it in items:
            locations.append({
                "line": getattr(it, "line_number", None),
                "context_before": getattr(it, "context_before", "") or "",
                "context_after": getattr(it, "context_after", "") or "",
                "start_pos": getattr(it, "start_pos", None),
                "end_pos": getattr(it, "end_pos", None),
            })
        try:
            locations.sort(key=lambda x: (x.get("line") or 0, x.get("start_pos") or 0))
        except Exception:
            pass

        if not getattr(first, "metadata", None):
            first.metadata = {}
        first.metadata["locations"] = locations
        first.metadata["locations_count"] = len(locations)
        deduped.append(first)

    return deduped


def scan_text(
    text: str,
    classifiers: List[Any],
    file_path: str,
    context_lines: int = 2,
    max_text_chars: int = 200000,
) -> List[Finding]:
    """Сканирует текст классификаторами и возвращает список Finding.

    Классификаторы с файловым анализом (scan_text) вызываются один раз на
    весь текст (PII — один вызов Presidio на файл). Остальные — построчно
    через scan_line. Контекст (before/after) подрезается `context_lines` строк.
    """
    if len(text) > max_text_chars:
        text = text[:max_text_chars]

    if not file_pass_prefilter(text, classifiers):
        return []

    lines = text.splitlines()
    line_end = len(lines)
    findings: List[Finding] = []

    # Файловый путь: scan_text(text) — один раз на весь файл.
    for classifier in classifiers:
        scan_text_fn = getattr(classifier, "scan_text", None)
        if scan_text_fn is None:
            continue
        try:
            file_findings = scan_text_fn(text)
        except Exception as exc:
            name = getattr(classifier, "classifier_name", type(classifier).__name__)
            logger.warning("[TextScanner] scan_text error %s at %s: %s", name, file_path, exc)
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

    # Построчный путь: классификаторы без scan_text (Credentials, Code).
    for idx in range(line_end):
        line = lines[idx]
        line_num = idx + 1
        before_start = max(0, idx - context_lines)
        after_end = min(line_end, idx + context_lines + 1)
        context_before = "\n".join(lines[before_start:idx])
        context_after = "\n".join(lines[idx + 1:after_end])

        for classifier in classifiers:
            if hasattr(classifier, "scan_text"):
                continue
            scan_line_fn = getattr(classifier, "scan_line", None)
            if scan_line_fn is None:
                continue
            try:
                line_findings = scan_line_fn(line, line_num)
            except Exception as exc:
                name = getattr(classifier, "classifier_name", type(classifier).__name__)
                logger.warning(
                    "[TextScanner] scan_line error %s at %s:%d: %s",
                    name, file_path, line_num, exc,
                )
                continue

            for finding in line_findings:
                finding.line_text = line
                finding.context_before = context_before
                finding.context_after = context_after
                finding.fragment_path = file_path
                findings.append(finding)

    # 53.4l (v3.14.10): дедуп в рамках файла — одно совпадение = одна находка,
    # все вхождения в metadata["locations"].
    findings = dedup_findings_by_file(findings)

    return findings


def extract_document_text(
    content: bytes,
    ext: str,
    filename: str,
    ocr_enabled: bool = False,
) -> Optional[str]:
    """Извлечь текст из PDF/Office/изображения (через DocumentExtractor).

    Принимает БАЙТЫ (а не путь) — чтобы FS и S3 могли переиспользовать.

    BUG-137 (v3.13.36): OCREngine внутри DocumentExtractor работает в своей
    уникальной подпапке temp, поэтому параллельные вызовы (по файлу на поток)
    не стирают чужие temp-файлы. Если извлечение вернуло пусто при включённом
    OCR — пишем WARNING (не молчаливая потеря).
    """
    try:
        import tempfile as _tf
        from pathlib import Path as _P

        extractor = _get_document_extractor(
            _P(_tf.gettempdir()),
            ocr_enabled,
        )
        result, error = extractor.extract_text(content, ext, filename)
        if ocr_enabled and not result and error:
            logger.warning(
                "[TextScanner] OCR/извлечение вернуло пусто для %s: %s",
                filename, error,
            )
        return result
    except Exception as exc:
        logger.warning("[TextScanner] extract_document failed for %s: %s", filename, exc)
        return None


__all__ = [
    "DEFAULT_TEXT_EXTENSIONS",
    "DOCUMENT_EXTENSIONS",
    "IMAGE_EXTENSIONS",
    "CRED_FILENAMES",
    "is_supported_file",
    "decode_text_bytes",
    "file_pass_prefilter",
    "scan_text",
    "dedup_findings_by_file",
    "extract_document_text",
]
