# Отчёт: День 53.1b — Scanner: фабрика коннекторов, `_text_scanner.py`, boto3

**Дата:** 04.10.2026
**Версия:** v3.13.29 → v3.13.30
**Задача:** BACKLOG-097, часть 2 (Scanner, ядро)
**Ветка:** `feature/day_53_1b_scanner_core`
**ТЗ:** `prompts/archive/day_53_1b_scanner_core.md`

---

## 1. Сводка по выполнению

| # | Файл | Действие | Задача | Статус |
|---|------|----------|--------|--------|
| 1 | `scanner/connectors/_text_scanner.py` | Создан | TASK-110 | ✅ |
| 2 | `scanner/connectors/factory.py` | Создан | TASK-111 | ✅ |
| 3 | `scanner/connectors/filesystem.py` | Рефакторинг на `_text_scanner` + регистрация в фабрике | TASK-112 | ✅ |
| 4 | `scanner/src/config_loader.py` | `S3ConnectorConfig` + `ConnectorConfig.s3` | TASK-113 | ✅ |
| 5 | `scanner/config/scanner_config.json` | Секция `connector.s3` | TASK-114 | ✅ |
| 6 | `scanner/requirements.txt` | `boto3>=1.34.0` | TASK-115 | ✅ |
| 7 | `scanner/src/managed_scanner.py` | `source_type` + фабрика + `_parent_of_path` | TASK-116 | ✅ |
| 8 | `tests/unit/test_factory_v31330.py` | Создан (7 тестов) | TASK-117 | ✅ |
| 9 | `tests/unit/test_text_scanner_extract_v31330.py` | Создан (13 тестов) | TASK-117 | ✅ |
| 10 | `tests/unit/test_catalog_entries_s3_v31330.py` | Создан (4 теста) | TASK-117 | ✅ |
| 11 | `tests/unit/test_ocr_bbox_v31317.py` | Обновлён (моки на новый seam) | регрессия | ✅ |

Миграции БД **не требуются** — день только про сканер.

---

## 2. Критерии приёмки

| # | Критерий | Проверка | Результат |
|---|----------|----------|-----------|
| 1 | `_text_scanner.py` создан, экспортирует 5 функций | `test_text_scanner_extract_v31330.py` | ✅ 13 passed |
| 2 | `factory.py` создан, `registered_types() == ["filesystem"]` | `test_factory_v31330.py` | ✅ `['filesystem']` |
| 3 | `FilesystemConnector` создаётся через `create_line_connector("filesystem", {})` | 117.1 + smoke | ✅ `isinstance` = True |
| 4 | `create_line_connector("s3")` → `ValueError` (53.2) | 117.1 | ✅ «S3 support arrives in day 53.2» |
| 5 | `FilesystemConnector` не изменил поведение | `pytest tests/unit/` | ✅ **402 passed** (было 378, +24), регрессий нет |
| 6 | `_parent_of_path("s3://bucket/a/b/file.txt") == "s3://bucket/a/b"` | 117.3 | ✅ |
| 7 | `config_loader` читает `connector.s3` из `scanner_config.json` | smoke `AppConfig.from_file` | ✅ `S3ConnectorConfig(...)`, секретов нет |
| 8 | `boto3` импортируется на сканере | `python -c "import boto3"` | ✅ `boto3 1.43.12` |
| 9 | Полный unit-набор зелёный | `pytest tests/unit/ -q` | ✅ 402 passed in 92.28s |
| 10 | Сканер по-прежнему не умеет S3 (ожидаемо) | `_init_line_pipeline()` при `source_type='s3'` + `FileSystemConnector.list_files('s3://...')` | ✅ вернул `False`, `_connector = None`, в логе точное сообщение из ТЗ; fallback даёт `[]` → задача `failed` с «No files found» |

---

## 3. Результаты тестов

### Целевые (новые файлы)

