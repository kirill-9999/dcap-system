#!/usr/bin/env python3
"""
Сканер папок на наличие паролей и SSH-ключей.

Стандартный режим: regex-паттерны (быстро, без зависимостей).
Опционально (--presidio): Presidio + spaCy (точнее, тяжелее).

Использование:
    python scan_folder.py <папка> <лог-файл>
    python scan_folder.py D:\\Projects D:\\logs\\scan.json
    python scan_folder.py \\\\server\\share \\\\server\\logs\\scan.json
    python scan_folder.py D:\\Projects D:\\logs\\scan.json --presidio
    python scan_folder.py D:\\Projects D:\\logs\\scan.json --presidio --encoding cp1251
"""
import sys
import os
import re
import time
import math
import threading
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# Regex-паттерны (на основе scanner/classifiers/credentials_classifier.py)
# ---------------------------------------------------------------------------

_CRED_PATTERNS: List[Dict] = [
    {
        "name": "PASSWORD",
        "pattern": re.compile(
            r"(?:password|passwd|pwd|пароль|pass)\s*[:=]\s*[\'\"]?([^\s\'\"\\\\]{4,128})[\'\"]?",
            re.IGNORECASE | re.MULTILINE,
        ),
        "subcategory": "CRED_PASSWORD",
        "confidence": 0.75,
        "entropy_check": True,
    },
    {
        "name": "PASSWORD_QUOTED",
        "pattern": re.compile(
            r'(?:password|passwd|pwd|пароль|pass)\s*[:=]\s*[\'"]([^\s\'"]{4,128})[\'"]',
            re.IGNORECASE | re.MULTILINE,
        ),
        "subcategory": "CRED_PASSWORD",
        "confidence": 0.85,
        "entropy_check": False,
    },
    {
        "name": "SSH_PRIVATE_KEY",
        "pattern": re.compile(
            r"-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH|DSA|PGP)\s+PRIVATE\s+KEY-----",
            re.IGNORECASE,
        ),
        "subcategory": "CRED_SSH_PRIVATE_KEY",
        "confidence": 0.99,
        "entropy_check": False,
    },
    {
        "name": "SSH_PUBLIC_KEY",
        "pattern": re.compile(
            r"ssh-(?:rsa|dss|ed25519)\s+[A-Za-z0-9+/=]{100,}",
        ),
        "subcategory": "CRED_SSH_PUBLIC_KEY",
        "confidence": 0.95,
        "entropy_check": False,
    },
    {
        "name": "SSH_KEY_FILE",
        "pattern": re.compile(
            r"(?:id_rsa|id_dsa|id_ecdsa|id_ed25519|\.ssh/[\w._-]+)",
            re.IGNORECASE,
        ),
        "subcategory": "CRED_SSH_KEY_PATH",
        "confidence": 0.70,
        "entropy_check": False,
    },
    {
        "name": "API_KEY",
        "pattern": re.compile(
            r"(?:api[_-]?key|apikey)\s*[:=]\s*[\'\"]?([A-Za-z0-9]{20,64})[\'\"]?",
            re.IGNORECASE | re.MULTILINE,
        ),
        "subcategory": "CRED_API_KEY",
        "confidence": 0.85,
        "entropy_check": True,
    },
    {
        "name": "AWS_ACCESS_KEY",
        "pattern": re.compile(r"AKIA[0-9A-Z]{16}"),
        "subcategory": "CRED_AWS_ACCESS_KEY",
        "confidence": 0.95,
        "entropy_check": False,
    },
    {
        "name": "AWS_SECRET_KEY",
        "pattern": re.compile(
            r"(?:aws_secret_access_key|secret_key)\s*[:=]\s*[\'\"]?([A-Za-z0-9/+=]{40})[\'\"]?",
            re.IGNORECASE | re.MULTILINE,
        ),
        "subcategory": "CRED_AWS_SECRET_KEY",
        "confidence": 0.95,
        "entropy_check": True,
    },
    {
        "name": "GITHUB_TOKEN",
        "pattern": re.compile(r"ghp_[A-Za-z0-9]{36}"),
        "subcategory": "CRED_GITHUB_TOKEN",
        "confidence": 0.95,
        "entropy_check": False,
    },
    {
        "name": "GITHUB_PAT",
        "pattern": re.compile(r"github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}"),
        "subcategory": "CRED_GITHUB_TOKEN",
        "confidence": 0.95,
        "entropy_check": False,
    },
    {
        "name": "SLACK_TOKEN",
        "pattern": re.compile(r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}"),
        "subcategory": "CRED_SLACK_TOKEN",
        "confidence": 0.90,
        "entropy_check": False,
    },
    {
        "name": "JWT_TOKEN",
        "pattern": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        "subcategory": "CRED_JWT_TOKEN",
        "confidence": 0.90,
        "entropy_check": False,
    },
    {
        "name": "GENERIC_TOKEN",
        "pattern": re.compile(
            r"(?:token|secret|access_key|private_key)\s*[:=]\s*[\'\"]?([A-Za-z0-9_\-]{20,128})[\'\"]?",
            re.IGNORECASE | re.MULTILINE,
        ),
        "subcategory": "CRED_GENERIC_TOKEN",
        "confidence": 0.70,
        "entropy_check": True,
    },
    {
        "name": "BEARER_TOKEN",
        "pattern": re.compile(r"Bearer\s+([A-Za-z0-9_\-\.]{20,})"),
        "subcategory": "CRED_BEARER_TOKEN",
        "confidence": 0.85,
        "entropy_check": True,
    },
    {
        "name": "DATABASE_URL",
        "pattern": re.compile(
            r"(?:postgresql|mysql|mongodb|redis|sqlite|postgres)://[^\s\'\"]+",
            re.IGNORECASE,
        ),
        "subcategory": "CRED_DATABASE_URL",
        "confidence": 0.90,
        "entropy_check": False,
    },
    {
        "name": "PRIVATE_KEY_FILE",
        "pattern": re.compile(
            r"(?:private_key_file|key_file|ssl_key)\s*[:=]\s*[\'\"]?([^\s\'\"]+\.pem)[\'\"]?",
            re.IGNORECASE,
        ),
        "subcategory": "CRED_PRIVATE_KEY_PATH",
        "confidence": 0.80,
        "entropy_check": False,
    },
]

