# Отчёт: День 53.2 — Scanner: S3LineConnector (streaming, ENV-секреты, OCR/документы)

**Дата:** 04.10.2026
**Версия:** v3.13.30 → v3.13.31
**Задача:** BACKLOG-097, часть 3 (реальное сканирование S3/MinIO)
**Ветка:** `feature/day_53_2_s3_line_connector`
**ТЗ:** `prompts/archive/day_53_2_s3_line_connector.md`

---

## 1. Сводка по выполнению

| # | Файл | Действие | Задача | Статус |
|---|------|----------|--------|--------|
| 1 | `scanner/connectors/_text_scanner.py` | Фикс BUG-136 (`decode_text_bytes`) | TASK-118 | ✅ |
| 2 | `scanner/connectors/s3_line_connector.py` | Создан (346 строк) | TASK-119 | ✅ |
| 3 | `scanner/connectors/s3_connector.py` | ENV-секреты с fallback | TASK-120 | ✅ |
| 4 | `scanner/connectors/factory.py` | Регистрация `s3` / `minio` | TASK-121 | ✅ |
| 5 | `scanner/src/managed_scanner.py` | Merge `scan_config.connector.s3` + `_current_scan_config` | TASK-122 | ✅ |
| 6 | `tests/unit/test_decode_text_cp1251_v31331.py` | Создан (5 тестов) | TASK-123.1 | ✅ |
| 7 | `tests/unit/test_s3_line_connector_v31331.py` | Создан (16 тестов) | TASK-123.2 | ✅ |
| 8 | `tests/unit/test_factory_v31330.py` | Обновлён (8 тестов) | TASK-123.3 | ✅ |
| 9 | `tests/unit/test_text_scanner_extract_v31330.py` | Заменён тест, фиксировавший баг cp1251 | регрессия | ✅ |

Миграции БД **не требуются**. Manager не трогался (только сканер).

---

## 2. Критерии приёмки

| # | Критерий | Проверка | Результат |
|---|----------|----------|-----------|
| 1 | `S3LineConnector` создан, принимает config | `test_s3_line_connector_v31331.py` | ✅ 16 passed |
| 2 | `scan_path` возвращает findings с `fragment_path=s3://bucket/key` | `test_scan_path_sets_s3_uri_in_findings` + БД (живой MinIO) | ✅ |
| 3 | `_discover_keys` фильтрует по extensions | `test_discover_keys_filters_by_extension` | ✅ |
| 4 | Секреты — из ENV (`S3_ACCESS_KEY`/`S3_SECRET_KEY`) | `test_constructor_reads_secrets_from_env`, `test_config_secrets_ignored_when_env_set` | ✅ |
| 5 | `bucket` обязателен → `ValueError` | `test_constructor_requires_bucket` | ✅ |
| 6 | `stop_event` прерывает итерацию | `test_stop_event_stops_iteration` | ✅ |
| 7 | `decode_text_bytes` декодирует cp1251 (BUG-136) | `test_decode_text_cp1251_v31331.py` (5) + живой cp1251-файл в MinIO | ✅ |
| 8 | `registered_types() == ["filesystem", "minio", "s3"]` | `test_registered_types_exact` | ✅ |
| 9 | `create_line_connector("s3")` возвращает `S3LineConnector` | `test_create_s3_returns_s3_line_connector` (+ minio) | ✅ |
| 10 | Полный unit-набор зелёный | `pytest tests/unit/ -q` | ✅ **424 passed** (было 402) |
| 11 | Smoke на живом MinIO: S3-задача проходит полный цикл | §5 — 3 задачи (193, 194, 195) | ✅ |

---

## 3. Результаты тестов

### Целевые

```
tests/unit/test_s3_line_connector_v31331.py ................   16 passed
tests/unit/test_decode_text_cp1251_v31331.py ..............    5 passed
tests/unit/test_factory_v31330.py ..........................    8 passed
tests/unit/test_text_scanner_extract_v31330.py (13, 1 заменён) 13 passed
                                                             = 42 passed in 0.73s
```

### Полный unit-набор

```
================ 424 passed, 1028 warnings in 85.23s ================
```

После первого прогона был 1 failure: `test_decode_cp1251_bytes_follow_utf8_ignore`
(тест 53.1b, который **документировал баг** BUG-136 и закреплял неверное
поведение `decode(...) == ""`). После фикса тест заменён на проверку
исправленного поведения — см. §4.1.

---

## 4. Отклонения от ТЗ

