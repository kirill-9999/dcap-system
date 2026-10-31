# DCAP Scanner

Тяжёлый агент сканирования: классификация файлов (PII, credentials, code), OCR, управляемый/автономный режим.

## Запуск

```powershell
python run_scanner.py scanner/config/scanner_config.json
```

Сканер ждёт Manager на `:8000`.

## Структура

```
scanner/
├── config/
│   └── scanner_config.json    # Конфигурация
├── state/
│   └── state.json             # Состояние (генерируется)
├── logs/
│   └── scanner.log            # Логи (генерируются)
├── src/
│   ├── managed_scanner.py     # Точка входа
│   ├── config_loader.py       # Загрузка конфига
│   ├── modes/
│   │   ├── base.py            # Базовый режим
│   │   ├── managed.py         # Управляемый (от Manager)
│   │   ├── standalone.py      # Автономный
│   │   └── hybrid.py          # Гибридный
│   └── offline/
│       ├── detector.py        # Детектирование offline
│       ├── queue.py           # Очередь offline
│       ├── storage.py         # Хранилище offline
│       └── sync.py            # Синхронизация
├── core/
│   ├── orchestrator.py        # Оркестрация сканирования
│   ├── dispatcher.py          # Диспетчер файлов
│   ├── state_manager.py       # Менеджер состояния
│   ├── resource_manager.py    # Менеджер ресурсов
│   ├── catalog_manager.py     # Менеджер каталога
│   ├── config_manager.py      # Менеджер конфига
│   ├── memory_manager.py      # Управление памятью
│   ├── adaptive_cache_manager.py # Адаптивный кэш
│   ├── metrics.py             # Метрики
│   └── logger.py              # Логирование
├── classifiers/
│   ├── pii_classifier.py      # PII (Presidio + spaCy)
│   ├── credentials_classifier.py # Пароли, ключи, токены
│   ├── code_classifier.py     # Скрипты, исполняемые модули
│   ├── ocr_worker.py          # OCR (Tesseract)
│   └── model_worker.py        # ML-модели
├── connectors/
│   ├── base.py                # Базовый коннектор
│   ├── filesystem.py          # Файловая система
│   └── s3_connector.py        # S3/MinIO
├── handlers/
│   └── finding_collector.py   # Сбор находок
└── utils/
    ├── ocr_engine.py          # Движок OCR
    ├── ocr_pool.py            # Пул OCR-процессов
    ├── safe_ocr_worker.py     # Безопасный воркер
    ├── file_hasher.py         # Хеширование файлов
    ├── document_extractor.py  # Извлечение текста
    └── performance_monitor.py # Мониторинг производительности
```

## Режимы работы

| Режим | Описание |
|-------|----------|
| managed | Управляется Manager — получает задания, отправляет результаты |
| standalone | Автономный — сканирует по конфигу, без Manager |
| hybrid | Гибридный — работает offline, синхронизирует с Manager |

## Конфигурация

`scanner/config/scanner_config.json`:

| Блок | Описание |
|------|----------|
| `scanner` | Имя, URL manager, интервал сканирования |
| `performance` | Параллелизм, лимиты памяти, таймауты |
| `classifiers` | Включение/выключение классификаторов, пороги |
| `connector` | Пропуск директорий, symlinks, скрытые файлы |
| `logging` | Уровень, файл, ротация |
| `client` | Таймауты HTTP-запросов к Manager |

## Классификаторы

| Классификатор | Что ищет | Зависимости |
|---------------|----------|-------------|
| pii_classifier | Имена, email, телефоны, паспорта, СНИЛС | presidio, spacy |
| credentials_classifier | Пароли, API-ключи, токены, приватные ключи | regex |
| code_classifier | Скрипты, .exe, .dll, .so, библиотеки | regex |

## Коннекторы

| Коннектор | Источник |
|-----------|----------|
| filesystem | Локальная файловая система |
| s3_connector | S3/MinIO |

## Зависимости

Тяжёлые: presidio, spacy, tesseract, openpyxl.
См. `requirements.txt` в корне проекта.