```
tests/unit/test_factory_v31330.py ...............................  7 passed
tests/unit/test_text_scanner_extract_v31330.py ................. 13 passed
tests/unit/test_catalog_entries_s3_v31330.py ...................  4 passed
                                                             = 24 passed in 0.41s
```

### Полный unit-набор

```
================ 402 passed, 1028 warnings in 92.28s ================
```

378 (до 53.1b) + 24 (новых) = 402. Ни одного падения, ни одной новой ошибки.

### Регрессия FS-коннектора (живой smoke)

Временный каталог: `app.env` (с `AKIAIOSFODNN7EXAMPLE`), `notes.txt`, `skipme.bin`
(бинарный мусор). Реальный `FilesystemConnector` + `CredentialsClassifier`:

```
файлов просканировано: 2      # skipme.bin отсечён как бинарный
находок: 1
 - aws_key | credentials | строка 1 | text_line
   контекст до: ''
```

FS-конвейер работает как до рефакторинга.

---

## 4. Отклонения от ТЗ

### 4.1 `test_decode_cp1251` из ТЗ противоречил коду из ТЗ — тест заменён

Код `decode_text_bytes` из ТЗ (и исходный `_read_text` с дня 40.2) содержит:

```python
for encoding in ("utf-8", "cp1251"):
    try:
        return content.decode(encoding, errors="ignore")
    except Exception:
        continue
```

`decode("utf-8", errors="ignore")` **никогда не бросает исключение** → цикл всегда
возвращается на первой итерации → `cp1251` **недостижим**. Проверено:

```
cp1251 bytes:   b'\xef\xf0\xe8\xe2\xe5\xf2'
utf-8 ignore:   ''            # ← фактический результат коннектора
cp1251 strict:  'привет'      # ← как было бы правильно
ИСХОДНЫЙ код даёт: ''         # поведение дня 40.2 совпадает
```

Тест из ТЗ утверждал `decode_text_bytes("привет".encode("cp1251")) == "привет"` —
то есть ожидал исправления, которого нет ни в ТЗ-реализации, ни в исходном коде.

**Решение:** поведение не менялось (приоритет ТЗ — «поведение не меняется»), тест
переписан на `test_decode_cp1251_bytes_follow_utf8_ignore` и документирует реальное
поведение с пояснением. Добавлен `test_decode_ascii`. Сам баг декодера заведён как
**BUG-136** в `STATE.md` — кандидат на отдельный день (вне 53.1b).

### 4.2 Моки в `test_ocr_bbox_v31317.py` переведены на функции-модули

Тест мокал приватные методы `connector._extract_document` и `connector._scan_text`,
которые TASK-112 удалил по прямому указанию ТЗ → `AttributeError` на
`patch.object`. Файл не был в списке ТЗ, но регрессию закрыть必须.

Моки заменены на `fs_mod.extract_document_text` и `fs_mod.shared_scan_text`
(имена, под которыми функции импортированы в `filesystem.py`). Проверяемая логика
BUG-077 (`fragment_type="image_region"`, `detector="ocr"`, `bounding_box=None`)
живёт в `scan_file` и **не менялась** — тест сохраняет исходный смысл.

### 4.3 Добавлен приватный helper `_read_bytes`

ТЗ-версия `scan_file` дублировала `with open(p, "rb") as f: content = f.read()` +
`except` в двух ветках (документы, изображения). Вынес в `_read_bytes(p, file_path)`
— тот же `logger.warning`, тот же `None` при ошибке. Поведение идентично.

### 4.4 sys.path в тестах — по конвенции репо

ТЗ добавлял только корень репо. Но `scanner/connectors/filesystem.py` импортирует
верхнеуровнево `from core.base import ...`, поэтому нужен и `scanner/` в `sys.path`
— ровно как в существующих `test_ocr_bbox_v31317.py` и `test_scanner_findings.py`.
Тесты приведены к этой конвенции.

### 4.5 `test_catalog_entries_s3_v31330.py` — raw docstring

