markdown
# PROJECT_CONTEXT.md — DCAP System
**Обновлено:** 2026-07-17
**Версия:** v2.0.0-alpha
**Статус:** 🚧 Разработка модуля управления доступом (Дни 9-15)

---

## 🏗️ АРХИТЕКТУРА ПРОЕКТА

### Компоненты
dcap-system/
├── manager/
│ └── src/
│ ├── main.py # FastAPI :8000
│ ├── api/
│ │ ├── resources.py # /api/resources ✅
│ │ ├── tasks.py # /api/tasks ✅
│ │ ├── findings.py # /api/findings ✅
│ │ ├── catalog.py # /api/catalog ✅
│ │ ├── scanner.py # /api/scanner ✅
│ │ └── permissions.py # 🚧 (День 13)
│ ├── connectors/
│ │ └── permissions/ # 🚧 (День 10)
│ │ ├── base.py
│ │ ├── local.py
│ │ ├── ad.py # заглушка для будущего
│ │ └── factory.py
│ ├── services/
│ │ └── access_service.py # 🚧 (День 11-12)
│ └── db/
│ ├── models.py # ✅ Базовые модели
│ └── session.py # ✅
├── scanner/
│ └── src/
│ ├── managed_scanner.py # ✅ REST клиент
│ ├── core/
│ │ └── orchestrator.py # ✅
│ └── classifiers/ # ✅ PII, Credentials, Code
├── webui/
│ └── static/
│ ├── index.html # ✅
│ ├── css/style.css # ✅
│ └── js/app.js # ✅
└── test_files/ # Тестовые данные

text

---

## 📋 ВЕРСИИ И СТАТУС

| Версия | Статус | Описание |
|--------|--------|----------|
| **v1.0.0** | ✅ **ГОТОВА** | Базовая DCAP (обнаружение + классификация + каталог) |
| **v2.0.0-alpha** | 🚧 **В РАЗРАБОТКЕ** | Добавление модуля управления доступом (Дни 9-15) |
| **v2.0.0-beta** | ⚪ ПЛАНИРУЕТСЯ | Добавление аудита и журналирования (Дни 16-22) |
| **v2.1.0** | ⚪ ПЛАНИРУЕТСЯ | Распределенная система (Дни 23-34) |
| **v3.0.0** | ⚪ ПЛАНИРУЕТСЯ | Промышленная DCAP (Дни 35-49) |

---

## 🗄️ ТЕКУЩИЕ МОДЕЛИ БД

### Существующие таблицы

| Таблица | Назначение | Статус |
|---------|-----------|--------|
| `resources` | Источники данных | ✅ |
| `scanners` | Зарегистрированные сканеры | ✅ |
| `scan_tasks` | Задания на сканирование | ✅ |
| `findings` | Находки (PII, Credentials, Code) | ✅ |
| `catalog_entries` | Каталог папок с метками | ✅ |
| `failed_files` | Файлы с ошибками | ✅ |
| `schedules` | Расписания сканирования | ✅ |

### Ключевые модели (актуальные)

