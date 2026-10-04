ТЗ: День 53.1b — Scanner: фабрика коннекторов, `_text_scanner.py`, boto3 (BACKLOG-097, часть 2)
Файл: prompts/tz/day_53_1b_scanner_core.md
Дата: 04.10.2026
Версия: v3.13.29 → v3.13.30
Статус: ✏️ Готово к разработке
Оценка: ~2–2.5 ч
Приоритет: 🔴 критично (BACKLOG-097 — часть 2: подготовка ядра сканера к S3)
Родительская задача: BACKLOG-097 «S3-коннектор сканера: интеграция в ядро + пайплайн находок»

🎯 ЦЕЛЬ

1. Вынести общий построчный пайплайн (`_scan_text` / `_file_pass_prefilter` / чтение с декодированием / диспетчер по расширению) в `scanner/connectors/_text_scanner.py`.
2. Реализовать фабрику коннекторов `scanner/connectors/factory.py` (реестр `SourceType → фабрика`).
3. Отрефакторить `FilesystemConnector` на использование `_text_scanner` — **поведение не меняется**.
4. Добавить в `config_loader.py` секцию `ConnectorConfig.s3` (endpoint/bucket/prefix/secure/use_path_style/region, **без секретов**).
5. Добавить `boto3` в `scanner/requirements.txt`.
6. В `managed_scanner.py`: читать `task["source_type"]` и выбирать коннектор через фабрику; в `_collect_catalog_entries` — корректная обработка `s3://bucket/key`.
7. Покрыть unit-тестами.

Что НЕ входит в 53.1b:
- `S3LineConnector` (построчный сканер S3) — 53.2.
- ENV-секреты в `s3_connector.py` (`S3_ACCESS_KEY`/`S3_SECRET_KEY`) — 53.2.
- Streaming-чтение объектов S3 — 53.2.
- OCR/документы из S3 — 53.2.
- WebUI-форма S3-ресурса — 53.3.
- E2E на MinIO — 53.3.

📌 ПРОБЛЕМА

После 53.1a Manager уже отдаёт сканеру `source_type` и `scan_config.connector.s3`, но **сканер его игнорирует**:
- `managed_scanner.py:1126` и `:729` жёстко создают `FilesystemConnector`;
- `FilesystemConnector._scan_text` / `_read_text` / `_extract_document` — построчный пайплайн, пригодный для любого источника, но живёт **внутри** FS-коннектора;
- `S3Connector` (247 строк, `scanner/connectors/s3_connector.py`) реализует `ISourceConnector`, но **не реализует** `scan_path` — построчный пайплайн не запустится;
- фабрики коннекторов нет; в `config_loader.py` нет секции `s3`; `boto3` отсутствует в `scanner/requirements.txt`;
- `_collect_catalog_entries` использует `Path(file_path).parent` — для `s3://bucket/key` это даст `s3:/bucket` (сломано).

**Следствие:** без выноса пайплайна в общий модуль и без фабрики подключение S3 в 53.2 потребует дублировать ~150 строк логики (контекст, префильтр, документы, OCR), а сканер не сможет выбрать коннектор по `source_type`.

📌 ПРЕДУСЛОВИЯ

- ✅ 53.1a закрыта (v3.13.29): `ScanTask.source_type`, `source_type` в payload `/tasks/pending`.
- ✅ Manager healthy, сканер регистрируется, FS-сканирование работает.
- ✅ `pytest tests/unit/` — 378 passed.
- ✅ MinIO (нативный, `E:\Dev\MinIO`) поднят, но в 53.1b **не используется** — S3 реально не сканируется.

📁 ФАЙЛЫ (создаются / изменяются)

Создаются

| Файл | Назначение |
|------|------------|
| `scanner/connectors/_text_scanner.py` | Общий построчный пайплайн (функции) |
| `scanner/connectors/factory.py` | Реестр коннекторов, `create_line_connector()` |
| `tests/unit/test_factory_v31330.py` | Unit-тесты фабрики |
| `tests/unit/test_text_scanner_extract_v31330.py` | Регрессия: `FilesystemConnector` через `_text_scanner` |
| `tests/unit/test_catalog_entries_s3_v31330.py` | `_collect_catalog_entries` для `s3://` |
| `prompts/reports/day_53_1b_report.md` | Отчёт о выполнении |

