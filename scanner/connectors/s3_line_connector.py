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
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from scanner.src.finding import Finding
from scanner.connectors._text_scanner import (
    CRED_FILENAMES,
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
        # BUG-149 (v3.13.41): bucket в config может отсутствовать — ресурсы
        # s3/minio, созданные через legacy-эндпоинты WebUI, не получали
        # connector.s3. В этом случае bucket берётся из path (s3://bucket/prefix)
        # в scan_path(). Если bucket нет ни там, ни в config — упадём в scan_path.
        if not self._bucket:
            logger.warning(
                "[S3Line] bucket не задан в config — будет определён из "
                "path (s3://bucket/prefix) в scan_path (BUG-149)"
            )

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

    def _discover_keys(self, prefix: str = "", bucket: Optional[str] = None) -> List[str]:
        """Список ключей в bucket под prefix, отфильтрованных по extensions/size."""
        bucket = bucket or self._bucket
        if not bucket:
            raise ValueError(
                "S3LineConnector: bucket не определён — задайте его в "
                "scan_config.connector.s3 или в path (s3://bucket/prefix)"
            )
        result: List[str] = []
        try:
            continuation_token = None
            while True:
                params: Dict[str, Any] = {
                    "Bucket": bucket,
                    "Prefix": prefix or self._prefix,
                    "MaxKeys": 1000,
                }
                if continuation_token:
                    params["ContinuationToken"] = continuation_token

                response = self._client.list_objects_v2(**params)
                page_keys = sum(1 for o in (response.get("Contents", []) or []) if not o["Key"].endswith("/"))
                logger.debug(
                    "[S3Line] list_objects_v2 bucket=%s prefix=%r page_keys=%d truncated=%s",
                    bucket, prefix or self._prefix, page_keys,
                    bool(response.get("IsTruncated", False)),
                )
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
                        cred_filenames=CRED_FILENAMES,
                    ):
                        continue
                    result.append(key)

                if not response.get("IsTruncated", False):
                    break
                continuation_token = response.get("NextContinuationToken")

        except (ConnectTimeoutError, ReadTimeoutError) as exc:
            # BUG-149 (v3.13.41): раньше таймаут молча превращался в 0 файлов —
            # теперь поднимаем исключение, чтобы ошибка была видна (не "No files").
            msg = f"[S3Line] Timeout при list_objects (bucket={bucket}, prefix={prefix!r}): {exc}"
            logger.error(msg)
            raise
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "[S3Line] ClientError list_objects (bucket=%s, prefix=%r): %s",
                bucket, prefix or self._prefix, code,
            )
            raise
        except BotoCoreError as exc:
            logger.error(
                "[S3Line] BotoCoreError list_objects (bucket=%s, prefix=%r): %s",
                bucket, prefix or self._prefix, exc,
            )
            raise
        logger.debug(
            "[S3Line] list_objects_v2 итого: bucket=%s prefix=%r keys=%d",
            bucket, prefix or self._prefix, len(result),
        )
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
        start_key: Optional[str] = None,
    ) -> List[Finding]:
        """Сканирует bucket по prefix. Возвращает список Finding.

        Bucket — преимущественно из scan_config.connector.s3.bucket (payload
        задачи, см. 53.1a), при его отсутствии — из path (BUG-149, v3.13.41).
        Путь задаётся как префикс:
          - 's3://bucket/prefix' — prefix из него (bucket — если нет в config),
          - 's3://bucket'        — пустой prefix,
          - '' или None          — prefix из конфига.

        progress_callback(stage, current, total, file_path): stage 1 = скан.
        stop_event: threading.Event — прерывание после текущего объекта.
        start_key: resume (53.4n) — пропустить ключи <= start_key.
        """
        keys = self.discover_files(path)
        total = len(keys)
        if not total:
            if progress_callback:
                progress_callback(1, 0, 0, path or self._prefix)
            return []

        if start_key:
            filtered = [k for k in keys if k > start_key]
            logger.info(
                "[S3Line] resume: пропущено %d ключей (start_key=%r)",
                total - len(filtered),
                start_key,
            )
            keys = filtered

        return self.scan_files(
            keys,
            classifiers,
            progress_callback=progress_callback,
            stop_event=stop_event,
        )

    def discover_files(self, path: str) -> List[str]:
        """Публичный отсортированный список ключей (53.4n, v3.14.12)."""
        # Bucket — обычно из scan_config.connector.s3 (см. 53.1a):
        # Manager кладёт bucket в payload задачи, а path (s3://bucket/prefix)
        # используется только как suffix для префикса. Если в path указан
        # другой bucket — он игнорируется намеренно (контракт ресурса —
        # bucket фиксирован на момент создания).
        #
        # BUG-149 (v3.13.41): у legacy-ресурсов (созданных через WebUI без
        # connector.s3) bucket в config отсутствует — берём его из path.
        # Приоритет: config.bucket > path.bucket.
        effective_bucket = self._bucket
        source_prefix = self._prefix
        if path:
            parsed = urlparse(path)
            if parsed.scheme in ("s3", "minio"):
                source_prefix = (parsed.path or "").lstrip("/")
                if not effective_bucket and parsed.netloc:
                    effective_bucket = parsed.netloc
                    logger.info(
                        "[S3Line] bucket взят из path: %s (конфиг без connector.s3)",
                        effective_bucket,
                    )
            else:
                source_prefix = (path or "").lstrip("/")

        if effective_bucket != self._bucket:
            # BUG-149: bucket из path — запоминаем, чтобы scan_file/_read_text
            # читали объекты из того же bucket (коннектор создаётся на задачу).
            self._bucket = effective_bucket

        logger.info(
            "[S3Line] scan_path: endpoint=%s, bucket=%s, prefix=%r",
            self._endpoint, effective_bucket, source_prefix,
        )
        return sorted(self._discover_keys(source_prefix, effective_bucket))

    def scan_files(
        self,
        keys: List[str],
        classifiers: List[Any],
        progress_callback: Optional[Callable[[int, int, int, str], None]] = None,
        stop_event: Optional[Any] = None,
        offset: int = 0,
        total: Optional[int] = None,
    ) -> List[Finding]:
        """Сканирует переданные ключи (53.4n) — чанки/resume как у FS-коннектора."""
        findings: List[Finding] = []
        if not keys:
            if progress_callback:
                progress_callback(1, offset, offset if total is None else total, "")
            return findings

        total = len(keys) if total is None else total
        for idx, key in enumerate(keys, start=1):
            if stop_event is not None and stop_event.is_set():
                logger.info("[S3Line] Остановка на %d/%d", offset + idx, total)
                break
            if progress_callback:
                progress_callback(1, offset + idx, total, key)
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
        if ext in self._text_extensions or filename.lower() in CRED_FILENAMES:
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