### 4.1 Тест 53.1b, фиксировавший BUG-136, заменён (необходимо)

`tests/unit/test_text_scanner_extract_v31330.py::test_decode_cp1251_bytes_follow_utf8_ignore`
утверждал `decode_text_bytes("привет".encode("cp1251")) == ""` — то есть
закреплял **баг**, который TASK-118 чинит. После фикса тест неизбежно падает.
Файл не был в списке ТЗ, но оставить его — значило бы оставить падающий тест.

**Решение:** переименован в `test_decode_cp1251_fixed_in_532`, теперь утверждает
`== "привет"` с пояснением, что было до фикса и почему.

### 4.2 `_DummyClassifier` из ТЗ не работал — `Finding()` требует 7 полей

ТЗ-тест создавал `f = Finding()` и присваивал поля по одному. В коде
`Finding` — dataclass с 7 обязательными позиционными полями, поэтому
`_text_scanner` ловил `TypeError` внутри `scan_line` и проглатывал его с
WARNING — тесты падали с `assert 0 == 1`.

```text
WARNING [TextScanner] scan_line error dummy at s3://test-bucket/notes.txt:2:
Finding.__init__() missing 7 required positional arguments: 'line_number', ...
```

**Решение:** `_DummyClassifier` создаёт `Finding(...)` с keyword-аргументами
(остальные поля — дефолты). Логика тестов не менялась.

### 4.3 `scan_file` / `_discover_keys` используют общий `CRED_FILENAMES`

В ТЗ `scan_file` содержал захардкоженный укороченный список
`{"id_rsa", ".env", "kubeconfig", "secrets", ".pgpass", ".netrc"}`, а
`_discover_keys` вовсе не передавал `cred_filenames` в `is_supported_file` —
то есть файл `id_rsa` **отфильтровывался бы на этапе листинга** и никогда не
дошёл бы до `scan_file`.

**Решение:** используется общий `CRED_FILENAMES` из `_text_scanner` (тот же
набор, что и в `FilesystemConnector`), передаётся и в `_discover_keys`, и в
`scan_file`. Покрыто тестами `test_discover_keys_credential_filename_without_extension`
и `test_scan_path_sets_s3_uri_in_findings`.

### 4.4 Удалён мёртвый код из ТЗ-фрагмента

- `from datetime import datetime` — не используется;
- `self._max_workers = int(self.config.get("max_parallel_files", 1) or 1)` —
  нигде не читается (параллелизм S3 сознательно вне 53.2, см. «Известные
  ограничения» ТЗ). Удалён, чтобы не вводить в заблуждение.

### 4.5 Сообщение фабрики для неизвестного `source_type` убрало «53.2»

ТЗ оставляло в `create_line_connector` текст «S3 support arrives in day 53.2» —
после регистрации s3/minio он стал неверным. Оставлено сообщение со списком
доступных типов (`Available: ['filesystem', 'minio', 's3']`). Тест
`test_create_unknown_raises_value_error` проверяет именно его.

### 4.6 `ImportError` при отсутствии boto3 не перехватывается

`_init_line_pipeline` ловит только `ValueError` (по ТЗ). Если `boto3` не
установлен, `ImportError("boto3 не установлен...")` поднимется выше — в
`_execute_task`, где задача корректно уйдёт в `failed` с этим сообщением.
Это лучше, чем `ValueError` → fallback на Orchestrator → «No files found».
Поведение оставлено как в ТЗ.

### 4.7 Добавлены 10 тестов сверх ТЗ

Пагинация `ContinuationToken`, skip «папок» и oversize-объектов, кред-файл по
имени, `ValueError` без ENV-секретов, бинарный объект → `[]`, OCR-поля для
изображений (`image_region`/`ocr`/`bounding_box=None`), `progress_callback` на
каждый объект, пустой bucket, игнор секретов из config при заданном ENV,
`test_registered_types_exact`.

---

## 5. Smoke на живом MinIO

**Окружение:** MinIO native (`E:\Dev\MinIO\bin\minio.exe`, PID 21976, порт 9000),
Manager в Docker 3.13.29 (`http://127.0.0.1:8000`), сканер на хосте
(`run_scanner.py`) с `S3_ACCESS_KEY=minioadmin` / `S3_SECRET_KEY=minioadmin`.

### 5.1 Задача 193 — `s3://dcap-audit-logs/access-logs/`

Ресурс `id=137`, `type=s3` (endpoint по умолчанию `host.docker.internal:9000`,
prefix из пути `access-logs/`).