# Дополнительные паттерны для паролей (сетевые конфиги, ini/cfg/yaml)
_NETWORK_PASS_PATTERNS: List[Dict] = [
    {
        "name": "NETWORK_PASSWORD",
        "pattern": re.compile(
            r"(?:password|pass|passwd|pwd)\s*[:=]\s*[\'\"]([^\s\'\"]{3,128})[\'\"]",
            re.IGNORECASE,
        ),
        "subcategory": "CRED_PASSWORD",
        "confidence": 0.80,
        "entropy_check": True,
    },
    {
        "name": "ENV_PASSWORD",
        "pattern": re.compile(
            r"(?:DB_PASSWORD|MYSQL_PASSWORD|POSTGRES_PASSWORD|REDIS_PASSWORD|MONGO_PASSWORD|SMTP_PASSWORD)"
            r"\s*[:=]\s*[\'\"]?([^\s\'\"]{3,128})[\'\"]?",
            re.IGNORECASE,
        ),
        "subcategory": "CRED_PASSWORD",
        "confidence": 0.90,
        "entropy_check": False,
    },
]


# ---------------------------------------------------------------------------
# Entropy
# ---------------------------------------------------------------------------


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: Dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(s)
    return -sum(
        (count / length) * __import__("math").log2(count / length) for count in freq.values()
    )


# ---------------------------------------------------------------------------
# Presidio-интеграция (опционально)
# ---------------------------------------------------------------------------

_presidio_analyzer = None
_presidio_available = False