Изменяются

| Файл | Что меняется |
|------|--------------|
| `scanner/connectors/filesystem.py` | Рефакторинг на `_text_scanner` (поведение не меняется) |
| `scanner/src/config_loader.py` | `S3ConnectorConfig`, `ConnectorConfig.s3` |
| `scanner/config/scanner_config.json` | Секция `connector.s3` (без секретов) |
| `scanner/requirements.txt` | `boto3` |
| `scanner/src/managed_scanner.py` | `_current_source_type`, `_init_line_pipeline` через фабрику, `_collect_catalog_entries` для S3 |
| `STATE.md` | Версия + следующий шаг |
| `CHANGELOG.md` | Секция `[3.13.30]` |
| `ROADMAP.md` | Отметка 53.1b выполненной |

🔧 ДЕТАЛЬНОЕ ТЗ

TASK-110 — `_text_scanner.py`

Файл: `scanner/connectors/_text_scanner.py` (создать)

Назначение: **функции**, вынесенные из `FilesystemConnector`, чтобы `S3LineConnector` (53.2) переиспользовал их без копипасты. Классов нет — только функции, импортируемые напрямую.

Полный код:

```python
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
from typing import Any, List, Optional

from scanner.src.finding import Finding

logger = logging.getLogger("dcap-scanner")


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
    """Декодировать байты в текст (utf-8 → cp1251, fallback utf-8 ignore).

    Возвращает None, если это явно бинарный мусор (\x00 в первых 4 КБ).
    """
    if content[:4096] and b"\x00" in content[:4096]:
        return None
    for encoding in ("utf-8", "cp1251"):
        try:
            return content.decode(encoding, errors="ignore")
        except Exception:
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

    return findings


def extract_document_text(
    content: bytes,
    ext: str,
    filename: str,
    ocr_enabled: bool = False,
) -> Optional[str]:
    """Извлечь текст из PDF/Office/изображения (через DocumentExtractor).

    Принимает БАЙТЫ (а не путь) — чтобы FS и S3 могли переиспользовать.
    """
    try:
        from utils.document_extractor import DocumentExtractor
        import tempfile as _tf
        from pathlib import Path as _P

        extractor = DocumentExtractor(
            temp_dir=_P(_tf.gettempdir()),
            ocr_enabled=ocr_enabled,
        )
        result, error = extractor.extract_text(content, ext, filename)
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
    "extract_document_text",
]
TASK-111 — factory.py

Файл: scanner/connectors/factory.py (создать)

Назначение: единая точка создания построчных коннекторов по source_type из payload задачи.

Полный код:

python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Фабрика построчных коннекторов (день 53.1b, BACKLOG-097).

Регистрирует коннекторы, реализующие интерфейс FilesystemConnector
(scan_path / scan_file). В 53.1b зарегистрирован только filesystem;
S3LineConnector добавится в 53.2.
"""
import logging
from typing import Any, Callable, Dict

logger = logging.getLogger("dcap-scanner")

_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Any]] = {}


def register_line_connector(source_type: str, factory: Callable[[Dict[str, Any]], Any]) -> None:
    """Зарегистрировать фабрику для source_type ('filesystem', 's3', 'minio')."""
    _REGISTRY[(source_type or "").lower()] = factory
    logger.debug("[Factory] Registered line connector: %s", source_type)


def create_line_connector(source_type: str, config: Dict[str, Any]) -> Any:
    """Создать построчный коннектор по source_type.

    В 53.1b зарегистрирован только 'filesystem'. Для 's3'/'minio' бросаем
    ValueError — S3LineConnector появится в 53.2; главное, чтобы сканер
    упал с понятным сообщением, а не пытался открыть 's3://bucket' как папку.
    """
    st = (source_type or "filesystem").lower()
    if st not in _REGISTRY:
        raise ValueError(
            f"Line connector for source_type={st!r} not registered. "
            f"Available: {sorted(_REGISTRY)}. "
            "S3 support arrives in day 53.2."
        )
    return _REGISTRY[st](config or {})


def registered_types() -> list:
    """Список зарегистрированных source_type (для диагностики/тестов)."""
    return sorted(_REGISTRY)


__all__ = ["register_line_connector", "create_line_connector", "registered_types"]
И регистрация FS-коннектора — в конце scanner/connectors/filesystem.py:

python
# Регистрация в фабрике (день 53.1b)
from scanner.connectors.factory import register_line_connector
register_line_connector("filesystem", lambda cfg: FilesystemConnector(cfg))
TASK-112 — Рефакторинг filesystem.py на _text_scanner

Файл: scanner/connectors/filesystem.py

Цель: поведение не меняется, но _scan_text / _file_pass_prefilter / _read_text / _extract_document больше не свои — делегируют в _text_scanner.

Что заменить:

Удалить из FilesystemConnector методы _scan_text, _file_pass_prefilter, _extract_document. Заменить вызовы на импортированные функции.

Метод _read_text оставить (он читает конкретный путь), но внутри использовать decode_text_bytes:

python
from scanner.connectors._text_scanner import decode_text_bytes

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
        return decode_text_bytes(b"".join(chunks))
    except Exception as exc:
        logger.warning("[FS] Не удалось прочитать %s: %s", file_path, exc)
        return None
scan_file — заменить внутренние вызовы:

python
from scanner.connectors._text_scanner import (
    DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS,
    extract_document_text, scan_text as shared_scan_text,
)

def scan_file(self, file_path: str, classifiers: List[Any]) -> List[Finding]:
    p = Path(file_path)
    if not p.exists():
        return []

    ext = p.suffix.lower().lstrip(".")

    # Текст — построчно
    if ext in self._text_extensions or p.name.lower() in self._cred_filenames:
        text = self._read_text(str(p))
        if text is None:
            return []
        return shared_scan_text(text, classifiers, str(p), self._context_lines, self._max_text_chars)

    # Документы — извлечь текст и сканировать построчно
    if ext in DOCUMENT_EXTENSIONS:
        try:
            with open(p, "rb") as f:
                content = f.read()
        except Exception as exc:
            logger.warning("[FS] Не удалось открыть %s: %s", file_path, exc)
            return []
        text = extract_document_text(content, ext, p.name, ocr_enabled=self.config.get("ocr_enabled", False))
        if not text:
            return []
        return shared_scan_text(text, classifiers, str(p), self._context_lines, self._max_text_chars)

    # Изображения — OCR
    if ext in IMAGE_EXTENSIONS:
        try:
            with open(p, "rb") as f:
                content = f.read()
        except Exception as exc:
            logger.warning("[FS] Не удалось открыть %s: %s", file_path, exc)
            return []
        text = extract_document_text(content, ext, p.name, ocr_enabled=self.config.get("ocr_enabled", False))
        if not text:
            return []
        findings = shared_scan_text(text, classifiers, str(p), self._context_lines, self._max_text_chars)
        for f in findings:
            f.fragment_type = "image_region"
            f.detector = "ocr"
            f.bounding_box = None
        return findings

    return []
_is_supported — заменить на импорт is_supported_file:

python
from scanner.connectors._text_scanner import (
    CRED_FILENAMES, DEFAULT_TEXT_EXTENSIONS,
    DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, is_supported_file,
)

def _is_supported(self, file_path: Path) -> bool:
    ext = file_path.suffix.lower().lstrip(".")
    return is_supported_file(
        ext, file_path.name,
        text_extensions=self._text_extensions,
        cred_filenames=self._cred_filenames,
    )
Что остаётся в filesystem.py:

_discover_files (os.walk), _within_size, scan_path (ThreadPool) — FS-специфично.

_read_text — читает файл.

scan_file — диспетчер по расширению (использует _text_scanner).

Проверка регрессии: поведение FilesystemConnector не должно измениться — тот же scan_path, те же находки, тот же контекст.

TASK-113 — config_loader.py: секция s3

Файл: scanner/src/config_loader.py

Добавить dataclass S3ConnectorConfig и опциональное поле s3 в ConnectorConfig.

Полный код нового dataclass (вставить перед ConnectorConfig):

python
@dataclass
class S3ConnectorConfig:
    """Конфигурация S3/MinIO-коннектора (день 53.1b, BACKLOG-097).

    Секреты (access_key / secret_key) НЕ хранятся здесь — только ENV
    на хосте сканера: S3_ACCESS_KEY / S3_SECRET_KEY (политика TASK-018).
    """
    endpoint: str = "host.docker.internal:9000"
    bucket: str = ""
    prefix: str = ""
    secure: bool = False
    use_path_style: bool = True
    region: str = "us-east-1"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "S3ConnectorConfig":
        return cls(
            endpoint=data.get("endpoint", "host.docker.internal:9000"),
            bucket=data.get("bucket", ""),
            prefix=data.get("prefix", ""),
            secure=bool(data.get("secure", False)),
            use_path_style=bool(data.get("use_path_style", True)),
            region=data.get("region", "us-east-1"),
        )
В ConnectorConfig добавить поле:

python
s3: Optional["S3ConnectorConfig"] = None
И в ConnectorConfig.from_dict — читать:

python
s3=S3ConnectorConfig.from_dict(data["s3"]) if data.get("s3") else None,
Также добавить в ConnectorConfig поле ocr_enabled: bool = False (для удобства, чтобы managed_scanner не читал его из classifier каждый раз — опционально; можно не добавлять в 53.1b, оставить как есть).

_validate_required не трогать — секция connector.s3 опциональна, обязательных ключей добавлять не нужно. Секции s3 может не быть в scanner_config.json вообще (тогда ConnectorConfig.s3 = None).

TASK-114 — scanner_config.json: секция connector.s3

Файл: scanner/config/scanner_config.json

Внутри существующего блока "connector" добавить поле "s3" без секретов (endpoint/bucket/prefix читаются из payload задачи, но дефолты — здесь):

json
"connector": {
    "skip_dirs": [ ... существующие ... ],
    "follow_symlinks": false,
    "scan_hidden": true,
    "buffer_size": 1048576,
    "max_text_chars": 200000,
    "context_lines": 2,
    "max_parallel_files": 8,
    "text_extensions": [ ... существующие ... ],

    "s3": {
        "endpoint": "host.docker.internal:9000",
        "bucket": "",
        "prefix": "",
        "secure": false,
        "use_path_style": true,
        "region": "us-east-1"
    }
}
Секретов нет — это дефолтный шаблон; реальные endpoint/bucket/prefix приходят от Manager в payload задачи; access_key/secret_key — только ENV.

TASK-115 — scanner/requirements.txt: boto3

Файл: scanner/requirements.txt

Добавить одну строку:

text
boto3>=1.34
Версия — из audit-agent-s3/requirements.txt (там уже есть boto3). Конкретную версию закрепить как boto3==1.34.* или по образцу S3-агента (совпадать не обязательно).

TASK-116 — managed_scanner.py: source_type + фабрика + S3-путь

Файл: scanner/src/managed_scanner.py

116.1. Импорты (в начале файла, после существующих)
python
from scanner.connectors.factory import create_line_connector
116.2. Поле _current_source_type
В __init__ класса ManagedScanner добавить:

python
self._current_source_type: str = "filesystem"
(рядом с self._connector: Optional[FilesystemConnector] = None)

116.3. _init_line_pipeline — через фабрику
Заменить блок создания коннектора. Было:

python
self._connector = FilesystemConnector(connector_cfg)
Стало:

python
# День 53.1b (BACKLOG-097): коннектор выбирается по source_type задачи,
# а не жёстко. Для s3/minio в 53.1b фабрика бросает ValueError —
# S3LineConnector появится в 53.2.
try:
    self._connector = create_line_connector(self._current_source_type, connector_cfg)
    logger.info("[LineScan] Connector created: source_type=%s, type=%s",
                self._current_source_type, type(self._connector).__name__)
except ValueError as exc:
    logger.error("[LineScan] %s", exc)
    self._connector = None
    return False
Важно: _init_line_pipeline возвращает False, если коннектор не удалось создать. Тогда _execute_task перейдёт в fallback-ветку (Orchestrator) — и она тоже не умеет S3, поэтому задача упадёт с понятной ошибкой. Это ожидаемо для 53.1b.

116.4. _execute_task — установить _current_source_type
В начале _execute_task:

python
def _execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
    task_id = task["id"]
    resource_path = task["path"]
    scan_config = task.get("scan_config", {})
    # День 53.1b (BACKLOG-097): тип источника из payload Manager.
    # Fallback на filesystem — если задача создана до 53.1a.
    self._current_source_type = (task.get("source_type") or "filesystem").lower()
    # ...
И: при смене source_type между задачами сбрасывать self._connector, чтобы _init_line_pipeline пересоздал коннектор под новый тип:

python
    # Если тип источника сменился — сбрасываем коннектор
    if getattr(self, "_connector_source_type", None) != self._current_source_type:
        self._connector = None
        self._connector_source_type = self._current_source_type
Проще — установить self._connector = None всегда при старте новой задачи (пересоздание коннектора дешёвое: там только конфиг). Так избежим багов с переиспользованием.

Выбираем: всегда self._connector = None в начале _execute_task. Это безопаснее и проще.

116.5. _collect_catalog_entries — корректный s3://
Заменить фрагмент:

python
folder_path = str(Path(file_path).parent)
На helper:

python
def _parent_of_path(self, file_path: str) -> str:
    """Родительская папка файла (поддерживает FS-пути и s3://bucket/key).

    Path('s3://bucket/key').parent даст 's3:/bucket' — сломано. Для s3://
    используем urlparse + posixpath.dirname.
    """
    if not file_path:
        return ""
    if file_path.startswith(("s3://", "minio://")):
        from urllib.parse import urlparse
        import posixpath
        parsed = urlparse(file_path)
        parent_dir = posixpath.dirname(parsed.path.lstrip("/"))
        bucket = parsed.netloc
        if parent_dir:
            return f"{parsed.scheme}://{bucket}/{parent_dir}"
        return f"{parsed.scheme}://{bucket}"
    return str(Path(file_path).parent)
И в _collect_catalog_entries:

python
folder_path = self._parent_of_path(file_path)
Также — при передаче в _collect_catalog_entries из _execute_task_linewise параметр resource_path может быть s3://bucket/prefix; в catalog_entries.path это тоже уйдёт как есть, корректно.

116.6. Метрики: self._current_source_type в логах
Добавить в logger.info("[Scanner] Построчное сканирование %s (task %d, source_type=%s)", resource_path, task_id, self._current_source_type) — для диагностики.

TASK-117 — Unit-тесты

117.1. tests/unit/test_factory_v31330.py
python
"""Unit-тесты фабрики коннекторов (день 53.1b).

Покрытие:
- registered_types() содержит filesystem;
- create_line_connector('filesystem', {}) возвращает FilesystemConnector;
- create_line_connector('s3') → ValueError (не зарегистрирован в 53.1b);
- create_line_connector('minio') → ValueError;
- create_line_connector(None) → filesystem (дефолт);
- create_line_connector('FILESYSTEM') → filesystem (нормализация регистра).
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scanner.connectors.factory import (  # noqa: E402
    create_line_connector,
    registered_types,
)
from scanner.connectors.filesystem import FilesystemConnector  # noqa: E402


def test_registered_types_contains_filesystem():
    assert "filesystem" in registered_types()


def test_create_filesystem_returns_instance():
    c = create_line_connector("filesystem", {})
    assert isinstance(c, FilesystemConnector)


def test_create_filesystem_normalizes_case():
    c1 = create_line_connector("FILESYSTEM", {})
    c2 = create_line_connector("FiLeSyStEm", {})
    assert isinstance(c1, FilesystemConnector)
    assert isinstance(c2, FilesystemConnector)


def test_create_filesystem_default_when_none():
    c = create_line_connector(None, {})
    assert isinstance(c, FilesystemConnector)


def test_create_s3_raises_value_error():
    with pytest.raises(ValueError) as exc:
        create_line_connector("s3", {})
    assert "s3" in str(exc.value)
    assert "53.2" in str(exc.value)


def test_create_minio_raises_value_error():
    with pytest.raises(ValueError) as exc:
        create_line_connector("minio", {})
    assert "minio" in str(exc.value)


def test_create_unknown_raises_value_error():
    with pytest.raises(ValueError):
        create_line_connector("ftp", {})
117.2. tests/unit/test_text_scanner_extract_v31330.py
python
"""Unit-тесты _text_scanner (день 53.1b): функции + регрессия.

Покрытие:
- is_supported_file: txt, .docx, .png, id_rsa, .env, unknown;
- decode_text_bytes: utf-8, cp1251, BOM, \x00 (None);
- file_pass_prefilter: классификатор без file_prefilter → True;
- scan_text: пустой текст → [], без классификаторов → [];
- scan_text + dummy scan_line классификатор → находит, ставит line_text/context/fragment_path.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scanner.connectors._text_scanner import (  # noqa: E402
    decode_text_bytes,
    file_pass_prefilter,
    is_supported_file,
    scan_text,
)


class _DummyFinding:
    def __init__(self, line_number, line_text="", category="test"):
        self.line_number = line_number
        self.line_text = line_text
        self.category = category
        self.finding_type = "pii"
        self.match_text = "dummy"
        self.start_pos = 0
        self.end_pos = 5
        self.context_before = ""
        self.context_after = ""
        self.fragment_path = ""
        self.confidence = 1.0
        self.severity = "medium"
        self.detector = "test"
        self.fragment_type = "text_line"
        self.bounding_box = None
        self.byte_offset = None
        self.byte_length = None
        self.hex_preview = None


class _DummyClassifier:
    classifier_name = "dummy"

    def scan_line(self, line, line_num):
        if "SECRET" in line:
            return [_DummyFinding(line_num, line_text=line)]
        return []


def test_is_supported_txt():
    assert is_supported_file("txt", "a.txt")


def test_is_supported_docx():
    assert is_supported_file("docx", "a.docx")


def test_is_supported_png():
    assert is_supported_file("png", "a.png")


def test_is_supported_cred_filename():
    assert is_supported_file("", "id_rsa")
    assert is_supported_file("", ".env")


def test_is_supported_unknown():
    assert not is_supported_file("bin", "a.bin")


def test_decode_utf8():
    assert decode_text_bytes("привет".encode("utf-8")) == "привет"


def test_decode_cp1251():
    assert decode_text_bytes("привет".encode("cp1251")) == "привет"


def test_decode_binary_returns_none():
    assert decode_text_bytes(b"\x00\x01\x02\x03" * 2048) is None


def test_file_pass_prefilter_no_classifiers():
    assert file_pass_prefilter("text", []) is False


def test_file_pass_prefilter_classifier_without_prefilter():
    class _NoPref:
        pass
    assert file_pass_prefilter("text", [_NoPref()]) is True


def test_scan_text_empty():
    assert scan_text("", [_DummyClassifier()], "/tmp/x.txt") == []


def test_scan_text_finds_line():
    text = "line1\nline2 SECRET\nline3"
    result = scan_text(text, [_DummyClassifier()], "/tmp/x.txt", context_lines=1)
    assert len(result) == 1
    f = result[0]
    assert f.line_number == 2
    assert f.fragment_path == "/tmp/x.txt"
    assert "line1" in f.context_before
    assert "line3" in f.context_after
117.3. tests/unit/test_catalog_entries_s3_v31330.py
python
"""Unit-тесты _collect_catalog_entries для s3:// (день 53.1b).

Покрытие:
- FS-путь: C:/x/y/file.txt → C:\x\y (как Path.parent);
- S3-путь: s3://bucket/a/b/file.txt → s3://bucket/a/b;
- S3-путь верхнего уровня: s3://bucket/file.txt → s3://bucket;
- пустой путь → "".
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scanner.src.managed_scanner import ManagedScanner  # noqa: E402


def _scanner_stub():
    """ManagedScanner без инициализации классификаторов."""
    s = ManagedScanner.__new__(ManagedScanner)
    return s


def test_parent_fs_path():
    s = _scanner_stub()
    parent = s._parent_of_path(r"C:\x\y\file.txt")
    assert parent.endswith("y")


def test_parent_s3_nested():
    s = _scanner_stub()
    assert s._parent_of_path("s3://bucket/a/b/file.txt") == "s3://bucket/a/b"


def test_parent_s3_top():
    s = _scanner_stub()
    assert s._parent_of_path("s3://bucket/file.txt") == "s3://bucket"


def test_parent_empty():
    s = _scanner_stub()
    assert s._parent_of_path("") == ""
🧪 КРИТЕРИИ ПРИЁМКИ

#	Критерий	Проверка
1	_text_scanner.py создан, экспортирует 5 функций	unit-тесты 117.2
2	factory.py создан, registered_types() == ["filesystem"]	unit-тесты 117.1
3	FilesystemConnector создаётся через create_line_connector("filesystem", {})	117.1
4	create_line_connector("s3") → ValueError (53.2)	117.1
5	FilesystemConnector после рефакторинга не изменил поведение (регрессия)	pytest tests/unit/ — 378 + N passed, регрессий нет
6	_parent_of_path("s3://bucket/a/b/file.txt") == "s3://bucket/a/b"	117.3
7	config_loader читает connector.s3 из scanner_config.json	smoke: AppConfig.from_file("scanner/config/scanner_config.json").connector.s3 is not None
8	boto3 импортируется на сканере (python -c "import boto3")	ручная
9	Полный unit-набор зелёный, регрессий нет	pytest tests/unit/ -q
10	Сканер по-прежнему не умеет S3 — это ожидаемо (граница 53.1b)	ручная: задача source_type=s3 → failed с сообщением «S3 support arrives in day 53.2»
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ

Миграции не требуются (только код сканера).

Unit-тесты:

powershell
pytest tests/unit/test_factory_v31330.py -v
pytest tests/unit/test_text_scanner_extract_v31330.py -v
pytest tests/unit/test_catalog_entries_s3_v31330.py -v
pytest tests/unit/ -q
Ожидание: 3 новых файла — passed; полный unit-набор — 378 + N passed, регрессий нет.

Smoke на FS-регрессе (сканер на хосте):

powershell
python run_scanner.py scanner/config/scanner_config.json
# В Manager создаём FS-задачу — она должна выполниться как раньше
Ожидание: сканер подхватывает FS-задачу, source_type=filesystem, находит те же находки, что до рефакторинга.

Smoke на S3 (ожидаемо падает):

powershell
# Убеждаемся, что FS-сканирование не сломано, а S3 уходит в failed
$body = '{"username":"admin","password":"admin123"}'
$token = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
    -ContentType "application/json" -Body $body).access_token
$headers = @{ Authorization = "Bearer $token" }

# Создаём задачу на S3-ресурсе (id=135 из 53.1a)
Invoke-RestMethod -Method POST "http://127.0.0.1:8000/api/resources/135/scan" -Headers $headers
Ожидание: сканер подхватит задачу, увидит source_type=s3, вызовет create_line_connector("s3"), получит ValueError, залогирует «S3 support arrives in day 53.2», пометит задачу failed.

📝 СВОДКА ПРАВОК

#	Файл	Действие	Задача
1	scanner/connectors/_text_scanner.py	Создан	TASK-110
2	scanner/connectors/factory.py	Создан	TASK-111
3	scanner/connectors/filesystem.py	Рефакторинг на _text_scanner	TASK-112
4	scanner/src/config_loader.py	S3ConnectorConfig, ConnectorConfig.s3	TASK-113
5	scanner/config/scanner_config.json	Секция connector.s3	TASK-114
6	scanner/requirements.txt	boto3	TASK-115
7	scanner/src/managed_scanner.py	source_type + фабрика + _parent_of_path	TASK-116
8	tests/unit/test_factory_v31330.py	Создан	TASK-117
9	tests/unit/test_text_scanner_extract_v31330.py	Создан	TASK-117
10	tests/unit/test_catalog_entries_s3_v31330.py	Создан	TASK-117
⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ

Сканер по-прежнему не умеет S3. Это граница 53.1b: подготовка ядра, но S3LineConnector — 53.2.

Существующий S3Connector (scanner/connectors/s3_connector.py) не изменяется и не используется — он реализует ISourceConnector, а не построчный интерфейс. Его место займёт новый S3LineConnector в 53.2.

boto3 добавляется, но не импортируется в 53.1b — до 53.2 остаётся только в requirements.txt. Поставка без pip install — ок, boto3 в requirements, но код его не трогает.

connector.s3 в JSON — шаблон, значения перекрываются payload'ом Manager.

📋 ОТКРЫТЫЕ ВОПРОСЫ

S3Connector (ISourceConnector) — оставляем как есть, не трогаем. ✅ (согласовано ранее).

_text_scanner — функции или класс? — функции (проще, без наследования). ✅

_current_source_type в ManagedScanner — сохраняем между задачами, но коннектор пересоздаём на каждой задаче (дешево, безопаснее). ✅

_parent_of_path — отдельный helper (не переписываем Path(...).parent глобально), чтобы поведение FS-путей не изменилось. ✅

⚠️ ЧТО НЕ ДЕЛАЕМ

Не трогаем scanner/connectors/s3_connector.py — он остаётся как есть.

Не пишем S3LineConnector — это 53.2.

Не трогаем ENV-секреты S3 (S3_ACCESS_KEY/S3_SECRET_KEY) — это 53.2 (вместе с S3LineConnector).

Не трогаем Manager — в 53.1b только сканер.

Не трогаем _init_line_pipeline логику классификаторов — только замену коннектора на фабрику.

💾 КОМАНДА ДЛЯ КОММИТА

bash
git checkout -b feature/day_53_1b_scanner_core

git add scanner/connectors/_text_scanner.py \
        scanner/connectors/factory.py \
        scanner/connectors/filesystem.py \
        scanner/src/config_loader.py \
        scanner/config/scanner_config.json \
        scanner/requirements.txt \
        scanner/src/managed_scanner.py \
        tests/unit/test_factory_v31330.py \
        tests/unit/test_text_scanner_extract_v31330.py \
        tests/unit/test_catalog_entries_s3_v31330.py \
        STATE.md CHANGELOG.md ROADMAP.md \
        prompts/reports/day_53_1b_report.md

git commit -m "feat: День 53.1b — Scanner: фабрика коннекторов + _text_scanner + boto3 (v3.13.30)

- scanner/connectors/_text_scanner.py — общий построчный пайплайн
  (scan_text / file_pass_prefilter / decode_text_bytes / is_supported_file /
   extract_document_text)
- scanner/connectors/factory.py — реестр SourceType → фабрика,
  create_line_connector(); зарегистрирован только filesystem
- FilesystemConnector — рефакторинг на _text_scanner (поведение не меняется)
- config_loader.py — S3ConnectorConfig + ConnectorConfig.s3 (без секретов)
- scanner_config.json — секция connector.s3 (дефолтный шаблон)
- requirements.txt += boto3
- managed_scanner.py — _current_source_type из payload задачи, выбор
  коннектора через фабрику, _parent_of_path для s3://bucket/key

BACKLOG-097 (часть 2: Scanner, ядро)
docs: обновлён STATE.md (v3.13.30)"
📊 ОБНОВЛЕНИЕ ПЛАНА

День	Задача	Статус
53.1a	Manager: source_type + S3-ресурсы	✅ v3.13.29
53.1b	Scanner: фабрика, _text_scanner.py, boto3	🔄 В РАБОТЕ
53.2	Scanner: S3LineConnector + ENV-секреты + streaming + OCR	📋 следующий
53.3	Тесты E2E (MinIO) + WebUI-форма S3	📋
52.1	Linux-агент (дотест)	📋
52.2	Блок 6.5 (сбор прав Windows)	📋
📌 ПОСЛЕ ВЫПОЛНЕНИЯ

Обновить STATE.md: версия v3.13.30, следующий шаг «53.2: Scanner — S3LineConnector (streaming, ENV-секреты, OCR/документы)».

Обновить CHANGELOG.md — секция [3.13.30].

Обновить ROADMAP.md — 53.1b ✅.

Переместить ТЗ в prompts/archive/day_53_1b_scanner_core.md.

Отчёт — prompts/reports/day_53_1b_report.md:

сводка по выполнению,

полный код изменённых/новых файлов,

результаты pytest,

ручная проверка FS-регресса + ожидаемый failed для S3.

Автор ТЗ: архитектор
Дата: 04.10.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.30 — общий _text_scanner, фабрика коннекторов, boto3 в зависимостях; сканер выбирает коннектор по source_type (пока только filesystem; S3 → понятный failed).