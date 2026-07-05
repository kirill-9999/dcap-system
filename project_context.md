# PROJECT_CONTEXT.md — DCAP System
**Обновлено:** 2026-07-05
**Ветка:** master (feature/debug-chain смержена)

---

## ТЕКУЩЕЕ СОСТОЯНИЕ

Цепочка **Scanner → Manager → БД** отлажена и работает стабильно.
Следующий этап: **WebUI**.

---

## ЧТО РАБОТАЕТ

### Запуск
```
# Терминал 1 — Manager
D:\dev\anaconda3\python -m manager.src.main

# Терминал 2 — Scanner
set TESSERACT_PATH=D:\dev\Tesseract-OCR\tesseract.exe
D:\dev\anaconda3\python create_task.sql.py
D:\dev\anaconda3\python run_scanner.py
```

> **Важно:** системный `python` не имеет зависимостей. Всегда использовать `D:\dev\anaconda3\python`.

### Цепочка
- Manager поднимает gRPC (порт 50051) и REST (порт 8000)
- Scanner регистрируется, получает задачу через `GetTask`, сканирует, отправляет находки через `ReportBatch`
- БД: `manager/src/db/dcap.db` (SQLite)

### Сканирование test_files
- 17 файлов, 12 с находками, ~233 находки
- Классификаторы: PII (Presidio + spaCy), Credentials, Code
- OCR (Tesseract): работает для PNG/JPG/DOCX с изображениями
- Русский язык OCR: нужно скачать `rus.traineddata` → `D:\dev\Tesseract-OCR\tessdata\`

### Каталог
Реализован и работает. Логика:
- Папка попадает в каталог если классификатор нашёл в ней что-либо
- Запись: `folder_path` (unique), `classifiers` (JSON list), `first_seen`, `updated_at`
- UPSERT по `folder_path` — при повторном скане перезаписывается
- Несколько сканеров строят общий каталог
- Периодический сброс каждые 30 сек + финальный в `close()`

---

## АРХИТЕКТУРА

```
dcap-system/
├── manager/src/
│   ├── main.py                    # gRPC :50051 + REST :8000
│   ├── db/models.py               # SQLAlchemy модели
│   ├── db/session.py              # SQLite (dcap.db)
│   └── services/manager_service.py # gRPC handlers
├── scanner/src/
│   └── managed_scanner.py         # ManagedScanner + GrpcHandler (каталог)
├── scanner/classifiers/
│   ├── pii_classifier.py          # Presidio + spaCy
│   ├── credentials_classifier.py
│   ├── code_classifier.py
│   └── ocr_worker.py              # Tesseract subprocess
├── scanner/utils/
│   └── ocr_engine.py              # OCR engine
├── create_task.sql.py             # Создать задачу вручную
└── proto/dcap/manager.proto       # gRPC контракт
```

### БД таблицы
| Таблица | Назначение |
|---|---|
| `scanners` | Зарегистрированные сканеры |
| `resources` | Папки/бакеты для сканирования |
| `scan_tasks` | Задания (PENDING→ASSIGNED→COMPLETED) |
| `findings` | Находки (файл, классификатор, значение, уверенность) |
| `catalog_entries` | Каталог папок (folder_path unique, classifiers, updated_at) |
| `failed_files` | Файлы с ошибками обработки |

---

## ИЗВЕСТНЫЕ ПРОБЛЕМЫ

| Проблема | Статус |
|---|---|
| OCR — русский язык | Нужно скачать `rus.traineddata` |
| `findings_count` в `scan_tasks` не обновляется | Мелкий баг, некритично |
| `catalog_entries` = 0 при быстром скане малого числа файлов | Буфер не успевает сброситься, финальный flush работает |
| Фоновые scanner-процессы перехватывают задачи | Всегда убивать `taskkill /F /IM python.exe` перед запуском |

---

## СЛЕДУЮЩИЙ ЭТАП — WebUI

### Цель
Замкнуть цепочку: **WebUI → Manager → Scanner → БД → WebUI**

### Что нужно реализовать
1. Страница ресурсов — список ресурсов, кнопка "Добавить ресурс"
2. Ручной запуск сканирования — кнопка "Сканировать" для ресурса
3. Просмотр заданий — статус, прогресс
4. Просмотр находок — таблица с фильтрацией по файлу/категории
5. Просмотр каталога — папки с метками классификаторов

### REST API Manager (уже есть)
- `GET /health` — статус
- Нужно добавить: `/api/resources`, `/api/tasks`, `/api/findings`, `/api/catalog`

### Технологии WebUI
- Backend: FastAPI (уже используется в Manager)
- Frontend: простой HTML + JS (без фреймворков)
- Файлы: `webui/` или встроить в Manager REST