def _init_presidio():
    global _presidio_analyzer, _presidio_available
    if _presidio_available:
        return _presidio_analyzer
    try:
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        configuration = {
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": "en", "model_name": "en_core_web_sm"},
                {"lang_code": "ru", "model_name": "ru_core_news_sm"},
            ],
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()

        _presidio_analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine,
            supported_languages=["ru", "en"],
        )
        _presidio_available = True
        return _presidio_analyzer
    except Exception as e:
        print(f"[presidio] Инициализация не удалась ({e}), работает только regex-режим")
        _presidio_available = False
        return None


def _scan_presidio(text: str, file_path: str, line_offset: int = 0) -> List[Dict]:
    analyzer = _init_presidio()
    if analyzer is None:
        return []
    findings: List[Dict] = []
    try:
        results = analyzer.analyze(text=text, language="ru")
    except Exception:
        try:
            results = analyzer.analyze(text=text, language="en")
        except Exception:
            return []
    for r in results:
        entity = r.entity_type
        if entity not in (
            "PERSON",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "CREDIT_CARD",
            "IP_ADDRESS",
            "URL",
            "IBAN_CODE",
        ):
            continue
        start_line = line_offset + text[: r.start].count("\n") + 1
        value = text[r.start : r.end]
        context_start = max(0, r.start - 60)
        context_end = min(len(text), r.end + 60)
        findings.append(
            {
                "category": "pii",
                "subcategory": f"PII_{entity}",
                "file_path": file_path,
                "line_number": start_line,
                "value": value[:200],
                "confidence": round(r.score, 2),
                "context": text[context_start:context_end].replace("\n", " "),
                "detection_method": "presidio",
            }
        )
    return findings


# ---------------------------------------------------------------------------
# Файловые утилиты
# ---------------------------------------------------------------------------

# Расширения, которые сканируются как текст
_TEXT_EXTENSIONS = {
    "txt",
    "csv",
    "log",
    "json",
    "xml",
    "yaml",
    "yml",
    "toml",
    "ini",
    "cfg",
    "conf",
    "env",
    "properties",
    "py",
    "js",
    "ts",
    "jsx",
    "tsx",
    "java",
    "c",
    "cpp",
    "h",
    "hpp",
    "cs",
    "go",
    "rs",
    "php",
    "rb",
    "swift",
    "kt",
    "sh",
    "bash",
    "zsh",
    "ps1",
    "bat",
    "cmd",
    "vbs",
    "pl",
    "lua",
    "r",
    "sql",
    "html",
    "css",
    "scss",
    "less",
    "md",
    "rst",
    "dockerfile",
    "makefile",
    "tf",
    "hcl",
    "gradle",
    "sbt",
    "cmake",
    "pem",
    "key",
    "cert",
    "crt",
    "p12",
    "pfx",
    "jks",
}

# Расширения-праттерны для файлов без расширения
_NAME_PATTERNS = {
    "dockerfile",
    "makefile",
    "rakefile",
    "gemfile",
    "procfile",
    "vagrantfile",
}

# Пропускаемые директории
_SKIP_DIRS = {
    "$Recycle.Bin",
    "System Volume Information",
    "tmp",
    "temp",
    "cache",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "site-packages",
    ".eggs",
    "egg-info",
}

# Максимальный размер файла для чтения (50 MB)
_MAX_FILE_SIZE = 50 * 1024 * 1024

# Максимальный размер текста для сканирования
_MAX_TEXT_SIZE = 200_000


def _read_text_file(path: str, encoding: str = "utf-8") -> Optional[str]:
    """Читает текстовый файл с fallback по кодировке."""
    try:
        size = os.path.getsize(path)
        if size > _MAX_FILE_SIZE:
            return None
    except OSError:
        return None

    for enc in (encoding, "utf-8", "cp1251"):
        try:
            with open(path, "r", encoding=enc, errors="ignore") as f:
                text = f.read(_MAX_TEXT_SIZE + 1000)
            if len(text) > _MAX_TEXT_SIZE:
                text = text[:_MAX_TEXT_SIZE]
            return text
        except Exception:
            continue
    return None