В docstring из ТЗ был `C:\x\y` → `SyntaxError: (unicode error) 'unicodeescape'
codec can't decode bytes ... truncated \xXX escape`. Документация стала `r"""..."""`.

### 4.6 Комментарий-подсказка в `scanner_config.json`

В секцию `connector.s3` добавлено поле `_comment_s3` — пояснение, что это шаблон,
значения перекрываются payload'ом Manager, а секреты только в ENV. ТЗ его не
предусматривал; на парсинг не влияет (в `ConnectorConfig.from_dict` не читается).

---

## 5. Ключевые решения

### 5.1 Регистрация FS — в конце `filesystem.py`

```python
from scanner.connectors.factory import register_line_connector
register_line_connector("filesystem", lambda cfg: FilesystemConnector(cfg))
```

`factory.py` не импортирует `filesystem.py` — иначе получился бы циклический импорт
(`filesystem` → `_text_scanner` → `scanner.src.finding`, и `filesystem` → `factory`).
Побочный эффект: реестр пуст, пока не импортирован `scanner.connectors.filesystem`.
`managed_scanner.py` импортирует его на строке 52, до первого вызова фабрики, —
поэтому рабочий путь всегда корректен. Покрыто тестом 117.1.

### 5.2 Коннектор пересоздаётся на каждой задаче

```python
self._current_source_type = (task.get("source_type") or "filesystem").lower()
self._connector = None
```

ТЗ предлагал сравнивать `_connector_source_type`; выбранAlways-reset — безопаснее
(исключает переиспользование коннектора от другого типа). Создание коннектора
дёшево: это только чтение конфига.

### 5.3 Fallback на `filesystem` для старых задач

`task.get("source_type") or "filesystem"` — задачи, созданные до 53.1a, не имеют
поля в payload, и для них поведение не меняется.

---

## 6. Полный код изменённых/новых файлов

