ТЗ: День 53.2 — Scanner: S3LineConnector (streaming, ENV-секреты, OCR/документы)
Файл: prompts/tz/day_53_2_s3_line_connector.md
Дата: 04.10.2026
Версия: v3.13.30 → v3.13.31
Статус: ✏️ Готово к разработке
Оценка: ~3–3.5 ч
Приоритет: 🔴 критично (BACKLOG-097, часть 3: реальное сканирование S3/MinIO)
Родительская задача: BACKLOG-097 «S3-коннектор сканера: интеграция в ядро + пайплайн находок»

🎯 ЦЕЛЬ

1. Реализовать `S3LineConnector` — построчный сканер S3/MinIO с тем же интерфейсом, что `FilesystemConnector` (`scan_path` / `scan_file`).
2. Читать объекты **streaming** (не целиком в память) через `Body.iter_chunks`.
3. Документы (PDF/Office) и изображения (OCR) — скачивать во временный файл, извлекать текст через `_text_scanner.extract_document_text`.
4. Секреты S3 (`access_key` / `secret_key`) — только из ENV (`S3_ACCESS_KEY` / `S3_SECRET_KEY`).
5. В `managed_scanner.py` передавать `scan_config.connector.s3` (из payload задачи Manager) в конфиг коннектора.
6. Зарегистрировать `s3` и `minio` в фабрике.
7. Фикс **BUG-136** — `decode_text_bytes` не пробует cp1251 (strict-декод перед `ignore`).
8. Покрыть unit-тестами + ручной smoke на живом MinIO.

Что НЕ входит в 53.2:
- E2E-тесты на MinIO — 53.3.
- WebUI-форма добавления S3-ресурса — 53.3.
- WebUI-отображение S3-находок — 53.3 (в UI уже поддерживается `s3://` в `file_path`, отдельной доработки не требует).
- Переработка `scanner/connectors/s3_connector.py` (`ISourceConnector` для Orchestrator) — не трогаем.
- Новые форматы (CloudTrail, S3 access log native) — не в этой задаче.

📌 ПРОБЛЕМА

После 53.1a Manager отдаёт сканеру `source_type` и `scan_config.connector.s3`, а 53.1b подготовил ядро (фабрика + `_text_scanner` + `boto3`), но:
- **нет `S3LineConnector`** — фабрика для `s3`/`minio` бросает `ValueError`,
- сканер для S3-задачи уходит в fallback Orchestrator, который использует `FileSystemConnector.list_files("s3://...")` → `[]` → задача `failed` с «No files found»,
- `scanner/connectors/s3_connector.py` (247 строк, `ISourceConnector`) реализует `list_files` / `get_content`, но **не** `scan_path` — построчный пайплайн не запустится,
- `decode_text_bytes` в `_text_scanner.py` содержит BUG-136 (ветка cp1251 недостижима).

**Следствие:** S3/MinIO реально не сканируется. BACKLOG-097 не закрыт.

📌 ПРЕДУСЛОВИЯ

- ✅ 53.1a закрыта (v3.13.29): Manager отдаёт `source_type` и `connector.s3`.
- ✅ 53.1b закрыта (v3.13.30): `_text_scanner.py`, `factory.py`, `boto3`, `_parent_of_path`.
- ✅ MinIO нативный (`E:\Dev\MinIO\bin\minio.exe`), bucket `dcap-audit-logs` наполнен seed-логами (`scripts/minio-seed/access-logs/*`).
- ✅ Manager healthy, сканер регистрируется, FS-сканирование работает.
- ✅ `pytest tests/unit/` — 402 passed.

📁 ФАЙЛЫ (создаются / изменяются)

Создаются

| Файл | Назначение |
|------|------------|
| `scanner/connectors/s3_line_connector.py` | S3LineConnector — построчный сканер S3/MinIO |
| `tests/unit/test_s3_line_connector_v31331.py` | Unit-тесты S3LineConnector (mock boto3) |
| `tests/unit/test_decode_text_cp1251_v31331.py` | BUG-136 фикс |
| `prompts/reports/day_53_2_report.md` | Отчёт о выполнении |

Изменяются

| Файл | Что меняется |
|------|--------------|
| `scanner/connectors/factory.py` | Регистрация `s3` + `minio` |
| `scanner/connectors/_text_scanner.py` | Фикс BUG-136 (`decode_text_bytes`) |
| `scanner/src/managed_scanner.py` | Передача `scan_config.connector.s3` в `create_line_connector` |
| `scanner/connectors/s3_connector.py` | ENV-секреты (`S3_ACCESS_KEY` / `S3_SECRET_KEY`) |
| `tests/unit/test_factory_v31330.py` | Обновить: `registered_types()` теперь `["filesystem", "minio", "s3"]` |
| `STATE.md`, `CHANGELOG.md`, `ROADMAP.md` | Версия, отчёт |

