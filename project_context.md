# PROJECT_CONTEXT.md — DCAP System
**Обновлено:** 2026-07-16
**Версия:** v2.0.0-alpha
**Статус:** ✅ Базовый функционал готов, начата разработка модуля управления доступом

---

## 🏗️ ТЕКУЩАЯ АРХИТЕКТУРА

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
│ │ └── permissions.py # /api/permissions 🚧 (в разработке)
│ ├── connectors/
│ │ └── permissions/ # 🚧 (в разработке)
│ │ ├── base.py # Абстрактный класс
│ │ ├── local.py # Windows 10 (без AD)
│ │ ├── ad.py # AD (заглушка для будущего)
│ │ └── factory.py # Фабрика коллекторов
│ ├── services/
│ │ ├── manager_service.py # gRPC (УДАЛЕН)
│ │ └── access_service.py # 🚧 (в разработке)
│ └── db/
│ ├── models.py # ✅ Расширены (AccessEntry, AccessAlert)
│ └── session.py # ✅
├── scanner/
│ └── src/
│ ├── managed_scanner.py # ✅ REST клиент
│ ├── core/
│ │ └── orchestrator.py # ✅
│ └── classifiers/ # ✅ PII, Credentials, Code
├── webui/
│ └── static/
│ ├── index.html # ✅ + страница "Управление доступом"
│ ├── css/style.css # ✅
│ └── js/app.js # ✅ + функции для Permissions
└── test_files/ # Тестовые данные

text

---

## 📋 ВЕРСИИ И СТАТУС

| Версия | Статус | Описание |
|--------|--------|----------|
| **v1.0.0** | ✅ **ГОТОВА** | Базовая DCAP (обнаружение + классификация + каталог) |
| **v2.0.0-alpha** | 🚧 **В РАЗРАБОТКЕ** | Добавление модуля управления доступом (Дни 9-15) |
| **v2.0.0-beta** | ⚪ ПЛАНИРУЕТСЯ | Добавление аудита и журналирования (Дни 16-22) |
| **v3.0.0** | ⚪ ПЛАНИРУЕТСЯ | Промышленная DCAP (Shadow Data + Интеграции + Продакшн) |

---

## 🗄️ МОДЕЛЬ ДАННЫХ (ОБНОВЛЕННАЯ)

### Существующие таблицы

| Таблица | Назначение | Статус |
|---------|-----------|--------|
| `resources` | Источники данных | ✅ **РАСШИРЕНА** (owner, permissions, is_sensitive, permission_source) |
| `scanners` | Зарегистрированные сканеры | ✅ |
| `scan_tasks` | Задания на сканирование | ✅ |
| `findings` | Находки (PII, Credentials, Code) | ✅ |
| `catalog_entries` | Каталог папок с метками | ✅ |
| `failed_files` | Файлы с ошибками | ✅ |
| `schedules` | Расписания сканирования | ✅ |

### Новые таблицы (в разработке)

| Таблица | Назначение | Статус |
|---------|-----------|--------|
| `access_entries` | Права доступа к ресурсам | 🚧 |
| `permission_changes` | История изменений прав | 🚧 |
| `access_alerts` | Алерты по доступам | 🚧 |

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
    
    # НОВОЕ: Управление доступом
    owner = Column(String(200), nullable=True)
    owner_sid = Column(String(100), nullable=True)
    permissions = Column(JSON, default={})
    permission_last_synced = Column(DateTime, nullable=True)
    is_sensitive = Column(Boolean, default=False)
    classification_level = Column(String(20), default="public")
    permission_source = Column(String(50), default="local")  # local, ad, custom
    domain = Column(String(100), nullable=True)

class AccessEntry(Base):
    __tablename__ = "access_entries"
    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False, index=True)
    
    # Субъект доступа
    principal_type = Column(String(20), nullable=False)  # user, group, local_user, ad_user, ad_group, system
    principal_name = Column(String(200), nullable=False)
    principal_sid = Column(String(100), nullable=True)
    principal_domain = Column(String(100), nullable=True)
    principal_upn = Column(String(200), nullable=True)
    
    # Права
    permission_type = Column(String(50), nullable=False)
    permission_source = Column(String(50), default="direct")
    
    # Наследование
    inherited_from = Column(String(500), nullable=True)
    is_inherited = Column(Boolean, default=False)
    
    # Аудит
    granted_at = Column(DateTime, default=datetime.utcnow)
    granted_by = Column(String(200), nullable=True)
    last_verified_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    collector_source = Column(String(50), default="local")  # local, ad, custom
    
    resource = relationship("Resource", back_populates="access_entries")

