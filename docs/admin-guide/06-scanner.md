# 06. Сканер

> **Руководство администратора DCAP.**
> Раздел «Сканер»: установка, настройка, ENV, ключи Findings, FP-фильтр.

**Обновлено:** 22.10.2026
**Версия:** v3.14.14

---

## 📖 Содержание

1. [Обзор](#1-обзор)
2. [Установка](#2-установка)
3. [Конфигурация](#3-конфигурация)
4. [ENV-переменные](#4-env-переменные)
5. [Ключи Findings (обязательно)](#5-ключи-findings-обязательно)
6. [Запуск](#6-запуск)
7. [Интеграция с Manager](#7-интеграция-с-manager)
8. [S3/MinIO-сканирование](#8-s3minio-сканирование)
9. [Параллелизм ФС](#9-параллелизм-фс-v31411)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Обзор

Scanner — тяжёлый агент сканирования файлов (Tesseract, spaCy, Presidio).

**Работает на хосте, не в Docker.** Причина: задания приходят с путями хоста
(`E:\...`, `/mnt/...`), а контейнер видит только заранее смонтированные тома.

**Ключевые функции:**
- Обход ФС, классификация PII / credentials / code.
- **Шифрование находок на стороне сканирующего хоста** (AES-256-GCM).
- **Маскирование** перед отправкой.
- **FP-фильтр** — проверка fingerprints до отправки.
- **Offline-буфер** — при недоступности Manager.

---

## 2. Установка

### Требования

- Python 3.11+
- Tesseract OCR
- spaCy модели (`ru_core_news_sm`, `en_core_web_sm`)
- Presidio
- RAM ≥ 4 GB, CPU ≥ 2

### Установка

```bash
cd scanner
python -m pip install -r requirements.txt
python -m spacy download ru_core_news_sm en_core_web_sm
Windows: Tesseract — отдельно, инструкция.

3. Конфигурация
Файл: scanner/config/scanner_config.json

Основные параметры:

json
{
  "scanner": {
    "manager_url": "http://localhost:8000",
    "heartbeat_interval": 30,
    "max_file_size_mb": 50,
    "extensions": ["txt", "pdf", "docx", "xlsx", "png", "jpg", "jpeg"],
    "recursive": true
  }
}
Override через ENV:

MANAGER_URL — URL Manager.

LOG_LEVEL — уровень логирования.

## 4. ENV-переменные

| Переменная | Обязательна | Назначение |
|------------|-------------|------------|
| `FINDINGS_ENCRYPTION_KEY` | ✅ | AES-256-GCM ключ (base64, 32 байта) |
| `FINDINGS_HMAC_KEY` | ✅ | HMAC-SHA256 ключ (base64, ≥32 байта) |
| `FINDINGS_KEY_ID` | ⚠️ Рекомендуется | ID ключа (напр. `key-2026-09`) |
| `MANAGER_URL` | ❌ | URL Manager (override config) |
| `LOG_LEVEL` | ❌ | Уровень логов (DEBUG/INFO/WARNING) |
| `DCAP_ALLOW_LEGACY_SCANNER` | ❌ | Только для dev — разрешает запуск без ключей |
| `S3_ACCESS_KEY` | Для S3-ресурсов | Access key MinIO/S3 (политика TASK-018) |
| `S3_SECRET_KEY` | Для S3-ресурсов | Secret key MinIO/S3 (политика TASK-018) |
| `S3_DEFAULT_ENDPOINT` | ❌ | Дефолтный endpoint (вариант B: без query и без ENV → 400) |

⚠️ `FINDINGS_*` должны быть ИДЕНТИЧНЫ ключам Manager. Иначе Manager не расшифрует `match_text`.

⚠️ `S3_DEFAULT_ENDPOINT` нужен на **хосте Manager** (дефолт при создании ресурса),
`S3_ACCESS_KEY` / `S3_SECRET_KEY` — на **хосте сканера** (политика TASK-018).
Не путать с секцией «S3/MinIO аудит-агент» в `.env.example` — это другой процесс.

5. Ключи Findings (обязательно)
С v3.13.9 (после фикса BUG-057) Scanner НЕ СТАРТУЕТ без ключей.

Почему: без ключей Scanner отправляет PII в открытом виде в Manager — нарушение модели безопасности (см. 05-security.md §3.2).

Получить ключи у администратора Manager
Значения — из secrets/ на Manager-хосте:

secrets/findings_encryption_key → FINDINGS_ENCRYPTION_KEY

secrets/findings_hmac_key → FINDINGS_HMAC_KEY

secrets/findings_key_id → FINDINGS_KEY_ID

Передача — только через защищённый канал (SSH, Ansible Vault).

Передача через ENV
Linux (systemd)
/etc/systemd/system/dcap-scanner.service:

ini
[Unit]
Description=DCAP Scanner
After=network.target

[Service]
Type=simple
User=dcap
WorkingDirectory=/opt/dcap
EnvironmentFile=/etc/dcap/scanner.env
ExecStart=/usr/bin/python -X utf8 /opt/dcap/run_scanner.py /opt/dcap/scanner/config/scanner_config.json
Restart=on-failure

[Install]
WantedBy=multi-user.target
/etc/dcap/scanner.env (chmod 600, owner dcap):

ini
FINDINGS_ENCRYPTION_KEY=<base64>
FINDINGS_HMAC_KEY=<base64>
FINDINGS_KEY_ID=key-2026-09
MANAGER_URL=http://dcap-manager.corp:8000
LOG_LEVEL=INFO
Запуск:

bash
sudo systemctl daemon-reload
sudo systemctl enable --now dcap-scanner
Windows (NSSM)
powershell
nssm install DCAPScanner "C:\Python311\python.exe" "-X utf8 C:\dcap\run_scanner.py C:\dcap\scanner\config\scanner_config.json"
nssm set DCAPScanner AppEnvironmentExtra `
    "FINDINGS_ENCRYPTION_KEY=<base64>" `
    "FINDINGS_HMAC_KEY=<base64>" `
    "FINDINGS_KEY_ID=key-2026-09" `
    "MANAGER_URL=http://dcap-manager.corp:8000"
nssm start DCAPScanner
Windows (ручной запуск, dev)
powershell
$env:FINDINGS_ENCRYPTION_KEY = (Get-Content secrets\findings_encryption_key -Raw).Trim()
$env:FINDINGS_HMAC_KEY       = (Get-Content secrets\findings_hmac_key -Raw).Trim()
$env:FINDINGS_KEY_ID         = (Get-Content secrets\findings_key_id -Raw).Trim()
python -X utf8 run_scanner.py scanner/config/scanner_config.json
Проверка ключей
bash
python -c "
from scanner.src.encryption import get_encryption
e = get_encryption(fail_if_missing=True)
print('key_id:', e.key_id)
print('key len:', len(e.aes._key))
"
Ожидаем: key_id совпадает с Manager, key len: 32.

Fail-fast и legacy-режим
По умолчанию (DCAP_ALLOW_LEGACY_SCANNER не задан или false):

text
RuntimeError: FINDINGS_ENCRYPTION_KEY/FINDINGS_HMAC_KEY not set.
Scanner cannot start without encryption keys.
Legacy-режим (только dev):

bash
export DCAP_ALLOW_LEGACY_SCANNER=true   # ⚠️ PLAINTEXT УХОДИТ В MANAGER!
В production — категорически запрещено.

Полная процедура ключей
См. 05-security.md §3 — включая:

Инвентаризация сканеров (§3.7).

Ротация (§3.8).

Компрометация (§3.9).

Troubleshooting (§3.10).

6. Запуск
Порядок: сначала Manager (docker compose up -d), потом Scanner.

bash
# Linux
sudo systemctl start dcap-scanner

# Windows (служба)
Start-Service DCAPScanner

# Ручной запуск (dev)
python -X utf8 run_scanner.py scanner/config/scanner_config.json
7. Интеграция с Manager
Процесс:

Scanner регистрируется в Manager (POST /api/scanner/register).

Каждые 30 сек — heartbeat (POST /api/scanner/heartbeat).

Забирает задание из очереди (GET /api/scanner/tasks/pending).

Сканирует путь, шифрует находки на хосте.

Отправляет результаты (POST /api/scanner/tasks/{id}/results).

При недоступности Manager — сохраняет в scanner/data/offline/, досылает позже.

FP-фильтр: перед отправкой Scanner батчем проверяет fingerprints (POST /api/findings/check-fingerprints) — FP-находки не пересоздаются.

Батчинг: находки отправляются батчами по 500 (BUG-035 fix).

### Модель доступа к scanner-API (с v3.13.10)

Сканер и его machine-API работают **без JWT** (агент не хранит пользовательские учётки), но
middleware Manager'а теперь **всегда пытается извлечь JWT** из запроса на `/api/scanner/*`,
прежде чем пропустить его (BUG-048b). Итоговая модель доступа:

| Эндпоинт | Без JWT | С JWT (admin) | С JWT (viewer) |
|----------|---------|---------------|----------------|
| `POST /api/scanner/register` | 200 (machine) | 200 | 200 |
| `POST /api/scanner/heartbeat` | 200/400/404 (machine) | 200/400/404 | 200/400/404 |
| `GET /api/scanner` (список) | 200 (machine) | 200 | 200 |
| `GET /api/scanner/{id}`, `/ping` | 200/404 (machine) | 200/404 | 200/404 |
| `DELETE /api/scanner/{id}` | 401 | 200/404 (require_admin) | **403** |

Некорректный JWT (garbage) на любом записи → 401. `DELETE /api/scanner/{id}` — единственный
scanner-эндпоинт с ролью: только `admin`; viewer получает 403, не-аутентифицированный — 401.
Удаление сканера из WebUI/API идёт именно через этот эндпоинт.

## 8. S3/MinIO-сканирование

> **С v3.13.31 (BACKLOG-097).** Сканер умеет сканировать S3-совместимые
> хранилища (MinIO, AWS S3, Wasabi и др.) построчно — так же, как файловую
> систему. Коннектор: `scanner/connectors/s3_line_connector.py`.

### 8.1. Как работает

- **Секреты — только ENV на хосте сканера:** `S3_ACCESS_KEY` / `S3_SECRET_KEY`.
  В форму WebUI и в payload задачи секреты не попадают (политика TASK-018).
- **Endpoint/bucket/prefix/secure/use_path_style/region** приходят в payload
  задачи от Manager (`scan_config.connector.s3`); регистрируются при создании
  ресурса: `POST /api/resources?type=s3&path=s3://bucket/prefix`.
- **Endpoint** (вариант B): если не задан в query при создании ресурса и не
  выставлен `S3_DEFAULT_ENDPOINT` на Manager-хосте → 400.
- **Формат пути:** `s3://bucket[/prefix]` (схема также `minio://`).
- **Bucket — из `scan_config.connector.s3.bucket`** (Manager кладёт в payload
  задачи при создании ресурса). Путь `s3://bucket/prefix/` в задании
  используется **только как суффикс префикса** (`prefix/`); bucket в path
  игнорируется — контракт ресурса фиксирует bucket на момент создания.
- **Рекурсия — всегда:** объекты обходятся по всему поддереву prefix
  (S3 — плоское хранилище, `list_objects_v2(Prefix=...)` возвращает всё
  поддерево). Опции `recursive=false` для S3 нет намеренно — чтобы не
  пропустить вложенные объекты при ошибке конфигурации.
- **Streaming:** объекты читаются по чанкам (`Body.iter_chunks`, 1 МБ),
  а не целиком в память.
- **Документы/изображения** — скачиваются во временный файл, извлекаются
  через `DocumentExtractor` (PDF/Office — текст; изображения — OCR).
- **Кодировки:** UTF-8 → CP1251 → UTF-8 с отбрасыванием невалидных байт
  (BUG-136, фикс v3.13.31).

### 8.2. Создание S3-ресурса

Через WebUI: **Ресурсы → Добавить ресурс → Тип: S3**, заполнить `path`
(`s3://bucket/prefix`), опционально `endpoint`, `secure`, `use_path_style`,
`region`.

Через API:

```bash
curl -X POST "http://localhost:8000/api/resources?path=s3://bucket/prefix&type=s3" \
     -H "Authorization: Bearer <TOKEN>"
```

- `endpoint` (`host:port`) — если не задан, берётся `S3_DEFAULT_ENDPOINT` из ENV
  Manager'а; если нет обоих — 400 `endpoint is required for S3/MinIO resources`.
- `secure=false` (дефолт) — HTTP; `secure=true` — HTTPS.
- `use_path_style=true` (дефолт) — адресация `<endpoint>/<bucket>/<key>`
  (нужно для MinIO и IP-эндпоинтов AWS).
- `region` — дефолт `us-east-1`.

### 8.3. Находки

- `file_path` в findings = `s3://bucket/key` (не локальный путь).
- `catalog_entries.path` = `s3://bucket/prefix` (без `//`, без `s3:/bucket`).
- Fingerprint (дедупликация) считается от `s3://bucket/key|line|match|type` —
  стабилен между сканами, если ключ не меняется.
- Находки шифруются на хосте сканера и маскируются Manager'ом — как для ФС.

### 8.4. Ограничения

| Ограничение | Описание |
|-------------|----------|
| `secure=false` = `verify=False` | При HTTP-endpoint сертификат не проверяется (TEST-NOTE-6.11). Для production — `secure=true`. |
| Секреты — per-host, не per-task | Разные credentials на разные S3 — отдельные инстансы сканера. |
| Параллелизм — последовательный | `S3LineConnector.scan_path` обрабатывает объекты по одному. `max_parallel_files > 1` — v3.1.0. |
| `s3_connector.py` (ISourceConnector) | Существует отдельно (для Orchestrator), сканером не используется. |
| Все bucket'ы одной задачей | Не поддерживается — на каждый bucket создаётся отдельный Resource. |

### 8.5. Масштабирование

Подробно — в отдельном дне документации (53.4). Кратко: один инстанс сканера =
одна задача за раз. Несколько bucket'ов — несколько Resource, сканер
обработает их последовательно. Для параллелизма — N инстансов сканера
(Manager разводит задачи между ними через `/api/scanner/tasks/pending`).

## 9. Параллелизм ФС (v3.14.11)

Файлы внутри одной задачи обрабатываются пулом исполнителей — секция
`performance` в `scanner/config/scanner_config.json`:

```json
{
  "performance": {
    "executor": "process",
    "max_workers": 4,
    "chunk_size": 100,
    "max_parallel_files": 8
  }
}
```

| Параметр | Значение | Смысл |
|----------|----------|-------|
| `executor` | `process` (по умолчанию) / `thread` | `ProcessPoolExecutor` — реальный параллелизм без GIL; `thread` — fallback (например, если запуск процессов запрещён политикой) |
| `max_workers` | 4 | Число процессов/потоков-исполнителей. Не больше числа физических ядер |
| `chunk_size` | 100 | Размер окна задач «в полёте» (bounded submit) |
| `max_parallel_files` | 8 | Верхний порог параллелизма (legacy, используется как fallback) |

**Память.** spaCy-модели в каждом процессе свои: на Windows (spawn) —
≈ 0.5 ГБ RSS на процесс, дошедший до PII-файла; на Linux (fork) модели
разделяются copy-on-write. Модели грузятся **лениво** — процесс, не
встретивший PII-файл, остаётся лёгким. Если RAM мало — уменьшить
`max_workers` (например, до 2).

**Ctrl+C** — graceful shutdown: уже собранные находки не теряются,
незапущенные задачи отменяются.

**Логи** показывают выбранный режим:

```text
[FS] ProcessPoolExecutor: 4 процессов, chunk=100
[FS] ThreadPoolExecutor: 8 потоков
[FS] Классификаторы не сериализуются — process-режим невозможен, thread
```

## 10. Troubleshooting
| Симптом | Причина | Fix |
|---------|---------|-----|
| `FINDINGS_ENCRYPTION_KEY not set` | Ключи не заданы | Задать ENV (§5) |
| `SCANNER IN LEGACY MODE` в логах | `DCAP_ALLOW_LEGACY_SCANNER=true` | Убрать флаг в prod |
| Manager не расшифровывает `match_text` | Ключ Scanner ≠ Manager | Сверить base64, сверить `key_id` |
| Scanner не регистрируется | Manager недоступен | `curl http://localhost:8000/api/health` |
| Heartbeat timeout | `STALE_THRESHOLD_MINUTES` < 2 | Проверить `heartbeat_interval` |
| Задание «зависло» в `running` | Scanner упал | Перезапустить Scanner; задача станет `failed` через 2 мин |
| S3-задача failed с «No files found» | `_connector is None` или `source_type` не распознан | Проверить логи сканера: должно быть `Connector created: source_type=s3` |
| `S3LineConnector: задайте S3_ACCESS_KEY / S3_SECRET_KEY в ENV` | Секреты не заданы на хосте сканера | Задать ENV (§4) |
| `endpoint is required for S3/MinIO resources` при создании ресурса | Не задан `endpoint` в query и не выставлен `S3_DEFAULT_ENDPOINT` | Задать `endpoint` в форме или ENV на Manager-хосте |
| `ClientError: NoSuchBucket` | Bucket не существует или неверный endpoint | Проверить `mc ls <alias>/<bucket>` |
| `secure=False` — HTTPS-проверка сертификата отключена | Endpoint по HTTP, `secure=false` | Ожидаемо для MinIO dev; для production — `secure=true` |
| Кириллица в S3-объектах отображается мусором | Объект в не-UTF8 кодировке | С v3.13.31 поддерживается cp1251 (BUG-136 fix) |

**Логи:**

```bash
tail -f logs/scanner.log
```

Метрики: http://localhost:9101/metrics (Prometheus).

### 📚 См. также

- `05-security.md` — безопасность (ключи Findings, ENV)
- `docs/deployment.md` — развёртывание
- `docs/monitoring.md` — мониторинг
- `ARCHITECTURE.md` — архитектура Scanner (раздел S3/MinIO-коннектор)

---

**Последнее обновление:** 04.10.2026
**Версия:** v3.13.32