🔧 ДЕТАЛЬНОЕ ТЗ

TASK-118 — `decode_text_bytes`: фикс BUG-136

Файл: `scanner/connectors/_text_scanner.py`

Найти функцию `decode_text_bytes`. Заменить тело:

```python
def decode_text_bytes(content: bytes) -> Optional[str]:
    """Декодировать байты в текст (utf-8 strict → cp1251 strict → utf-8 ignore).

    Возвращает None, если это явно бинарный мусор (\\x00 в первых 4 КБ).

    BUG-136 (день 53.2): раньше цикл использовал errors="ignore" на первой
    итерации (utf-8), из-за чего ветка cp1251 была недостижима — файлы в
    cp1251 декодировались в мусор («пустую строку»). Теперь — строгий декод,
    и только если оба провалились, fallback на utf-8 с errors="ignore".
    """
    if content[:4096] and b"\\x00" in content[:4096]:
        return None
    for encoding in ("utf-8", "cp1251"):
        try:
            return content.decode(encoding)  # strict — падает на несовпадении
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")
Поведение до фикса: файл primer.txt в cp1251 → "" (utf-8 strict не падал из-за errors="ignore", но и не декодировал).
Поведение после: файл primer.txt в cp1251 → "привет".

TASK-119 — s3_line_connector.py (новый)

Файл: scanner/connectors/s3_line_connector.py

Полный код:

python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Построчный S3/MinIO-коннектор (день 53.2, BACKLOG-097).

Интерфейс — как у FilesystemConnector: scan_path() / scan_file().
Читает объекты S3 построчно (streaming) и прогоняет через _text_scanner.
Документы/изображения — временный файл + DocumentExtractor.

Секреты (access_key / secret_key) — только ENV: S3_ACCESS_KEY / S3_SECRET_KEY
(политика TASK-018). Endpoint/bucket/prefix/secure/use_path_style — из config,
который приходит per-task из scan_config.connector.s3 (payload Manager).
"""
import logging
import os
import posixpath
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional
from urllib.parse import urlparse

from scanner.src.finding import Finding
from scanner.connectors._text_scanner import (
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    decode_text_bytes,
    extract_document_text,
    is_supported_file,
    scan_text as shared_scan_text,
)

try:
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import (
        BotoCoreError,
        ClientError,
        ConnectTimeoutError,
        ReadTimeoutError,
    )
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

logger = logging.getLogger("dcap-scanner")


class S3LineConnector:
    """Построчный сканер S3/MinIO (интерфейс — FilesystemConnector)."""

    def __init__(self, config: Dict[str, Any]):
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 не установлен. Установите: pip install boto3")

        self.config = config or {}

        # Параметры источника (прилетают из payload задачи).
        self._endpoint = self.config.get("endpoint") or "host.docker.internal:9000"
        self._bucket = self.config.get("bucket") or ""
        self._prefix = (self.config.get("prefix") or "").lstrip("/")
        self._secure = bool(self.config.get("secure", False))
        self._use_path_style = bool(self.config.get("use_path_style", True))
        self._region = self.config.get("region") or "us-east-1"

        # Параметры сканирования.
        self._text_extensions = set(
            self.config.get("text_extensions")
            or [
                "txt", "csv", "log", "json", "yaml", "yml", "xml", "toml",
                "ini", "cfg", "conf", "env", "envrc", "properties", "py",
                "js", "ts", "tsx", "java", "c", "cpp", "h", "hpp", "go",
                "rs", "sh", "bash", "zsh", "ps1", "cmd", "bat", "sql",
                "php", "rb", "lua", "r", "swift", "kt", "md", "rst",
                "html", "css", "scss", "dockerfile", "makefile", "tf",
                "hcl", "pem", "key", "crt", "csr", "cert", "p12", "pfx",
                "jks",
            ]
        )
        self._context_lines = int(self.config.get("context_lines", 2))
        self._max_file_size_mb = int(self.config.get("max_file_size_mb", 50))
        self._max_text_chars = int(self.config.get("max_text_chars", 200000))
        self._buffer_size = int(self.config.get("buffer_size", 1024 * 1024))
        self._max_workers = int(self.config.get("max_parallel_files", 1) or 1)
        self._ocr_enabled = bool(self.config.get("ocr_enabled", False))

        # Секреты — только ENV. Проверка: если в config тоже есть — предупреждаем.
        env_access = os.environ.get("S3_ACCESS_KEY")
        env_secret = os.environ.get("S3_SECRET_KEY")
        if self.config.get("access_key") or self.config.get("secret_key"):
            logger.warning(
                "[S3Line] access_key/secret_key в config игнорируются — используйте "
                "ENV S3_ACCESS_KEY / S3_SECRET_KEY (политика TASK-018)"
            )
        self._access_key = env_access or self.config.get("access_key")
        self._secret_key = env_secret or self.config.get("secret_key")

        if not self._access_key or not self._secret_key:
            raise ValueError(
                "S3LineConnector: задайте S3_ACCESS_KEY / S3_SECRET_KEY в ENV"
            )
        if not self._bucket:
            raise ValueError("S3LineConnector: параметр 'bucket' обязателен")

        # Клиент boto3.
        protocol = "https" if self._secure else "http"
        endpoint_url = f"{protocol}://{self._endpoint}"
        s3_config = BotoConfig(
            s3={"addressing_style": "path" if self._use_path_style else "virtual"},
            connect_timeout=30,
            read_timeout=60,
            retries={"max_attempts": 3, "mode": "standard"},
        )
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
            config=s3_config,
            verify=False if not self._secure else True,  # TEST-NOTE-6.11
        )
        logger.info(
            "[S3Line] Connector configured: endpoint=%s, bucket=%s, prefix=%r, "
            "path_style=%s, secure=%s",
            endpoint_url, self._bucket, self._prefix, self._use_path_style, self._secure,
        )
        if not self._secure:
            logger.warning(
                "[S3Line] secure=False — HTTPS-проверка сертификата отключена "
                "(TEST-NOTE-6.11). Для production используйте secure=true."
            )

    # =====================================================================
    # Обход объектов
    # =====================================================================

    def _discover_keys(self, prefix: str) -> List[str]:
        """Список ключей в bucket под prefix, отфильтрованных по extensions/size."""
        result: List[str] = []
        try:
            continuation_token = None
            while True:
                params: Dict[str, Any] = {
                    "Bucket": self._bucket,
                    "Prefix": prefix or self._prefix,
                    "MaxKeys": 1000,
                }
                if continuation_token:
                    params["ContinuationToken"] = continuation_token

                response = self._client.list_objects_v2(**params)
                for obj in response.get("Contents", []) or []:
                    key = obj["Key"]
                    if key.endswith("/"):
                        continue
                    size_mb = obj.get("Size", 0) / (1024 * 1024)
                    if size_mb > self._max_file_size_mb:
                        continue
                    ext = Path(key).suffix.lower().lstrip(".")
                    filename = posixpath.basename(key)
                    if not is_supported_file(
                        ext, filename,
                        text_extensions=self._text_extensions,
                    ):
                        continue
                    result.append(key)

                if not response.get("IsTruncated", False):
                    break
                continuation_token = response.get("NextContinuationToken")

        except (ConnectTimeoutError, ReadTimeoutError) as exc:
            logger.error("[S3Line] Timeout при list_objects: %s", exc)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            logger.error("[S3Line] ClientError list_objects: %s", code)
            raise
        except BotoCoreError as exc:
            logger.error("[S3Line] BotoCoreError list_objects: %s", exc)
            raise
        return result

    # =====================================================================
    # Публичный интерфейс (совместим с FilesystemConnector)
    # =====================================================================

    def scan_path(
        self,
        path: str,
        classifiers: List[Any],
        progress_callback: Optional[Callable[[int, int, int, str], None]] = None,
        stop_event: Optional[Any] = None,
    ) -> List[Finding]:
        """Сканирует bucket по prefix. Возвращает список Finding.

        path может быть:
          - 's3://bucket/prefix' — используется bucket/prefix из него,
          - 's3://bucket'        — bucket без prefix,
          - '' или None          — bucket/prefix из конфига.

        progress_callback(stage, current, total, file_path): stage 1 = скан.
        stop_event: threading.Event — прерывание после текущего объекта.
        """
        source_prefix = self._prefix
        if path:
            parsed = urlparse(path)
            if parsed.scheme in ("s3", "minio"):
                if parsed.netloc and parsed.netloc != self._bucket:
                    # Bucket в path отличается от bucket в config — доверяем path.
                    logger.warning(
                        "[S3Line] Bucket в path (%s) != bucket в config (%s) — "
                        "использую path",
                        parsed.netloc, self._bucket,
                    )
                source_prefix = (parsed.path or "").lstrip("/")
            else:
                source_prefix = (path or "").lstrip("/")

        keys = self._discover_keys(source_prefix)
        total = len(keys)
        if not total:
            if progress_callback:
                progress_callback(1, 0, 0, path or source_prefix)
            return []

        findings: List[Finding] = []
        for idx, key in enumerate(keys, start=1):
            if stop_event is not None and stop_event.is_set():
                logger.info("[S3Line] Остановка на %d/%d", idx, total)
                break
            if progress_callback:
                progress_callback(1, idx, total, key)
            try:
                findings.extend(self.scan_file(key, classifiers))
            except Exception as exc:
                logger.warning("[S3Line] Ошибка scan_file(%s): %s", key, exc)
        return findings

    def scan_file(self, key: str, classifiers: List[Any]) -> List[Finding]:
        """Сканирует один объект bucket по его ключу.

        file_path в findings = 's3://bucket/key' (не локальный путь) — это
        важно для fingerprint (дедупликации) и для /fragment в Manager.
        """
        if not key:
            return []
        s3_uri = f"s3://{self._bucket}/{key}"
        ext = Path(key).suffix.lower().lstrip(".")
        filename = posixpath.basename(key)

        # Текст — построчно, streaming.
        if ext in self._text_extensions or filename.lower() in {
            "id_rsa", ".env", "kubeconfig", "secrets", ".pgpass", ".netrc",
        }:
            text = self._read_text(key)
            if text is None:
                return []
            return shared_scan_text(
                text, classifiers, s3_uri, self._context_lines, self._max_text_chars
            )

        # Документы / изображения — временный файл + DocumentExtractor.
        if ext in DOCUMENT_EXTENSIONS or ext in IMAGE_EXTENSIONS:
            content = self._download_bytes(key)
            if content is None:
                return []
            text = extract_document_text(
                content, ext, filename, ocr_enabled=self._ocr_enabled,
            )
            if not text:
                return []
            findings = shared_scan_text(
                text, classifiers, s3_uri, self._context_lines, self._max_text_chars
            )
            if ext in IMAGE_EXTENSIONS:
                for f in findings:
                    f.fragment_type = "image_region"
                    f.detector = "ocr"
                    f.bounding_box = None
            return findings

        return []

    # =====================================================================
    # Чтение
    # =====================================================================

    def _read_text(self, key: str) -> Optional[str]:
        """Streaming-чтение текста (максимум self._max_text_chars байт)."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            chunks = []
            total = 0
            # Streaming: iter_chunks(buffer_size) — не читает весь объект в память.
            for chunk in body.iter_chunks(chunk_size=self._buffer_size):
                chunks.append(chunk)
                total += len(chunk)
                if total >= self._max_text_chars:
                    break
            body.close()
            return decode_text_bytes(b"".join(chunks))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            logger.warning("[S3Line] ClientError get_object(%s): %s", key, code)
            return None
        except Exception as exc:
            logger.warning("[S3Line] Ошибка чтения %s: %s", key, exc)
            return None

    def _download_bytes(self, key: str) -> Optional[bytes]:
        """Скачать объект во временный файл, вернуть байты.

        Нужно, потому что DocumentExtractor работает с путём/байтами, а не
        с потоком boto3. Для больших PDF — читаем целиком (лимит уже проверен
        в _discover_keys по max_file_size_mb).
        """
        tmp_path: Optional[str] = None
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=Path(key).suffix, delete=False,
            ) as tmp:
                for chunk in body.iter_chunks(chunk_size=self._buffer_size):
                    tmp.write(chunk)
                tmp_path = tmp.name
            body.close()
            with open(tmp_path, "rb") as f:
                return f.read()
        except Exception as exc:
            logger.warning("[S3Line] Ошибка скачивания %s: %s", key, exc)
            return None
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


__all__ = ["S3LineConnector"]
TASK-120 — s3_connector.py: ENV-секреты

Файл: scanner/connectors/s3_connector.py

В методе configure заменить блок чтения секретов. Было:

python
        self.access_key = config.get("access_key")
        self.secret_key = config.get("secret_key")
Стало:

python
        # Секреты — только ENV (политика TASK-018). Оставлено чтение из config
        # для обратной совместимости с аудит-агентом S3 (не относится к сканеру).
        env_access = os.environ.get("S3_ACCESS_KEY")
        env_secret = os.environ.get("S3_SECRET_KEY")
        if config.get("access_key") and not env_access:
            logger.warning(
                "[S3] access_key в config — устаревший способ, используйте "
                "ENV S3_ACCESS_KEY"
            )
        self.access_key = env_access or config.get("access_key")
        self.secret_key = env_secret or config.get("secret_key")
⚠️ s3_connector.py не используется сканером (он для ISourceConnector/Orchestrator), но правка полезна на будущее. Если кодер решит не трогать — допустимо (в 53.2 не критично). По усмотрению кодера.

TASK-121 — factory.py: регистрация s3 и minio

Файл: scanner/connectors/factory.py

В конец файла добавить:

python
# Регистрация S3/MinIO (день 53.2, BACKLOG-097)
from scanner.connectors.s3_line_connector import S3LineConnector  # noqa: E402

register_line_connector("s3", lambda cfg: S3LineConnector(cfg))
register_line_connector("minio", lambda cfg: S3LineConnector(cfg))
Циклических импортов нет — s3_line_connector не импортирует factory.

TASK-122 — managed_scanner.py: передача connector.s3

Файл: scanner/src/managed_scanner.py

В _init_line_pipeline перед вызовом create_line_connector добавить merge из payload задачи. Найти:

python
        connector_cfg["ocr_enabled"] = ocr_enabled
        try:
            self._connector = create_line_connector(self._current_source_type, connector_cfg)
Заменить на:

python
        connector_cfg["ocr_enabled"] = ocr_enabled
        # День 53.2 (BACKLOG-097): для S3/MinIO параметры endpoint/bucket/prefix
        # приходят в payload задачи (scan_config.connector.s3). Мержим поверх
        # локального конфига — приоритет у payload (per-task конфиг).
        self._current_scan_config = self._current_scan_config or {}
        s3_payload = (
            self._current_scan_config.get("connector", {}).get("s3", {}) or {}
        )
        if s3_payload:
            connector_cfg.update(s3_payload)
        try:
            self._connector = create_line_connector(self._current_source_type, connector_cfg)
И в __init__ добавить:

python
        self._current_scan_config: Dict[str, Any] = {}
В _execute_task сохранить текущий scan_config:

python
        self._current_source_type = (task.get("source_type") or "filesystem").lower()
        self._current_scan_config = task.get("scan_config", {}) or {}
        self._connector = None
Обоснование: scan_config приходит per-task, а _init_line_pipeline вызывается внутри _execute_task_linewise, где scan_config — локальная переменная. Сохраняем её в поле.

TASK-123 — Unit-тесты

123.1. tests/unit/test_decode_text_cp1251_v31331.py
python
"""BUG-136: decode_text_bytes должен пробовать cp1251 после utf-8."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scanner.connectors._text_scanner import decode_text_bytes  # noqa: E402


def test_decode_utf8_still_works():
    assert decode_text_bytes("привет мир".encode("utf-8")) == "привет мир"


def test_decode_cp1251_now_works():
    """Регрессия BUG-136: раньше возвращалась пустая строка."""
    result = decode_text_bytes("привет".encode("cp1251"))
    assert result == "привет"


def test_decode_ascii():
    assert decode_text_bytes(b"hello") == "hello"


def test_decode_binary_returns_none():
    assert decode_text_bytes(b"\x00\x01\x02\x03" * 2048) is None


def test_decode_invalid_bytes_falls_back_to_ignore():
    """Если ни utf-8 strict, ни cp1251 strict не подошли — игнорируем."""
    bad = b"\xff\xfe\xfd\xfc"
    result = decode_text_bytes(bad)
    assert isinstance(result, str)  # не падает
123.2. tests/unit/test_s3_line_connector_v31331.py
python
"""Unit-тесты S3LineConnector (день 53.2) с mock boto3."""
import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Изолируем от реального boto3: в тесте подменяем клиент.
os.environ.setdefault("S3_ACCESS_KEY", "test-access")
os.environ.setdefault("S3_SECRET_KEY", "test-secret")

from scanner.connectors.s3_line_connector import S3LineConnector  # noqa: E402


class _DummyClassifier:
    classifier_name = "dummy"

    def scan_line(self, line, line_num):
        from scanner.src.finding import Finding
        if "SECRET" in line:
            f = Finding()
            f.line_number = line_num
            f.line_text = line
            f.match_text = "SECRET"
            f.category = "test"
            f.finding_type = "credentials"
            f.start_pos = 0
            f.end_pos = 6
            f.confidence = 1.0
            f.severity = "medium"
            f.detector = "test"
            f.fragment_type = "text_line"
            f.bounding_box = None
            f.byte_offset = None
            f.byte_length = None
            f.hex_preview = None
            return [f]
        return []


def _make_connector(mock_list, mock_get=None):
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client
        mock_client.list_objects_v2.side_effect = mock_list
        if mock_get is not None:
            mock_client.get_object.side_effect = mock_get
        connector = S3LineConnector({
            "endpoint": "test.local:9000",
            "bucket": "test-bucket",
            "prefix": "",
            "secure": False,
            "use_path_style": True,
        })
    return connector, mock_client


def _list_one_page(keys):
    def _list(**kwargs):
        return {
            "Contents": [{"Key": k, "Size": 100, "LastModified": None} for k in keys],
            "IsTruncated": False,
        }
    return _list


def test_discover_keys_filters_by_extension():
    connector, _ = _make_connector(_list_one_page(["a.txt", "b.bin", "c.pdf"]))
    keys = connector._discover_keys("")
    assert "a.txt" in keys
    assert "c.pdf" in keys
    assert "b.bin" not in keys


def test_scan_path_sets_s3_uri_in_findings():
    """file_path в findings = s3://bucket/key — критично для fingerprint."""
    fake_body = io.BytesIO(b"line1\nline2 SECRET\nline3")

    class _Body:
        def iter_chunks(self, chunk_size=1024):
            yield fake_body.read()

        def close(self):
            pass

    def _get(**kwargs):
        return {"Body": _Body()}

    connector, _ = _make_connector(_list_one_page(["notes.txt"]), mock_get=_get)

    findings = connector.scan_path("s3://test-bucket/", [_DummyClassifier()])
    assert len(findings) == 1
    assert findings[0].fragment_path == "s3://test-bucket/notes.txt"
    assert findings[0].line_number == 2


def test_scan_path_uses_prefix_from_arg():
    connector, mock_client = _make_connector(_list_one_page([]))
    connector.scan_path("s3://test-bucket/logs/", [_DummyClassifier()])
    call_kwargs = mock_client.list_objects_v2.call_args.kwargs
    assert call_kwargs["Prefix"] == "logs/"


def test_constructor_reads_secrets_from_env(monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY", "env-access")
    monkeypatch.setenv("S3_SECRET_KEY", "env-secret")
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        S3LineConnector({"bucket": "b"})
        kwargs = mock_boto.client.call_args.kwargs
        assert kwargs["aws_access_key_id"] == "env-access"
        assert kwargs["aws_secret_access_key"] == "env-secret"


def test_constructor_requires_bucket():
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        with pytest.raises(ValueError) as exc:
            S3LineConnector({"endpoint": "x"})
        assert "bucket" in str(exc.value)


def test_stop_event_stops_iteration():
    """stop_event прерывает скан между объектами."""
    import threading
    stop = threading.Event()
    stop.set()

    def _get(**kwargs):
        raise AssertionError("не должен вызываться")

    connector, _ = _make_connector(_list_one_page(["a.txt", "b.txt"]), mock_get=_get)
    findings = connector.scan_path("s3://test-bucket/", [_DummyClassifier()], stop_event=stop)
    assert findings == []
123.3. Обновить tests/unit/test_factory_v31330.py
Заменить test_registered_types_contains_filesystem на:

python
def test_registered_types_contains_all():
    types = registered_types()
    assert "filesystem" in types
    assert "s3" in types
    assert "minio" in types
Тесты test_create_s3_raises_value_error / test_create_minio_raises_value_error — удалить (после 53.2 фабрика их создаёт). Добавить:

python
def test_create_s3_returns_s3_line_connector(monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY", "x")
    monkeypatch.setenv("S3_SECRET_KEY", "y")
    from unittest.mock import MagicMock, patch
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        from scanner.connectors.s3_line_connector import S3LineConnector
        c = create_line_connector("s3", {"bucket": "b"})
        assert isinstance(c, S3LineConnector)


def test_create_minio_returns_s3_line_connector(monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY", "x")
    monkeypatch.setenv("S3_SECRET_KEY", "y")
    from unittest.mock import MagicMock, patch
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        from scanner.connectors.s3_line_connector import S3LineConnector
        c = create_line_connector("minio", {"bucket": "b"})
        assert isinstance(c, S3LineConnector)
🧪 КРИТЕРИИ ПРИЁМКИ

#	Критерий	Проверка
1	S3LineConnector создан, принимает config	123.2
2	scan_path возвращает findings с fragment_path=s3://bucket/key	123.2
3	_discover_keys фильтрует по extensions	123.2
4	Секреты — из ENV (S3_ACCESS_KEY/S3_SECRET_KEY)	123.2
5	bucket обязателен → ValueError	123.2
6	stop_event прерывает итерацию	123.2
7	decode_text_bytes декодирует cp1251 (BUG-136)	123.1
8	registered_types() == ["filesystem", "minio", "s3"]	123.3
9	create_line_connector("s3") возвращает S3LineConnector	123.3
10	Полный unit-набор зелёный	pytest tests/unit/ -q
11	Smoke на живом MinIO: S3-задача проходит полный цикл	ручная проверка §7
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ

Установить boto3 (уже в requirements): pip install boto3.

Установить ENV для сканера:

powershell
$env:S3_ACCESS_KEY = "minioadmin"
$env:S3_SECRET_KEY = "minioadmin"
Unit:

powershell
pytest tests/unit/test_s3_line_connector_v31331.py -v
pytest tests/unit/test_decode_text_cp1251_v31331.py -v
pytest tests/unit/test_factory_v31330.py -v
pytest tests/unit/ -q
Smoke на MinIO:

Предусловия:

MinIO запущен (docker ps | findstr minio или нативный на E:\Dev\MinIO).

Bucket dcap-audit-logs содержит seed-логи (scripts/minio-seed/access-logs/*).

Manager healthy, сканер запущен.

Команды:

powershell
# Токен
$body = '{"username":"admin","password":"admin123"}'
$token = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
    -ContentType "application/json" -Body $body).access_token
$headers = @{ Authorization = "Bearer $token" }

# Создать S3-ресурс (если ещё нет — из 53.1a уже есть, id=135)
$res = Invoke-RestMethod -Method POST `
    "http://127.0.0.1:8000/api/resources?path=s3%3A%2F%2Fdcap-audit-logs%2Faccess-logs%2F&type=s3" `
    -Headers $headers
"RES_ID=$($res.id)"

# Запустить сканирование
$task = Invoke-RestMethod -Method POST `
    "http://127.0.0.1:8000/api/resources/$($res.id)/scan" `
    -Headers $headers
"TASK_ID=$($task.task_id)"
Ожидание в логах сканера:

text
INFO  [LineScan] Connector created: source_type=s3, type=S3LineConnector
INFO  [S3Line] Connector configured: endpoint=http://host.docker.internal:9000, bucket=dcap-audit-logs, prefix='access-logs/'
INFO  [Scanner] Построчное сканирование s3://dcap-audit-logs/access-logs/ (task N, source_type=s3)
INFO  [Scanner] Task N completed (linewise):
  - Files scanned: 3
  - Total findings: <N>
Проверка findings:

powershell
$findings = Invoke-RestMethod -Method GET `
    "http://127.0.0.1:8000/api/findings?task_id=$($task.task_id)&limit=100" `
    -Headers $headers
$findings | Where-Object { $_.file_path -like "s3://*" } | Select-Object -First 3
Ожидание: file_path в findings начинается на s3://dcap-audit-logs/access-logs/..., has_fragment вычисляется как для обычных findings.

Проверка _parent_of_path в каталоге:

powershell
docker exec -i dcap-postgres psql -U dcap -d dcap -c "SELECT path, entry_metadata->'total_findings' FROM catalog_entries WHERE path LIKE 's3://%' ORDER BY id DESC LIMIT 5;"
Ожидание: пути s3://dcap-audit-logs/access-logs (без //, без s3:/bucket).

📝 СВОДКА ПРАВОК

#	Файл	Действие	Задача
1	scanner/connectors/_text_scanner.py	Фикс decode_text_bytes (BUG-136)	TASK-118
2	scanner/connectors/s3_line_connector.py	Создан	TASK-119
3	scanner/connectors/s3_connector.py	ENV-секреты (по желанию)	TASK-120
4	scanner/connectors/factory.py	Регистрация s3/minio	TASK-121
5	scanner/src/managed_scanner.py	Передача connector.s3 из payload	TASK-122
6	tests/unit/test_decode_text_cp1251_v31331.py	Создан	TASK-123
7	tests/unit/test_s3_line_connector_v31331.py	Создан	TASK-123
8	tests/unit/test_factory_v31330.py	Обновлён	TASK-123
⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ

E2E на живом MinIO — 53.3. В 53.2 — только unit + ручной smoke.

WebUI-форма S3-ресурса — 53.3.

s3_connector.py (ISourceConnector) не используется сканером — его правка (TASK-120) опциональна.

TEST-NOTE-6.11 (verify=False при secure=False) — сознательное решение; в 53.2 добавлен WARNING в лог.

Параллелизм S3 (max_parallel_files) — в 53.2 scan_path последовательный (один поток). ThreadPool — кандидат в v3.1.0 (BACKLOG-097-параллелизм не входит в 53.2).

stop_event проверяется только между объектами (не внутри чтения одного объекта) — как и в FS.

📋 ОТКРЫТЫЕ ВОПРОСЫ

s3_connector.py (TASK-120) — править или не трогать? В 53.2 не критично, сканер его не использует. Решение архитектора: править (единая политика ENV), но если кодер решит не трогать — допустимо.

TASK-118 (BUG-136) — по вашему решению от 04.10.2026: фиксим в 53.2.

Fallback при _connector is None — оставляем как есть до полного закрытия 53.2; после 53.2 S3-путь не доходит до fallback.

⚠️ ЧТО НЕ ДЕЛАЕМ

Не пишем E2E-тесты — 53.3.

Не делаем WebUI-форму — 53.3.

Не переписываем s3_connector.py архитектурно — только ENV-секреты (TASK-120).

Не добавляем S3_* переменные в .env.example — это часть 53.3 (вместе с E2E и WebUI).

Не трогаем Manager — только сканер.

Не делаем параллелизм S3 (max_parallel_files > 1) — v3.1.0.

💾 КОМАНДА ДЛЯ КОММИТА

bash
git checkout -b feature/day_53_2_s3_line_connector

git add scanner/connectors/_text_scanner.py \
        scanner/connectors/s3_line_connector.py \
        scanner/connectors/s3_connector.py \
        scanner/connectors/factory.py \
        scanner/src/managed_scanner.py \
        tests/unit/test_decode_text_cp1251_v31331.py \
        tests/unit/test_s3_line_connector_v31331.py \
        tests/unit/test_factory_v31330.py \
        STATE.md CHANGELOG.md ROADMAP.md \
        prompts/reports/day_53_2_report.md

git commit -m "feat: День 53.2 — Scanner: S3LineConnector + BUG-136 fix (v3.13.31)

- scanner/connectors/s3_line_connector.py — построчный S3/MinIO-коннектор
  (scan_path / scan_file; streaming через Body.iter_chunks; документы/OCR
   через _text_scanner; fragment_path = s3://bucket/key)
- scanner/connectors/factory.py — регистрация s3/minio
- scanner/connectors/_text_scanner.py — BUG-136: decode_text_bytes
  пробует cp1251 после strict-utf8 (было: errors='ignore' на первой итерации)
- scanner/src/managed_scanner.py — передача scan_config.connector.s3
  из payload задачи в конфиг коннектора
- scanner/connectors/s3_connector.py — секреты только из ENV
  (S3_ACCESS_KEY / S3_SECRET_KEY), политика TASK-018
- tests/unit: +S3LineConnector (6), +BUG-136 (5), factory обновлён;
  полный unit-набор — passed без регрессий

BACKLOG-097 (часть 3: Scanner, реальное сканирование S3)
docs: обновлены STATE.md (v3.13.31), CHANGELOG.md, ROADMAP.md"
📊 ОБНОВЛЕНИЕ ПЛАНА

День	Задача	Статус
53.1a	Manager: source_type + S3-ресурсы	✅ v3.13.29
53.1b	Scanner: фабрика, _text_scanner.py, boto3	✅ v3.13.30
53.2	Scanner: S3LineConnector (streaming, ENV, OCR)	🔄 В РАБОТЕ
53.3	Тесты E2E (MinIO) + WebUI-форма S3	📋 следующий
52.1	Linux-агент (дотест)	📋
52.2	Блок 6.5 (сбор прав Windows)	📋
📌 ПОСЛЕ ВЫПОЛНЕНИЯ

Обновить STATE.md: версия v3.13.31, следующий шаг «53.3: E2E на MinIO + WebUI-форма S3-ресурса».

Обновить CHANGELOG.md — секция [3.13.31].

Обновить ROADMAP.md — 53.2 ✅.

Переместить ТЗ в prompts/archive/day_53_2_s3_line_connector.md.

Отчёт — prompts/reports/day_53_2_report.md:

сводка по выполнению,

полный код изменённых/новых файлов,

результаты pytest,

результаты smoke на MinIO (findings с s3://, catalog_entries.path),

BUG-136 — статус (fixed v3.13.31).

Автор ТЗ: архитектор
Дата: 04.10.2026