class AccessAlert(Base):
    __tablename__ = "access_alerts"
    id = Column(Integer, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=True)
    
    alert_type = Column(String(50), nullable=False)  # excessive_permissions, orphaned, sensitive_access
    severity = Column(String(20), default="warning")  # critical, warning, info
    principal_name = Column(String(200), nullable=True)
    description = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)
    
    status = Column(String(20), default="open")  # open, acknowledged, resolved, ignored
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(200), nullable=True)
    
    resource = relationship("Resource", back_populates="access_alerts")
🔌 ИНТЕРФЕЙСЫ (АКТУАЛЬНЫЕ)
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
GET	/api/catalog/stats	Статистика каталога
GET	/api/catalog/search	Поиск по каталогу
Scanner API (✅ ГОТОВЫ)
Метод	Эндпоинт	Назначение
POST	/api/scanner/register	Регистрация сканера
POST	/api/scanner/heartbeat	Heartbeat
GET	/api/scanner/tasks/pending	Получить задание
POST	/api/scanner/tasks/{id}/results	Отправить результаты
GET	/api/scanner/tasks/assigned	Активные задания
POST	/api/scanner/tasks/{id}/release	Освободить задание
Permissions API (🚧 В РАЗРАБОТКЕ)
Метод	Эндпоинт	Назначение
GET	/api/permissions/resources/{id}	Получить права доступа
POST	/api/permissions/sync	Синхронизировать права
GET	/api/permissions/resources/{id}/effective	Эффективные права
GET	/api/permissions/resources/{id}/excessive	Избыточные права
GET	/api/permissions/resources/{id}/inheritance	Анализ наследования
GET	/api/permissions/resources/{id}/report	Полный отчет
GET	/api/permissions/alerts	Алерты по доступам
PUT	/api/permissions/alerts/{id}	Обновить статус алерта
GET	/api/permissions/collectors	Список коллекторов
🔧 КОННЕКТОРЫ ПРАВ ДОСТУПА (🚧 В РАЗРАБОТКЕ)
Архитектура (Strategy Pattern)
text
PermissionCollector (abstract)
├── LocalPermissionCollector   ✅ Windows 10 (без AD) — СЕЙЧАС
├── ADPermissionCollector      ⚪ Active Directory — ЗАГЛУШКА
└── CustomPermissionCollector  ⚪ Пользовательский — БУДУЩЕЕ
LocalPermissionCollector
Возможности:

Сбор NTFS прав через icacls

Получение локальных пользователей через net user

Получение локальных групп через net localgroup

Анализ наследования прав

Ограничения:

Только Windows 10 (без AD)

Не видит права через AD группы

ADPermissionCollector (заглушка)
Планируемые возможности:

Интеграция с Active Directory через LDAP/ADSI

Получение групп пользователей

Анализ эффективных прав с учетом AD

Синхронизация пользователей/групп

🖥️ WEBUI (АКТУАЛЬНЫЙ)
Страницы
Страница	Статус	Функционал
📁 Ресурсы	✅	CRUD, настройка конфига, запуск сканирования
🔍 Находки	✅	Список находок, фильтры
📂 Каталог	✅	Дерево папок с находками, поиск
📋 Задания	✅	Список заданий, активные задания
🔐 Управление доступом	🚧	Права доступа, алерты, отчеты
Навигация
text
[📁 Ресурсы] [🔍 Находки] [📂 Каталог] [📋 Задания] [🔐 Доступ]
📊 ТЕКУЩИЙ СТАТУС РАЗРАБОТКИ
Неделя 1-2: Базовый функционал (✅ ЗАВЕРШЕНА)
День	Задача	Статус
День 1	Переход с gRPC на REST	✅
День 2	Исправление сохранения findings	✅
День 3	Регистрация Scanner	✅
День 4	WebUI: находки	✅
День 5	Разделение конфигурации	✅
День 6	Передача catalog_entries	✅
День 7	WebUI: CRUD ресурсов	✅
День 8	WebUI: каталог	✅
Неделя 3: Управление доступом (🚧 В ПРОЦЕССЕ)
День	Задача	Статус
День 9	Модель данных (AccessEntry, AccessAlert)	🚧
День 10	Коннектор (LocalPermissionCollector)	🚧
День 11-12	Сервис (AccessService)	🚧
День 13	API эндпоинты	🚧
День 14	WebUI: управление доступом	🚧
День 15	Тестирование	⚪
Неделя 4: Аудит и журналирование (⚪ ПЛАНИРУЕТСЯ)
День	Задача	Статус
День 16-17	Сбор аудит-логов	⚪
День 18-19	Поведенческий анализ	⚪
День 20-22	Отчеты и WebUI	⚪
Неделя 5-6: Shadow Data + Интеграции + Продакшн (⚪ ПЛАНИРУЕТСЯ)
День	Задача	Статус
День 23-25	Shadow Data Discovery	⚪
День 26-28	Интеграции (AD, DLP, SIEM)	⚪
День 29-30	Тестирование интеграций	⚪
День 31-36	Масштабирование (PostgreSQL, Redis)	⚪
День 37-38	Мониторинг (Prometheus, Grafana)	⚪
День 39-40	Документация и релиз	⚪
📈 ЭВОЛЮЦИЯ ФУНКЦИОНАЛА
text
v1.0.0 (✅)               v2.0.0 (🚧)              v3.0.0 (⚪)
─────────────────────────────────────────────────────────────────────────
│ Обнаружение: 80%   │ Обнаружение: 90%   │ Обнаружение: 95%   │
│ Классификация: 80% │ Классификация: 90% │ Классификация: 95% │
│ Доступ: 20%        │ Доступ: 80%        │ Доступ: 85%        │
│ Аудит: 20%         │ Аудит: 75%         │ Аудит: 80%         │
│ Каталог: 95%       │ Каталог: 95%       │ Каталог: 98%       │
│ Интеграции: 20%    │ Интеграции: 40%    │ Интеграции: 75%    │
│ WebUI: 75%         │ WebUI: 90%         │ WebUI: 95%         │
─────────────────────────────────────────────────────────────────────────
│ Итого: 65%         │ Итого: 80%         │ Итого: 90%+        │
─────────────────────────────────────────────────────────────────────────
🚀 ЗАПУСК
Терминал 1 — Manager
powershell
cd D:\Projects\dcap-system
D:\dev\anaconda3\python -m manager.src.main
REST: http://localhost:8000
Swagger: http://localhost:8000/docs