### 6.1 `scanner/connectors/_text_scanner.py` (новый)

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
```

### 6.2 `scanner/connectors/factory.py` (новый)

```python
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
```

### 6.3 `scanner/connectors/filesystem.py` (изменён — ключевые фрагменты)

Шапка:

```python
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
```

`_is_supported`:

```python
    def _is_supported(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower().lstrip('.')
        return is_supported_file(
            ext, file_path.name,
            text_extensions=self._text_extensions,
            cred_filenames=self._cred_filenames,
        )
```

`scan_file` + `_read_bytes` + `_read_text`:

```python
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
```

**Удалено** (≈150 строк): `_scan_text`, `_file_pass_prefilter`, `_extract_document`,
`_DOCUMENT_EXTENSIONS`, `_IMAGE_EXTENSIONS`, локальные копии `CRED_FILENAMES` /
`DEFAULT_TEXT_EXTENSIONS` (теперь импортируются из `_text_scanner`).

**Осталось** в `filesystem.py`: `FileSystemConnector` (для Orchestrator, не тронут),
`_discover_files` (os.walk), `_within_size`, `scan_path` (ThreadPool), `scan_file`
(диспетчер по расширению), `_read_text`, `_read_bytes`.

### 6.4 `scanner/src/config_loader.py` (добавлено)

```python
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
    def from_dict(cls, data: Dict[str, Any]) -> 'S3ConnectorConfig':
        return cls(
            endpoint=data.get("endpoint", "host.docker.internal:9000"),
            bucket=data.get("bucket", ""),
            prefix=data.get("prefix", ""),
            secure=bool(data.get("secure", False)),
            use_path_style=bool(data.get("use_path_style", True)),
            region=data.get("region", "us-east-1"),
        )
```

В `ConnectorConfig`:

```python
    max_parallel_files: int = 1  # <-- ДОБАВЛЕНО (день 42, параллельный скан)
    # День 53.1b (BACKLOG-097): опциональная секция S3/MinIO (без секретов).
    # None, если в конфиге секции connector.s3 нет.
    s3: Optional['S3ConnectorConfig'] = None
```

и в `from_dict`:

```python
            max_parallel_files=data.get("max_parallel_files", 1),  # <-- ДОБАВЛЕНО
            s3=S3ConnectorConfig.from_dict(data["s3"]) if data.get("s3") else None,
```

### 6.5 `scanner/config/scanner_config.json` (добавлено)

```json
        "_comment_s3": "День 53.1b (BACKLOG-097): дефолтный шаблон S3/MinIO-коннектора. Реальные endpoint/bucket/prefix приходят в payload задачи от Manager и перекрывают эти значения. Секреты (access_key/secret_key) НЕ хранятся здесь — только ENV S3_ACCESS_KEY / S3_SECRET_KEY на хосте сканера.",
        "s3": {
            "endpoint": "host.docker.internal:9000",
            "bucket": "",
            "prefix": "",
            "secure": false,
            "use_path_style": true,
            "region": "us-east-1"
        }
```

### 6.6 `scanner/requirements.txt` (добавлено)

```
# S3/MinIO (день 53.1b, BACKLOG-097): коннектор сканера к S3.
# В 53.1b только в зависимостях — S3LineConnector появится в 53.2
boto3>=1.34.0
```

### 6.7 `scanner/src/managed_scanner.py` (изменён — ключевые фрагменты)

Импорт:

```python
from scanner.connectors.filesystem import FileSystemConnector, FilesystemConnector
# День 53.1b (BACKLOG-097): коннектор выбирается по source_type из payload задачи
from scanner.connectors.factory import create_line_connector
```

`__init__`:

```python
        # Построчный конвейер (день 40.2)
        self._connector: Optional[FilesystemConnector] = None
        # День 53.1b (BACKLOG-097): тип источника текущей задачи
        # (filesystem | s3 | minio) — из payload Manager.
        self._current_source_type: str = "filesystem"
        self._enc = None
```

`_parent_of_path`:

```python
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
```

в `_collect_catalog_entries`:

```python
            folder_path = self._parent_of_path(file_path)
```

`_init_line_pipeline` (конец):

```python
        connector_cfg["ocr_enabled"] = ocr_enabled
        # День 53.1b (BACKLOG-097): коннектор выбирается по source_type задачи,
        # а не жёстко. Для s3/minio в 53.1b фабрика бросает ValueError —
        # S3LineConnector появится в 53.2.
        try:
            self._connector = create_line_connector(self._current_source_type, connector_cfg)
            logger.info(
                "[LineScan] Connector created: source_type=%s, type=%s",
                self._current_source_type,
                type(self._connector).__name__,
            )
        except ValueError as exc:
            logger.error("[LineScan] %s", exc)
            self._connector = None
            return False
```

`_execute_task` (начало):

```python
    def _execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task["id"]
        resource_path = task["path"]
        scan_config = task.get("scan_config", {})

        # День 53.1b (BACKLOG-097): тип источника из payload Manager.
        # Fallback на filesystem — если задача создана до 53.1a.
        self._current_source_type = (task.get("source_type") or "filesystem").lower()
        # Коннектор пересоздаём на каждой задаче: дешёво (только конфиг) и
        # исключает переиспользование коннектора от другого source_type.
        self._connector = None

        logger.info(
            f"[Scanner] Executing task {task_id} on {resource_path} "
            f"(source_type={self._current_source_type})"
        )
```

`_execute_task_linewise` (лог):

```python
        logger.info(
            "[Scanner] Построчное сканирование %s (task %d, source_type=%s)",
            resource_path, task_id, self._current_source_type,
        )
```

---

## 7. Ручная проверка

### 7.1 Регресс FS-сканирования

```powershell
$env:PYTHONUTF8 = '1'
python run_scanner.py scanner/config/scanner_config.json
```

В Manager создаём FS-задачу на `E:\projects\dcap-system\test_files`.
**Ожидание:** задача выполняется как раньше, `source_type=filesystem`, те же находки.

В логах сканера должно быть:

```
INFO  [LineScan] Connector created: source_type=filesystem, type=FilesystemConnector
INFO  [LineScan] Построчный конвейер готов: N классификаторов, keys=...
INFO  [Scanner] Построчное сканирование <путь> (task <id>, source_type=filesystem)
```

### 7.2 S3-задача — ожидаемо `failed`

```powershell
$body = '{"username":"admin","password":"admin123"}'
$token = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
    -ContentType "application/json" -Body $body).access_token
