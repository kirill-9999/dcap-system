# Справка для архитектора: S3/MinIO-коннектор сканера — мёртвый код

**Дата:** 03.10.2026
**Предмет:** `scanner/connectors/s3_connector.py` — сканирование бакетов MinIO/S3
**Вывод:** код **не зачищен** и цел, но **никогда не был подключён** — с Дня 8. Работающего сканирования бакетов нет.
**Срочность:** 🟡 средняя (заявленная в README возможность не работает; ПИИ в S3 не сканируется)

---

## 1. Краткий ответ

Файл на месте (247 строк, в git), вся обвязка под него тоже есть — `SourceType.S3/MINIO`, ветки в `state_manager` и `orchestrator`, `hash_s3_object`. Но:

- `S3Connector` **не импортируется и не инстанцируется нигде** в репозитории;
- фабрики коннекторов **нет** — `managed_scanner.py` жёстко создаёт `FilesystemConnector`;
- секции `connectors.s3` **нет ни в одном конфиге**;
- `boto3` **не входит** в `scanner/requirements.txt`.

Это не регресс и не результат чистки Блока 6 — см. §4.

---

## 2. Что именно есть на месте

| Файл / строка | Состояние | Комментарий |
|----------------|-----------|-------------|
| `scanner/connectors/s3_connector.py` | ✅ 247 строк | Полная реализация: `configure`, `test_connection`, `list_files`, `get_content` |
| `scanner/connectors/base.py:24,28` | ✅ | `list_files` / `get_content` — единственные абстрактные методы, **оба реализованы** |
| `scanner/core/base.py:28,29,51` | ✅ | `SourceType.S3`, `SourceType.MINIO`, поля `bucket`/`key`/`endpoint` в `FileContext` |
| `scanner/core/state_manager.py:109` | ✅ | Отдельная ветка: в `ProcessedFileInfo` пишутся `bucket` и `key` |
| `scanner/core/orchestrator.py:587` | ✅ | Отображение источника как `s3://{source_path}` |
| `scanner/utils/file_hasher.py:37` | ✅ | `hash_s3_object(client, bucket, key)` |
| `scanner/README.md:56,102` | ✅ | `s3_connector` заявлен в дереве и таблице коннекторов |

**Вывод:** заготовка качественная, интерфейс соблюдён, интеграционные точки в ядре подготовлены. Не хватает только «включателя».

---

## 3. Чего не хватает (4 точки)

### 3.1 Фабрики коннекторов — нет

`orchestrator.configure()` (строка 365) принимает готовый объект, выбор коннектора по конфигу не предусмотрен:

```python
def configure(self, connector: ISourceConnector, configure_connector: bool = False) -> None:
    self.connector = connector
    connector_config = self.config.get("connectors", {}).get(connector.connector_type.value, {})
```

Обратите внимание: ветка `self.config.get("connectors", {})` **уже написана** под словарь коннекторов, но словаря `connectors` в конфигах нет. Заготовка рассчитана на выбор по ключу, реализации выбора нет.

### 3.2 `managed_scanner.py` — жёсткий `FilesystemConnector`

| Строка | Код |
|--------|-----|
| 1126 | `connector = FileSystemConnector()` |
| 729 | `self._connector = FilesystemConnector(connector_cfg)` |

Оба места — единственная точка, где сканер решает, что сканировать. Тип источника из задания Manager не разбирается.

### 3.3 Конфиг сканера — секции нет

В `scanner/config/scanner_config.json` нет ни `connectors`, ни `s3`, ни `minio`. `_get_connector_config()` (`managed_scanner.py:597`) формирует плоский словарь только под файловый коннектор:

```
extensions, max_file_size_mb, recursive, skip_dirs,
buffer_size, max_text_chars, context_lines, max_parallel_files
```

Ни `endpoint`, ни `bucket`, ни ключей доступа в модели конфига нет — то есть передать S3-параметры **нечем** без правки `config_loader`.

### 3.4 Зависимости — `boto3` не установлен

`boto3` отсутствует в `scanner/requirements.txt` (присутствует только в `audit-agent-s3/requirements.txt`). Код это учитывает мягко:

```python
try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
...
if not BOTO3_AVAILABLE:
    raise ImportError("boto3 не установлен. Установите: pip install boto3")
```

То есть при включении коннектора сканер упадёт с `ImportError`, если `boto3` не добавлен.

---

## 4. Это не мы зачистили

`git log -S "S3Connector" --all` — класс **никогда не был вызываемым**:

| Коммит | Что сделал |
|--------|-----------|
| `0d44446` День 8 | Создал `s3_connector.py` |
| `4e2fcec` День 9, `ee6561f`, `18f60e1` День 13 | Правки в других местах (S3Connector не вызывался) |
| `76c94e5`, `cbaf9d5` | Переименования |
| `80c3728` Блок 1 (17.09) | Последняя правка самого файла: 9 строк |

Ни в одном коммите нет `S3Connector(...)` или `from connectors.s3_connector import ...`. Рабочее дерево по `scanner/` чистое — локальных правок нет.

**Вывод:** это заготовка с Дня 8, которая никогда не включалась в конвейер. Блок 6 её не трогал.

---

## 5. Дополнительные находки (для решения при включении)

| # | Находка | Место | Комментарий |
|---|---------|-------|-------------|
| 1 | `verify=False` при `secure=false` | `s3_connector.py:110` | Для HTTP-MinIO нормально, но для HTTPS-совместимых хранилищ отключает проверку сертификата |
| 2 | Секреты в конфиге | `s3_connector.py:50-56` | `access_key`/`secret_key` читаются из конфига. Следует читать из ENV/SecretsManager (`manager/src/core/secrets.py` уже есть) |
| 3 | `get_content` читает объект целиком | `s3_connector.py:237` | В память, без потоковой буферизации. Файловый коннектор буферизует по 1 МБ (`buffer_size`). Для больших объектов MinIO — риск OOM |
| 4 | `print()` вместо логгера | по всему файлу | Остальной сканер использует `logging` |
| 5 | Не проверяется `ContentLength` до чтения | `s3_connector.py:232` | Фильтр по `max_file_size_mb` есть в `list_files` (строка 196), но объект может измениться между листингом и чтением |
| 6 | Не используется `hash_s3_object` | `file_hasher.py:37` | Функция объявлена, но `get_content` хэш не считает — дедупликация по хэшу для S3 не работает |
| 7 | Нет `recursive` в логике | `s3_connector.py:58` | Параметр читается, но плоскость бакета всегда обходится целиком (`list_objects_v2` без `Delimiter`) |
| 8 | Пустой `__init__.py` | `scanner/connectors/__init__.py` | Коннекторы не реэкспортируются |

---

## 6. Что нужно для включения (оценка)

| # | Задача | Файл | Оценка |
|---|--------|------|--------|
| 1 | Фабрика коннекторов (реестр по `connector_type`) | `scanner/core/` — новое | 40 строк |
| 2 | Модель конфига S3 + секция `connectors.s3` | `scanner/config_loader.py`, `scanner_config.json` | 30 строк |
| 3 | Выбор коннектора по заданию | `managed_scanner.py:1126`, `:729` | 15 строк |
| 4 | `boto3` в зависимости | `scanner/requirements.txt` | 1 строка |
| 5 | Секреты через ENV вместо конфига | `s3_connector.py:50-56` | 15 строк |
| 6 | Логгер вместо `print` | `s3_connector.py` | 20 строк |
| 7 | Тест на `dcap-audit-logs` | `tests/` | 1 тест |

**Итого: ~2-3 часа** вместе с тестом на нашем MinIO (бакет `dcap-audit-logs` уже поднят и наполнен — можно проверять сразу).

Опционально (после включения): стриминг вместо `read()` целиком, интеграция `hash_s3_object`, поддержка `recursive`.

---

## 7. Решение за архитектором

| Вариант | Суть |
|---------|------|
| **А. Включить** (~2-3 ч) | Реализовать п.6, закрыть заявленную в README возможность, ПИИ в MinIO-бакетах начнёт сканироваться |
| **Б. Отключить явно** (~15 мин) | Удалить `s3_connector.py` + мёртвые ветки в `state_manager`/`orchestrator`/`base.py`, убрать строку из README. Честнее, чем «работающая» неиспользуемая возможность |
| **В. Отложить** | Добавить в бэклог как `BACKLOG-1xx`, убрать `s3_connector` из README, чтобы не вводить в заблуждение |

**Рекомендация: А** — заготовка качественная, зависимости и бакет для теста уже есть, работа в основном организационная (выбор коннектора), а не архитектурная.

---

## 8. Проверка для архитектора

```powershell
# Код на месте
git log --oneline --follow -- scanner/connectors/s3_connector.py
Get-Content scanner\connectors\s3_connector.py | Measure-Object -Line

# Нигде не вызывается
Select-String -Path (Get-ChildItem -Recurse -Include *.py -Path .).FullName -Pattern "S3Connector"

# Точки, которые надо менять
Select-String -Path scanner\src\managed_scanner.py -Pattern "FilesystemConnector\("
Select-String -Path scanner\config\*.json -Pattern "connectors|s3"

# boto3 нет в зависимостях сканера
Select-String -Path scanner\requirements.txt -Pattern "boto3"
```