Терминал 2 — Scanner
powershell
cd D:\Projects\dcap-system
set TESSERACT_PATH=D:\dev\Tesseract-OCR\tesseract.exe
D:\dev\anaconda3\python run_scanner.py
🧪 ТЕСТОВЫЕ ДАННЫЕ
Путь: D:\Projects\dcap-system\test_files

Содержание: Текстовые файлы с PII (email, телефон, паспорт)

⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ (v2.0.0-alpha)
Ограничение	Статус	Решение
Нет AD интеграции	🚧	Заглушка, будет позже
Только Windows 10	✅	Для текущей разработки
SQLite (не PostgreSQL)	⚪	Будет в v3.0.0
Нет аутентификации	⚪	Будет в v3.0.0
📝 ТЕКУЩАЯ ЗАДАЧА (ПРИОРИТЕТ 1)
Дни 9-15: Управление доступом
Цель: Реализовать модуль управления доступом для DCAP-системы.

Объем работ:

Модель данных (AccessEntry, AccessAlert, расширение Resource)

Коннектор для Windows 10 (LocalPermissionCollector)

Сервис управления доступом (AccessService)

API эндпоинты (/api/permissions/*)

WebUI страница "Управление доступом"

Критерии успеха:

icacls работает и парсится корректно

Локальные пользователи/группы определяются

Алерты генерируются для избыточных прав

API возвращает права доступа

WebUI отображает таблицу прав и алерты

Архитектура расширяема для AD

🏗️ АРХИТЕКТУРНОЕ РЕШЕНИЕ: РАСШИРЯЕМОСТЬ
Паттерн: Стратегия (Strategy Pattern)
text
PermissionCollector (abstract)
├── LocalPermissionCollector   ✅ СЕЙЧАС
├── ADPermissionCollector      ⚪ ПОТОМ (заглушка)
└── CustomPermissionCollector  ⚪ БУДУЩЕЕ
Преимущества:

Легко добавить AD без рефакторинга

Можно переключаться между коллекторами

Единый интерфейс для всех источников

✅ ТЕКУЩИЙ ВЕРДИКТ
Статус: 🚧 v2.0.0-alpha в разработке

v1.0.0: ✅ ГОТОВ

Управление доступом: 🚧 В ПРОЦЕССЕ (Дни 9-15)

Аудит: ⚪ ПЛАНИРУЕТСЯ

Продакшн: ⚪ ПЛАНИРУЕТСЯ

Следующий шаг: Завершить Дни 9-15 (Управление доступом) и перейти к тестированию.

Архитектор: ✅ Контекст обновлен
Дата: 2026-07-16
Версия: v2.0.0-alpha

text

---

## 📋 ЧТО ИЗМЕНИЛОСЬ

| Раздел | Изменение |
|--------|-----------|
| **Версия** | v1.0.0 → v2.0.0-alpha |
| **Статус** | ✅ Готов → 🚧 В разработке |
| **Архитектура** | Добавлены connectors/permissions |
| **Модели** | Добавлены AccessEntry, AccessAlert, расширен Resource |
| **API** | Добавлены /api/permissions/* |
| **WebUI** | Добавлена страница "Управление доступом" |
| **План** | Добавлены Дни 9-15 (Управление доступом) |
| **Ограничения** | Указаны текущие ограничения |