$headers = @{ Authorization = "Bearer $token" }

# создаём S3-ресурс и задачу (или используем существующий ресурс)
$res = Invoke-RestMethod -Method POST "http://127.0.0.1:8000/api/resources?path=s3%3A%2F%2Ftest-bucket%2Fdata&type=s3" -Headers $headers
Invoke-RestMethod -Method POST "http://127.0.0.1:8000/api/resources/$($res.id)/scan" -Headers $headers
```

**Ожидание** в логах сканера:

```
ERROR [LineScan] Line connector for source_type='s3' not registered. Available: ['filesystem']. S3 support arrives in day 53.2.
```

Задача уходит в fallback-ветку (Orchestrator + `FileSystemConnector.list_files`),
который для `s3://bucket/data` возвращает `[]` (проверено), и завершается `failed`:

```
failed_files: [{"path": "s3://bucket/data", "error": "No files found", "error_type": "connection"}]
stats: {"files_scanned": 0, "files_failed": 1, "total_findings": 0}
```

**Это ожидаемо для 53.1b** — понятный отказ вместо падения с
`FileNotFoundError: 's3:/bucket'`. Реальное сканирование S3 появится в 53.2.

### 7.3 Конфиг

```powershell
python -c "import sys; sys.path.insert(0,'.'); from scanner.src.config_loader import AppConfig; print(AppConfig.from_file('scanner/config/scanner_config.json').connector.s3)"
```

**Ожидание:** `S3ConnectorConfig(endpoint='host.docker.internal:9000', bucket='', prefix='', secure=False, use_path_style=True, region='us-east-1')`

---

## 8. Что НЕ сделано (по границам 53.1b)

- `S3LineConnector` — 53.2.
- ENV-секреты `S3_ACCESS_KEY` / `S3_SECRET_KEY` — 53.2.
- Streaming-чтение объектов S3 — 53.2.
- OCR/документы из S3 — 53.2.
- `scanner/connectors/s3_connector.py` (247 строк, `ISourceConnector`) не тронут
  и не используется — его место займёт новый `S3LineConnector`.
- WebUI-форма S3-ресурса — 53.3.
- E2E на MinIO — 53.3.
- Логика `_init_line_pipeline` для классификаторов не менялась — только замена
  коннектора на фабрику.
- Миграции БД не требовались.
- `boto3` в `requirements.txt`, но нигде не импортируется (код 53.2).

---

## 9. Команда для коммита

```powershell
git add scanner/connectors/_text_scanner.py `
        scanner/connectors/factory.py `
        scanner/connectors/filesystem.py `
        scanner/src/config_loader.py `
        scanner/config/scanner_config.json `
        scanner/requirements.txt `
        scanner/src/managed_scanner.py `
        tests/unit/test_factory_v31330.py `
        tests/unit/test_text_scanner_extract_v31330.py `
        tests/unit/test_catalog_entries_s3_v31330.py `
        tests/unit/test_ocr_bbox_v31317.py `
        STATE.md CHANGELOG.md ROADMAP.md `
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
- 24 unit-теста; tests/unit: 402 passed (было 378), регрессий нет

BACKLOG-097 (часть 2: Scanner, ядро)
docs: обновлены STATE.md (v3.13.30), CHANGELOG.md, ROADMAP.md"
```

---

**Автор отчёта:** кодер
**Дата:** 04.10.2026
**Статус ТЗ:** выполнено (10 критериев приёмки из 10)