```python
# manager/src/db/models.py

class Resource(Base):
    __tablename__ = "resources"
    id = Column(Integer, primary_key=True)
    path = Column(String(500), nullable=False, unique=True)
    type = Column(String(50), default="FILESYSTEM")
    status = Column(String(20), default="ACTIVE")
    last_scanned_at = Column(DateTime, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Конфиг сканирования
    scan_config = Column(JSON, nullable=True)
    scan_interval = Column(Integer, default=3600)
    schedule_enabled = Column(Boolean, default=False)
    cron_expression = Column(String(100), nullable=True)
    
    # НУЖНО ДОБАВИТЬ (День 9):
    # owner = Column(String(200), nullable=True)
    # owner_sid = Column(String(100), nullable=True)
    # permissions = Column(JSON, default={})
    # permission_last_synced = Column(DateTime, nullable=True)
    # is_sensitive = Column(Boolean, default=False)
    # classification_level = Column(String(20), default="public")
    # permission_source = Column(String(50), default="local")
    # domain = Column(String(100), nullable=True)

class Scanner(Base):
    __tablename__ = "scanners"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    status = Column(String(20), default="offline")
    last_heartbeat = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    hostname = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    scan_interval = Column(Integer, default=10)

class ScanTask(Base):
    __tablename__ = "scan_tasks"
    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"))
    scanner_id = Column(Integer, ForeignKey("scanners.id"), nullable=True)
    source_path = Column(String(500), nullable=False)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    files_scanned = Column(Integer, default=0)
    files_failed = Column(Integer, default=0)
    findings_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("scan_tasks.id"))
    resource_id = Column(Integer, ForeignKey("resources.id"))
    file_path = Column(String(500), nullable=False)
    line_number = Column(Integer, default=0)
    category = Column(String(50), nullable=False)
    subcategory = Column(String(50), nullable=True)
    value = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    context = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CatalogEntry(Base):
    __tablename__ = "catalog_entries"
    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"))
    task_id = Column(Integer, ForeignKey("scan_tasks.id"), nullable=True)
    path = Column(String(500), nullable=False, unique=True, index=True)
    entry_metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
🔌 ИНТЕРФЕЙСЫ
REST API (Manager :8000)
Основные эндпоинты (✅ ГОТОВЫ)
Метод	Эндпоинт	Назначение
GET	/api/resources	Список ресурсов
POST	/api/resources	Создать ресурс
DELETE	/api/resources/{id}	Удалить ресурс
POST	/api/resources/{id}/scan	Запустить сканирование
GET	/api/resources/{id}/config	Получить конфиг
PUT	/api/resources/{id}/config	Обновить конфиг
GET	/api/tasks	Список заданий
GET	/api/findings	Список находок
GET	/api/catalog	Каталог папок
GET	/api/catalog/tree	Дерево папок
Scanner API (✅ ГОТОВЫ)
Метод	Эндпоинт	Назначение
POST	/api/scanner/register	Регистрация сканера
POST	/api/scanner/heartbeat	Heartbeat
GET	/api/scanner/tasks/pending	Получить задание
POST	/api/scanner/tasks/{id}/results	Отправить результаты
Permissions API (🚧 В РАЗРАБОТКЕ — День 13)
Метод	Эндпоинт	Назначение
GET	/api/permissions/resources/{id}	Получить права доступа
POST	/api/permissions/sync	Синхронизировать права
GET	/api/permissions/resources/{id}/effective	Эффективные права
GET	/api/permissions/resources/{id}/excessive	Избыточные права
GET	/api/permissions/resources/{id}/inheritance	Анализ наследования
GET	/api/permissions/resources/{id}/report	Полный отчет
GET	/api/permissions/alerts	Алерты по доступам
PUT	/api/permissions/alerts/{id}	Обновить статус алерта
🎯 ТЕКУЩАЯ ЗАДАЧА (ДНИ 9-15)
Цель
Реализовать модуль управления доступом (Access Management) для DCAP-системы.

Объем работ
День	Задача	Описание
День 9	Модель данных	AccessEntry, AccessAlert, расширение Resource
День 10	Коннектор прав	LocalPermissionCollector (icacls, net user)
День 11-12	Сервис	AccessService (синхронизация, анализ, алерты)
День 13	API	Эндпоинты /api/permissions/*
День 14	WebUI	Страница "Управление доступом"
День 15	Тестирование	Проверка всех сценариев
⚠️ ВАЖНЫЕ ОГРАНИЧЕНИЯ
Нет Active Directory — разработка ведется на Windows 10 без AD

Архитектура должна быть расширяемой — возможность добавить AD в будущем

Паттерн Strategy — для коллекторов прав доступа

Локальные пользователи/группы — через net user и net localgroup