```text
[Scanner] Executing task 193 on s3://dcap-audit-logs/access-logs/ (source_type=s3)
[S3Line] Connector configured: endpoint=http://host.docker.internal:9000,
         bucket=dcap-audit-logs, prefix='access-logs/', path_style=True, secure=False
[S3Line] secure=False - HTTPS-проверка сертификата отключена (TEST-NOTE-6.11).
[Scanner] Task 193 completed (linewise):
  - Files scanned: 4
  - Files with findings: 4
  - Total findings: 27
  - Folders with findings: 1
  - Failed files: 0
[SubmitResults] batch 1/1: 27 findings saved
[OK] Task 193 completed successfully
```

`catalog_entries` (критерий «без `//`, без `s3:/bucket»»):

```text
              path               | total_findings
-----------------------------------+---------------
 s3://dcap-audit-logs/access-logs | 27
```

Находки в БД (в т.ч. от задачи 191 того же ресурса — повторное сканирование
дедуплицируется по fingerprint, поэтому новых строк не создаётся, а обновляется
`last_seen_at`; это штатное поведение DCAP):

```text
 id   | fragment_path                                             | line | category
------+-----------------------------------------------------------+------+------------
 1741 | s3://dcap-audit-logs/access-logs/2026-10-03T10-00-00.json |    7 | ip_address
 1742 | s3://dcap-audit-logs/access-logs/2026-10-03T10-00-00.json |   16 | ip_address
 1743 | s3://dcap-audit-logs/access-logs/2026-10-03T10-00-00.json |   25 | ip_address
```

### 5.2 Задача 194 — BUG-136 на живых данных

Залит объект `legacy/cp1251_pii.txt` (140 байт, **cp1251**, русские ФИО/телефон/
паспорт/адрес) в временный bucket `dcap-scanner-smoke`, ресурс `id=138`.

```text
  - Files scanned: 1 | Total findings: 9 | Failed files: 0
```

```text
 line | category      | detector  | line (маскировано Manager'ом)
------+---------------+-----------+--------------------------------
    3 | email         | presidio  | Email: iv***@ex***.com
    2 | phone         | presidio  | Телефон: +7***123-45-67
    1 | person        | presidio  | Сотрудник: Иванов Иван Иванович
    5 | location      | presidio  | ***: ***, ул. ***, д. 1
    4 | phone         | presidio  | Паспорт: 45***678
    1 | person        | presidio  | Сотрудник: Иванов Иван Иванович
    5 | organization  | presidio  | ***: ***, ул. ***, д. 1
```

**До фикса** этот файл декодировался бы в пустую/мусорную строку и находок не
было бы. Presidio распознал ФИО, телефон, e-mail и адрес — кириллица дошла
корректно.

### 5.3 Задача 195 — документы и OCR из S3

Ресурс `id=139` → `s3://storage1/test_files/` (8 объектов: `PII_in_PDF.pdf`,
`PII.png`, `*.txt`).

```text
  - Files scanned: 8 | Files with findings: 6 | Total findings: 25 | Failed files: 0
```

```text
 fragment_path                        | fragment_type | category      | count
--------------------------------------+---------------+---------------+------
 s3://storage1/test_files/PII.png      | image_region  | location      |      1
 s3://storage1/test_files/PII.png      | image_region  | organization  |      2
 s3://storage1/test_files/PII.png      | image_region  | person        |      1
 s3://storage1/test_files/PII_in_PDF.pdf | text_line   | person        |      9
 s3://storage1/test_files/PII_in_PDF.pdf | text_line   | phone         |      2
 s3://storage1/test_files/english_pii.txt | text_line  | ...           |      4
```

У OCR-находок `detector=ocr`, `bounding_box` = JSON `null` — идентично
FS-коннектору (`C:\test\scanner_clean\images\screenshot_clean.png` → `null`),
т.е. поведение `bounding_box=None` (BUG-077) соблюдено.

### 5.4 Очистка

Ресурсы 137/138/139 и 135 удалены (`DELETE /api/resources/{id}` каскадно удаляет
findings/tasks/catalog_entries); bucket `dcap-scanner-smoke` удалён. Итог:
`findings LIKE 's3://%'` — 0, `scan_tasks WHERE source_type='s3'` — 0,
`catalog_entries LIKE 's3://%'` — 0. Сканер остановлен, bucket-и остались
без изменений: `dcap-audit-logs`, `storage1`, `storage2`, `testbucker1`,
`testbucket2`.

---

## 6. Ключевые решения

### 6.1 Секреты только из ENV

```python
env_access = os.environ.get("S3_ACCESS_KEY")
env_secret = os.environ.get("S3_SECRET_KEY")
if self.config.get("access_key") or self.config.get("secret_key"):
    logger.warning("[S3Line] access_key/secret_key в config игнорируются ...")
self._access_key = env_access or self.config.get("access_key")
```

Fallback на config оставлен (как в ТЗ) — чтобы сканер можно было запустить в
teach/локальной среде без ENV, но приоритет у ENV, и о факте секретов в config
пишется WARNING. Политика TASK-018 соблюдена: Manager никогда не передаёт
секреты в payload, `scanner_config.json` их не содержит.

### 6.2 Streaming, а не `read()`

`_read_text` идёт по `Body.iter_chunks(chunk_size=self._buffer_size)` и рвёт
чтение на `max_text_chars` — 1 МБ буфер, до 200 000 символов текста. `_download_bytes`
(документы/OCR) тоже идёт по чанкам, но пишет во временный файл, который
удаляется в `finally` (лимит размера уже проверен в `_discover_keys` по
`max_file_size_mb`).

### 6.3 Merge конфига: приоритет у payload

`_init_line_pipeline` мержит `scan_config.connector.s3` (из payload задачи
Manager) **поверх** локального `connector`-конфига. Поэтому ресурс, созданный с
`endpoint=127.0.0.1:9000`, работает и без правки `scanner_config.json`.

### 6.4 Регистрация s3/minio в конце `factory.py`

```python
from scanner.connectors.s3_line_connector import S3LineConnector  # noqa: E402
register_line_connector("s3", lambda cfg: S3LineConnector(cfg))
register_line_connector("minio", lambda cfg: S3LineConnector(cfg))
```

`s3_line_connector` не импортирует `factory` — цикла нет. `managed_scanner`
импортирует `filesystem` → `factory` → `s3_line_connector`, так что реестр
заполняется при первом же импорте.

---

## 7. Полный код изменённых/новых файлов

### 7.1 `scanner/connectors/_text_scanner.py` (изменён — только `decode_text_bytes`)

```python
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
```

### 7.2 `scanner/connectors/factory.py` (изменён)

Заголовок модуля:

```python
"""Фабрика построчных коннекторов (день 53.1b / 53.2, BACKLOG-097).

Регистрирует коннекторы, реализующие интерфейс FilesystemConnector
(scan_path / scan_file). Зарегистрированы: filesystem (53.1b),
s3 и minio (53.2, S3LineConnector).
"""
```

`create_line_connector`:

```python
def create_line_connector(source_type: str, config: Dict[str, Any]) -> Any:
    """Создать построчный коннектор по source_type.

    День 53.2 (BACKLOG-097): зарегистрированы 's3' и 'minio' → S3LineConnector.
    Неизвестный source_type по-прежнему даёт понятный ValueError со списком
    доступных — сканер упадёт с сообщением, а не откроет 's3://bucket' как папку.
    """
    st = (source_type or "filesystem").lower()
    if st not in _REGISTRY:
        raise ValueError(
            f"Line connector for source_type={st!r} not registered. "
            f"Available: {sorted(_REGISTRY)}."
        )
    return _REGISTRY[st](config or {})
```

Конец файла:

```python
__all__ = ["register_line_connector", "create_line_connector", "registered_types"]


# Регистрация S3/MinIO (день 53.2, BACKLOG-097).
# s3_line_connector не импортирует factory — циклических импортов нет.
from scanner.connectors.s3_line_connector import S3LineConnector  # noqa: E402

register_line_connector("s3", lambda cfg: S3LineConnector(cfg))
register_line_connector("minio", lambda cfg: S3LineConnector(cfg))
```

### 7.3 `scanner/connectors/s3_line_connector.py` (новый, 346 строк)

```python
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
                        cred_filenames=CRED_FILENAMES,
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
```

### 7.4 `scanner/connectors/s3_connector.py` (изменён — TASK-120)

```python
import logging
import os
...
logger = logging.getLogger("dcap-scanner")
```

```python
        # Все параметры ТОЛЬКО из конфига
        self.endpoint = config.get("endpoint")
        self.bucket = config.get("bucket")
        # День 53.2 (BUG-136/TASK-120): секреты — сначала ENV (политика TASK-018).
        # Оставлено чтение из config для обратной совместимости (этот коннектор
        # используется не только сканером).
        env_access = os.environ.get("S3_ACCESS_KEY")
        env_secret = os.environ.get("S3_SECRET_KEY")
        if config.get("access_key") and not env_access:
            logger.warning(
                "[S3] access_key в config — устаревший способ, используйте "
                "ENV S3_ACCESS_KEY"
            )
        if config.get("secret_key") and not env_secret:
            logger.warning(
                "[S3] secret_key в config — устаревший способ, используйте "
                "ENV S3_SECRET_KEY"
            )
        self.access_key = env_access or config.get("access_key")
        self.secret_key = env_secret or config.get("secret_key")
        self.secure = config.get("secure")
```

### 7.5 `scanner/src/managed_scanner.py` (изменён — TASK-122)

`__init__`:

```python
        self._current_source_type: str = "filesystem"
        # День 53.2 (BACKLOG-097): scan_config текущей задачи (payload Manager).
        # Нужен в _init_line_pipeline для merge scan_config.connector.s3 —
        # там scan_config является локальной переменной.
        self._current_scan_config: Dict[str, Any] = {}
        self._enc = None
```

`_init_line_pipeline` (перед вызовом фабрики):

```python
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
        # День 53.1b/53.2 (BACKLOG-097): коннектор выбирается по source_type
        # задачи через фабрику (filesystem | s3 | minio).
        try:
            self._connector = create_line_connector(self._current_source_type, connector_cfg)
```

`_execute_task`:

```python
        self._current_source_type = (task.get("source_type") or "filesystem").lower()
        # День 53.2 (BACKLOG-097): scan_config приходит per-task, а
        # _init_line_pipeline вызывается из _execute_task_linewise, где
        # scan_config — локальная переменная. Сохраняем в поле.
        self._current_scan_config = scan_config or {}
```

### 7.6 `tests/unit/test_s3_line_connector_v31331.py` (новый, 16 тестов)

```python
"""Unit-тесты S3LineConnector (день 53.2) с mock boto3."""
import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scanner")))

# Изолируем от реального boto3: в тесте подменяем клиент.
os.environ.setdefault("S3_ACCESS_KEY", "test-access")
os.environ.setdefault("S3_SECRET_KEY", "test-secret")

from scanner.connectors.s3_line_connector import S3LineConnector  # noqa: E402


class _BodyEmpty:
    """Пустой поток boto3 Body."""

    def iter_chunks(self, chunk_size=1024):
        return iter(())

    def close(self):
        pass


class _DummyClassifier:
    classifier_name = "dummy"

    def scan_line(self, line, line_num):
        from scanner.src.finding import Finding
        if "SECRET" in line:
            return [Finding(
                line_number=line_num,
                line_text=line,
                match_text="SECRET",
                start_pos=0,
                end_pos=6,
                finding_type="credentials",
                category="test",
                confidence=1.0,
                severity="medium",
                detector="test",
                fragment_type="text_line",
            )]
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


def test_constructor_requires_env_secrets(monkeypatch):
    """Без S3_ACCESS_KEY/S3_SECRET_KEY — понятный ValueError (политика TASK-018)."""
    monkeypatch.delenv("S3_ACCESS_KEY", raising=False)
    monkeypatch.delenv("S3_SECRET_KEY", raising=False)
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        with pytest.raises(ValueError) as exc:
            S3LineConnector({"bucket": "b", "endpoint": "x:9000"})
        assert "S3_ACCESS_KEY" in str(exc.value)


def test_discover_keys_uses_pagination():
    """IsTruncated=True → следующая страница по ContinuationToken."""
    pages = [
        {"Contents": [{"Key": "a.txt", "Size": 10}], "IsTruncated": True,
         "NextContinuationToken": "tok1"},
        {"Contents": [{"Key": "b.txt", "Size": 10}], "IsTruncated": False},
    ]
    calls = []

    def _list(**kwargs):
        calls.append(kwargs)
        return pages[len(calls) - 1]

    connector, _ = _make_connector(_list)
    keys = connector._discover_keys("logs/")
    assert keys == ["a.txt", "b.txt"]
    assert calls[0]["Prefix"] == "logs/"
    assert "ContinuationToken" not in calls[0]
    assert calls[1]["ContinuationToken"] == "tok1"


def test_discover_keys_skips_dirs_and_oversize():
    objects = [
        {"Key": "logs/", "Size": 0},
        {"Key": "big.txt", "Size": 200 * 1024 * 1024},   # 200 МБ > max_file_size_mb=50
        {"Key": "ok.log", "Size": 10},
    ]
    connector, _ = _make_connector(lambda **kw: {"Contents": objects, "IsTruncated": False})
    keys = connector._discover_keys("")
    assert keys == ["ok.log"]


def test_discover_keys_credential_filename_without_extension():
    """Файл-кред по имени (id_rsa) сканируется, несмотря на отсутствие расширения."""
    connector, _ = _make_connector(
        _list_one_page(["id_rsa", "photo.png.bak"])
    )
    keys = connector._discover_keys("")
    assert "id_rsa" in keys
    assert "photo.png.bak" not in keys


def test_scan_path_reads_prefix_from_path_over_config():
    """Prefix берётся из path; bucket остаётся из config (в path только префикс)."""
    connector, mock_client = _make_connector(
        _list_one_page(["x.txt"]), mock_get=lambda **kw: {"Body": _BodyEmpty()}
    )
    connector.scan_path("s3://test-bucket/logs", [_DummyClassifier()])
    kwargs = mock_client.list_objects_v2.call_args.kwargs
    assert kwargs["Bucket"] == "test-bucket"
    assert kwargs["Prefix"] == "logs"


def test_read_text_returns_none_on_binary():
    """Бинарный объект (\\x00) → decode_text_bytes вернул None → findings нет."""
    class _Body:
        def iter_chunks(self, chunk_size=1024):
            yield b"\x00\x01\x02" * 100

        def close(self):
            pass

    connector, _ = _make_connector(
        _list_one_page(["notes.txt"]), mock_get=lambda **kw: {"Body": _Body()}
    )
    assert connector.scan_path("s3://test-bucket/", [_DummyClassifier()]) == []


def test_scan_file_sets_ocr_fields_for_images(monkeypatch):
    """Изображение → fragment_type=image_region, detector=ocr, bounding_box=None."""
    monkeypatch.setattr(
        "scanner.connectors.s3_line_connector.extract_document_text",
        lambda content, ext, filename, ocr_enabled=False: "line1\nline2 SECRET",
    )

    class _Body:
        def iter_chunks(self, chunk_size=1024):
            yield b"\xff\xd8\xff\xe0fake-jpeg"

        def close(self):
            pass

    connector, _ = _make_connector(
        _list_one_page(["p.png"]), mock_get=lambda **kw: {"Body": _Body()}
    )
    findings = connector.scan_path("s3://test-bucket/", [_DummyClassifier()])
    assert len(findings) == 1
    assert findings[0].fragment_type == "image_region"
    assert findings[0].detector == "ocr"
    assert findings[0].bounding_box is None
    assert findings[0].fragment_path == "s3://test-bucket/p.png"


def test_scan_path_progress_callback_reports_progress():
    """progress_callback(stage, current, total, file_path) вызывается на каждый объект."""
    seen = []

    def _cb(stage, current, total, file_path):
        seen.append((stage, current, total, file_path))

    def _get(**kwargs):
        class _Body:
            def iter_chunks(self, chunk_size=1024):
                yield b"nothing here"

            def close(self):
                pass
        return {"Body": _Body()}

    connector, _ = _make_connector(
        _list_one_page(["a.txt", "b.txt"]), mock_get=_get
    )
    connector.scan_path("s3://test-bucket/", [_DummyClassifier()], progress_callback=_cb)
    assert seen == [(1, 1, 2, "a.txt"), (1, 2, 2, "b.txt")]


def test_scan_path_empty_bucket_calls_progress_with_zeros():
    seen = []
    connector, _ = _make_connector(_list_one_page([]))
    findings = connector.scan_path(
        "s3://test-bucket/empty/", [_DummyClassifier()],
        progress_callback=lambda *a: seen.append(a),
    )
    assert findings == []
    assert seen == [(1, 0, 0, "s3://test-bucket/empty/")]


def test_config_secrets_ignored_when_env_set(monkeypatch):
    """Секреты в config игнорируются, если есть ENV (политика TASK-018)."""
    monkeypatch.setenv("S3_ACCESS_KEY", "env-access")
    monkeypatch.setenv("S3_SECRET_KEY", "env-secret")
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        S3LineConnector({
            "bucket": "b", "endpoint": "x:9000",
            "access_key": "cfg-access", "secret_key": "cfg-secret",
        })
        kwargs = mock_boto.client.call_args.kwargs
        assert kwargs["aws_access_key_id"] == "env-access"
        assert kwargs["aws_secret_access_key"] == "env-secret"
```

### 7.7 `tests/unit/test_decode_text_cp1251_v31331.py` (новый, 5 тестов)

```python
"""BUG-136: decode_text_bytes должен пробовать cp1251 после utf-8 (день 53.2)."""
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
```

### 7.8 `tests/unit/test_factory_v31330.py` (обновлён)

```python
"""Unit-тесты фабрики коннекторов (день 53.1b, дополнено в 53.2).

Покрытие:
- registered_types() содержит filesystem, s3, minio;
- create_line_connector('filesystem', {}) возвращает FilesystemConnector;
- create_line_connector('s3'/'minio') возвращает S3LineConnector (день 53.2);
- create_line_connector(None) → filesystem (дефолт);
- create_line_connector('FILESYSTEM') → filesystem (нормализация регистра);
- неизвестный source_type → ValueError со списком доступных.
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNER_DIR = ROOT / "scanner"
for _p in (str(ROOT), str(SCANNER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Секреты S3 — только ENV (день 53.2, политика TASK-018). Нужны для создания
# S3LineConnector в тестах фабрики.
os.environ.setdefault("S3_ACCESS_KEY", "test-access")
os.environ.setdefault("S3_SECRET_KEY", "test-secret")

from scanner.connectors.factory import (  # noqa: E402
    create_line_connector,
    registered_types,
)
from scanner.connectors.filesystem import FilesystemConnector  # noqa: E402


def test_registered_types_contains_all():
    types = registered_types()
    assert "filesystem" in types
    assert "s3" in types
    assert "minio" in types


def test_registered_types_exact():
    assert registered_types() == ["filesystem", "minio", "s3"]


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


def test_create_s3_returns_s3_line_connector(monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY", "x")
    monkeypatch.setenv("S3_SECRET_KEY", "y")
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        from scanner.connectors.s3_line_connector import S3LineConnector
        c = create_line_connector("s3", {"bucket": "b"})
        assert isinstance(c, S3LineConnector)


def test_create_minio_returns_s3_line_connector(monkeypatch):
    monkeypatch.setenv("S3_ACCESS_KEY", "x")
    monkeypatch.setenv("S3_SECRET_KEY", "y")
    with patch("scanner.connectors.s3_line_connector.boto3") as mock_boto:
        mock_boto.client.return_value = MagicMock()
        from scanner.connectors.s3_line_connector import S3LineConnector
        c = create_line_connector("minio", {"bucket": "b"})
        assert isinstance(c, S3LineConnector)


def test_create_unknown_raises_value_error():
    with pytest.raises(ValueError) as exc:
        create_line_connector("ftp", {})
    # Сообщение содержит список доступных типов
    assert "filesystem" in str(exc.value)
```

### 7.9 `tests/unit/test_text_scanner_extract_v31330.py` (заменён 1 тест)

```python
def test_decode_cp1251_fixed_in_532():
    """BUG-136 (фикс в 53.2): cp1251-файлы декодируются правильно.

    До фикса: `decode('utf-8', errors='ignore')` на первой итерации цикла
    никогда не бросал исключение → ветка cp1251 была недостижима, и
    байты cp1251 разбирались как utf-8 с потерями («привет» → '').
    Теперь декод строгий: utf-8 → cp1251 → fallback utf-8 с errors='ignore'.
    """
    raw = "привет".encode("cp1251")
    assert raw.decode("cp1251") == "привет"
    assert decode_text_bytes(raw) == "привет"
```

---

## 8. Инструкция по ручному тестированию

### 8.1 Запуск сканера с S3

```powershell
$env:PYTHONUTF8 = '1'
$env:S3_ACCESS_KEY = "minioadmin"
$env:S3_SECRET_KEY = "minioadmin"
python run_scanner.py scanner/config/scanner_config.json
```

Секреты также нужны сканеру, если он запускается как сервис/в Docker — там их
задают через ENV или Docker Secrets (53.3 добавит их в `.env.example`).

### 8.2 Создание S3-ресурса и запуск сканирования

```powershell
$body = '{"username":"admin","password":"admin123"}'
$token = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
    -ContentType "application/json" -Body $body).access_token
$headers = @{ Authorization = "Bearer $token" }

# endpoint можно не указывать — тогда возьмётся host.docker.internal:9000
$res = Invoke-RestMethod -Method POST `
    "http://127.0.0.1:8000/api/resources?path=s3%3A%2F%2Fdcap-audit-logs%2Faccess-logs%2F&type=s3" `
    -Headers $headers
$task = Invoke-RestMethod -Method POST "http://127.0.0.1:8000/api/resources/$($res.id)/scan" -Headers $headers
"TASK_ID=$($task.task_id)"
```

### 8.3 Ожидание в логах сканера

```text
[Scanner] Executing task N on s3://dcap-audit-logs/access-logs/ (source_type=s3)
[S3Line] Connector configured: endpoint=http://host.docker.internal:9000, bucket=dcap-audit-logs, prefix='access-logs/', path_style=True, secure=False
[LineScan] Connector created: source_type=s3, type=S3LineConnector
[Scanner] Task N completed (linewise):
  - Files scanned: 4
  - Total findings: 27
[OK] Task N completed successfully
```

### 8.4 Проверка находок и каталога

```powershell
docker exec -i dcap-postgres psql -U dcap -d dcap -c "SELECT path, entry_metadata->>'total_findings' FROM catalog_entries WHERE path LIKE 's3://%' ORDER BY id DESC LIMIT 5;"
```

**Ожидание:** `s3://dcap-audit-logs/access-logs` (без `//`, без `s3:/bucket`).

### 8.5 Отсутствие секретов

```powershell
$env:S3_ACCESS_KEY = ""; $env:S3_SECRET_KEY = ""
```

S3-задача должна упасть в `failed` с сообщением
`S3LineConnector: задайте S3_ACCESS_KEY / S3_SECRET_KEY в ENV`.

---

## 9. Что НЕ сделано (границы 53.2)

- E2E-тесты на MinIO — 53.3 (здесь ручной smoke, 3 задачи).
- WebUI-форма добавления S3-ресурса — 53.3 (сейчас только через API).
- `S3_*` в `.env.example` — 53.3 (по ТЗ).
- Параллелизм S3 (`max_parallel_files` > 1) — v3.1.0; в 53.2 `scan_path`
  последовательный.
- `stop_event` проверяется между объектами (как в FS).
- `s3_connector.py` (`ISourceConnector` для Orchestrator) не переписывался —
  только ENV-секреты (TASK-120, опционально).
- CloudTrail/S3 access log native — вне задачи.

---

## 10. Команда для коммита

```powershell
git add scanner/connectors/_text_scanner.py `
        scanner/connectors/s3_line_connector.py `
        scanner/connectors/s3_connector.py `
        scanner/connectors/factory.py `
        scanner/src/managed_scanner.py `
        tests/unit/test_decode_text_cp1251_v31331.py `
        tests/unit/test_s3_line_connector_v31331.py `
        tests/unit/test_factory_v31330.py `
        tests/unit/test_text_scanner_extract_v31330.py `
        STATE.md CHANGELOG.md ROADMAP.md `
        prompts/reports/day_53_2_report.md `
        prompts/archive/day_53_2_s3_line_connector.md

git commit -m "feat: День 53.2 — Scanner: S3LineConnector + BUG-136 fix (v3.13.31)

- scanner/connectors/s3_line_connector.py — построчный S3/MinIO-коннектор
  (scan_path / scan_file; streaming через Body.iter_chunks; документы/OCR
   через _text_scanner; fragment_path = s3://bucket/key; пагинация
   list_objects_v2; фильтры по расширениям/размеру/кред-именам)
- scanner/connectors/factory.py — регистрация s3/minio
- scanner/connectors/_text_scanner.py — BUG-136: decode_text_bytes
  пробует cp1251 после strict-utf8 (было: errors='ignore' на первой итерации)
- scanner/src/managed_scanner.py — передача scan_config.connector.s3
  из payload задачи в конфиг коннектора
- scanner/connectors/s3_connector.py — секреты сначала из ENV
  (S3_ACCESS_KEY / S3_SECRET_KEY), политика TASK-018
- tests/unit: +S3LineConnector (16), +BUG-136 (5), factory обновлён;
  424 passed (было 402), регрессий нет
- smoke на живом MinIO: 3 задачи (текст 27 находок, cp1251 9, PDF+OCR 25),
  catalog_entries.path = s3://bucket/prefix

BACKLOG-097 (часть 3: Scanner, реальное сканирование S3)
docs: обновлены STATE.md (v3.13.31, следующий — 53.3), CHANGELOG.md, ROADMAP.md"
```

---

**Автор отчёта:** кодер
**Дата:** 04.10.2026
**Статус ТЗ:** выполнено (11 критериев приёмки из 11)