def _should_scan(path: str) -> bool:
    """Определяет, стоит ли сканировать файл."""
    p = Path(path)
    name_lower = p.name.lower()
    ext = p.suffix.lstrip(".").lower()

    if ext in _TEXT_EXTENSIONS:
        return True
    if name_lower in _NAME_PATTERNS:
        return True
    if not ext and name_lower:
        try:
            with open(path, "rb") as f:
                chunk = f.read(512)
            if not chunk:
                return False
            text_bytes = chunk
            null_count = text_bytes.count(b"\x00")
            if null_count > len(text_bytes) * 0.05:
                return False
            return True
        except Exception:
            return False
    return False


def _line_number_at(text: str, char_offset: int) -> int:
    """Конвертирует символьный offset в номер строки."""
    return text[:char_offset].count("\n") + 1


def _resolve_log_path(log_arg: str) -> str:
    """Возвращает путь к логу, добавляя время запуска в имя файла.

    Если передан путь к вложенной папке — создаёт папку и кладёт туда
    scan_<datetime>.log. Если передан файл (с расширением) — вставляет
    datetime перед расширением: <name>_<datetime>.log
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    arg = os.path.abspath(log_arg)
    base = os.path.basename(arg)
    if os.path.isdir(arg) or "." not in base:
        log_dir = arg
        name = f"scan_{ts}.log"
    else:
        log_dir = os.path.dirname(arg)
        stem, ext = os.path.splitext(base)
        name = f"{stem}_{ts}{ext}"
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, name)


# ---------------------------------------------------------------------------
# Многопоточный прогресс (отдельная строка на каждый поток)
# ---------------------------------------------------------------------------


class _MultiProgress:
    """Рисует по строке прогресса на каждый рабочий поток.

    Каждый поток обновляет свою строку; строки перерисовываются под
    блокировкой, чтобы не перемешивались при конкурентной записи.
    """

    def __init__(self, rows: int):
        self.rows = rows
        self.lock = threading.Lock()
        # {worker_id: {"current": int, "total": int, "text": str}}
        self._data: Dict[int, Dict] = {
            wid: {"current": 0, "total": 0, "text": ""} for wid in range(rows)
        }
        self._started = False

    def _move_up(self):
        # Перемещаем курсор вверх на количество строк прогресса
        if self.rows > 1:
            sys.stdout.write(f"\033[{self.rows}A")

    def _draw_row(self, wid: int):
        d = self._data[wid]
        cur, total = d["current"], d["total"]
        text = d["text"][:40]
        if total:
            pct = cur * 100.0 / total
            cols = 30
            filled = int(cols * cur / total) if total else 0
            bar = "#" * filled + "-" * (cols - filled)
            sys.stdout.write(
                f"\033[2K\r[worker {wid + 1}] [{bar}] {pct:5.1f}%" f" ({cur:>6}/{total}) {text}"
            )
        else:
            sys.stdout.write(f"\033[2K\r[worker {wid + 1}] {cur} файлов {text}")

    def set_total(self, wid: int, total: int):
        with self.lock:
            self._data[wid]["total"] = total

    def tick(self, wid: int, text: str = ""):
        with self.lock:
            self._data[wid]["current"] += 1
            self._data[wid]["text"] = text
            self._draw()

    def _draw(self):
        if not self._started:
            # Первый вывод: освобождаем строки под прогресс
            sys.stdout.write("\n" * self.rows)
            self._started = True
        self._move_up()
        for wid in range(self.rows):
            self._draw_row(wid)
            if wid < self.rows - 1:
                sys.stdout.write("\n")
        sys.stdout.flush()

    def clear(self):
        with self.lock:
            if not self._started:
                return
            self._move_up()
            for wid in range(self.rows):
                sys.stdout.write("\033[2K\r")
                if wid < self.rows - 1:
                    sys.stdout.write("\n")
            sys.stdout.write("\r")
            sys.stdout.flush()
            self._started = False


# ---------------------------------------------------------------------------
# Основной скан
# ---------------------------------------------------------------------------


def scan_folder(
    folder: str,
    log_path: str,
    use_presidio: bool = False,
    encoding: str = "utf-8",
    verbose: bool = False,
    threads: int = 1,
) -> Dict:
    """Сканирует папку, записывает в текстовый лог список файлов с секретами.

    Многопоточный режим (threads от 1 до 10): файлы распределяются между
    потоками, каждый поток показывает собственный прогресс. Лог пишется
    в один файл (запись из потоков защищена блокировкой).

    Формат лога: только пути к файлам, в которых найден секрет,
    по одному на строку. Секреты и статистика в лог не пишутся.

    Возвращает статистику сканирования.
    """
    threads = max(1, min(int(threads), 10))
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        print(f"[!] Папка не найдена: {folder}")
        sys.exit(1)

    log_path = _resolve_log_path(log_path)

    if use_presidio:
        _init_presidio()

    stats = {
        "scan_started": datetime.now(timezone.utc).isoformat(),
        "folder": folder,
        "log_file": os.path.abspath(log_path),
        "files_scanned": 0,
        "files_skipped": 0,
        "files_error": 0,
        "findings_count": 0,
        "by_category": {},
        "by_subcategory": {},
        "findings": [],
        "flagged_files": [],
    }

    seen_keys = set()  # дедупликация: file:subcategory:value
    flagged_files = set()  # файлы, в которых найден секрет

    # Блокировки: для статистики и для записи в лог
    stats_lock = threading.Lock()
    log_lock = threading.Lock()

    print(f"[i] Сканирование: {folder}")
    print(f"[i] Лог: {os.path.abspath(log_path)}")
    print(f"[i] Режим: {'Presidio + regex' if use_presidio else 'regex'}")
    print(f"[i] Потоков: {threads}")

    # Проход 1: сбор списка файлов, подлежащих обработке
    files_to_scan: List[str] = []
    total_subdirs = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        total_subdirs += len(dirs)
        for filename in files:
            p = os.path.join(root, filename)
            if _should_scan(p):
                files_to_scan.append(p)
            else:
                stats["files_skipped"] += 1

    total_to_scan = len(files_to_scan)
    print(f"[i] Файлов к обработке: {total_to_scan}, подпапок: {total_subdirs}")
    print()

    def _add_finding(f: Dict):
        key = f"{f['file_path']}:{f['subcategory']}:{f['value'][:100]}"
        with stats_lock:
            if key in seen_keys:
                return
            seen_keys.add(key)
            stats["findings"].append(f)
            stats["findings_count"] += 1
            cat = f["category"]
            sub = f["subcategory"]
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
            stats["by_subcategory"][sub] = stats["by_subcategory"].get(sub, 0) + 1
            is_new_file = f["file_path"] not in flagged_files
            if is_new_file:
                flagged_files.add(f["file_path"])

        # Запись пути в лог (первый раз для файла) — под блокировкой
        if is_new_file:
            with log_lock:
                log_fh.write(f["file_path"] + "\n")
                log_fh.flush()

    def _scan_text(file_path: str, text: str):
        """Regex + Presidio-сканирование одного текста, pipeline внутри потока."""
        all_patterns = _CRED_PATTERNS + _NETWORK_PASS_PATTERNS
        for pat_def in all_patterns:
            for match in pat_def["pattern"].finditer(text):
                groups = match.groups()
                if groups:
                    value = groups[0]
                else:
                    value = match.group(0)

                if not value or len(value) < 4:
                    continue

                if pat_def.get("entropy_check"):
                    ent = _shannon_entropy(value)
                    if ent < 3.0:
                        continue

                line_num = _line_number_at(text, match.start())
                ctx_start = max(0, match.start() - 80)
                ctx_end = min(len(text), match.end() + 80)
                ctx = text[ctx_start:ctx_end].replace("\n", " ").strip()

                _add_finding(
                    {
                        "category": "credentials",
                        "subcategory": pat_def["subcategory"],
                        "file_path": file_path,
                        "line_number": line_num,
                        "value": value[:500],
                        "confidence": pat_def["confidence"],
                        "context": ctx[:500],
                        "detection_method": "regex",
                    }
                )

        if use_presidio and _presidio_available:
            presidio_findings = _scan_presidio(text, file_path)
            for pf in presidio_findings:
                _add_finding(pf)

    def _process_file(file_path: str) -> None:
        """Обрабатывает один файл (statistics обновляются под локами)."""
        try:
            text = _read_text_file(file_path, encoding=encoding)
        except Exception as e:
            with stats_lock:
                stats["files_error"] += 1
            if verbose:
                print(f"  [!] Ошибка чтения {file_path}: {e}")
            return
        if text is None:
            with stats_lock:
                stats["files_skipped"] += 1
            return

        with stats_lock:
            stats["files_scanned"] += 1
        _scan_text(file_path, text)

    t0 = time.time()

    # Лог открываем один раз — все потоки пишут в один дескриптор
    log_fh = open(log_path, "w", encoding="utf-8")

    progress = _MultiProgress(rows=threads)

    # Распределение файлов по потокам (непрерывными кусками)
    per = math.ceil(total_to_scan / threads) if threads else 0
    chunks = [files_to_scan[i * per : (i + 1) * per] if per else [] for i in range(threads)]

    def _worker(wid: int, chunk: List[str]) -> None:
        progress.set_total(wid, len(chunk))
        for file_path in chunk:
            rel = os.path.relpath(file_path, folder) if verbose else ""
            _process_file(file_path)
            progress.tick(wid, rel)

    if threads <= 1:
        _worker(0, files_to_scan)
    else:
        workers = [
            threading.Thread(target=_worker, args=(wid, chunks[wid]), daemon=True)
            for wid in range(threads)
        ]
        for w in workers:
            w.start()
        for w in workers:
            w.join()

    stats["scan_finished"] = datetime.now(timezone.utc).isoformat()
    stats["elapsed_seconds"] = round(time.time() - t0, 1)
    stats["flagged_files"] = sorted(flagged_files)

    progress.clear()
    log_fh.close()

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Сканер папок на наличие паролей и SSH-ключей",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s D:\\Projects D:\\logs
  %(prog)s D:\\Projects D:\\logs\\scan.log
  %(prog)s D:\\Projects D:\\logs 4
  %(prog)s \\\\server\\share \\\\logs 2
  %(prog)s D:\\Projects D:\\logs --presidio
  %(prog)s D:\\Projects D:\\logs -v --encoding cp1251
        """,
    )
    parser.add_argument(
        "folder",
        help="Путь к сканируемой папке (локальной или сетевой)",
    )
    parser.add_argument(
        "log_file",
        help="Папка или файл для лога; в имя файла добавляется время запуска",
    )
    parser.add_argument(
        "threads",
        type=int,
        nargs="?",
        default=1,
        help="Количество потоков (максимум 10, по умолчанию 1)",
    )
    parser.add_argument(
        "--presidio",
        action="store_true",
        default=False,
        help="Использовать Presidio + spaCy для PII (требует presidio-analyzer, spacy)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Кодировка файлов (по умолчанию utf-8)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Подробный вывод",
    )
    args = parser.parse_args()

    threads = max(1, min(args.threads, 10))
    if threads != args.threads:
        print(f"[i] Количество потоков ограничено диапазоном [1..10], используется: {threads}")

    stats = scan_folder(
        folder=args.folder,
        log_path=args.log_file,
        use_presidio=args.presidio,
        encoding=args.encoding,
        verbose=args.verbose,
        threads=threads,
    )

    print()
    print("=" * 60)
    elapsed = stats.get("elapsed_seconds", 0)
    print(f"  Сканирование завершено за {elapsed:.1f} сек")
    print(f"  Папка:     {stats['folder']}")
    print(
        f"  Файлов:    {stats['files_scanned']} скан | {stats['files_skipped']} пропуск | {stats['files_error']} ошибки"
    )
    print(f"  Находок:   {stats['findings_count']}")
    if stats["by_subcategory"]:
        print()
        for sub, count in sorted(stats["by_subcategory"].items(), key=lambda x: -x[1]):
            print(f"    {sub}: {count}")
    print(f"  Лог:       {stats['log_file']}")
    print("=" * 60)

    if stats["findings_count"] > 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
