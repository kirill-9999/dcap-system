# Release Notes — DCAP System v2.0.1

**Дата:** 2026-08-25
**Версия:** v2.0.1
**Статус:** Стабильный релиз

---

## Обзор

DCAP System v2.0.1 — завершение Windows-стека. Система полностью готова к использованию на Windows-платформах для обнаружения и классификации персональных данных, управления доступом и аудита файловой системы.

---

## Что нового в v2.0.1

### 1. WebUI для аудита (День 19)
- Страница «Аудит» с таблицей событий и фильтрами
- Дашборд: блок «Агенты аудита» с живым обновлением
- Вкладка «Сканеры и агенты» — таблица агентов аудита с badges
- API: `GET /api/audit/agents` (список агентов)
- Удаление легаси-файлов, единая точка входа `webui/main.py` на :8001

### 2. Отчеты по аудиту (День 20)
- `POST /api/audit/report/preview` — предпросмотр отчета
- `GET /api/audit/report/export/excel` — экспорт в Excel (openpyxl)
- `GET /api/audit/report/export/pdf` — экспорт в PDF (reportlab)
- Кнопка «Отчет» + модалка с фильтрами по датам, типам, важности

### 3. Интеграционное тестирование (День 21)
- Структура `tests/integration/`: conftest + 5 модулей
- **47/48 тестов пройдено** (1 skipped — нет активного задания)
- Покрытие: Manager API, Scanner, Audit Agent, WebUI, E2E

### 4. Исправления (hotfix)
- SQLite threading: `check_same_thread=False` для многопоточных сервисов
- Относительные пути агента: `base_dir` вместо `Path(__file__)`
- XML-парсинг: namespace strip + bare `<Event>` wrap
- wevtutil colon-syntax: `/f:XML`, `/q:...`, `/c:N`
- WebUI inline-JS: экранирование `\n`/`\x27`

---

## Структура проекта

```
dcap-system/
├── manager/          # FastAPI :8000 (чистое API)
├── scanner/          # агент сканирования (тяжелый)
├── audit-agent/      # легкий агент аудита (Windows)
├── webui/            # каноничный UI :8001
├── tests/            # интеграционные тесты
└── docs/             # документация
```

---

## Как запустить

```powershell
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Инициализировать БД
python init_db.py

# 3. Запустить Manager (API)
python -m uvicorn manager.src.main:app --port 8000

# 4. Запустить WebUI
python run_webui.py

# 5. Запустить Audit Agent (опционально)
cd audit-agent
python main.py

# 6. Запустить тесты
python -m pytest tests/integration/ -v
```

---

## Тестирование

| Модуль | Тестов | Результат |
|--------|--------|-----------|
| Manager API | 12 | 12/12 |
| Audit Agent | 7 | 7/7 |
| Scanner | 6 | 5/6 (1 skipped) |
| WebUI | 21 | 21/21 |
| E2E | 2 | 2/2 |
| **Итого** | **48** | **47/48** |

---

## Следующий план

**v2.1.0 — Linux агент**
- Агент аудита для Linux (auditd)
- Унифицированный формат событий
- Кроссплатформенный аудит

**v3.0.0 — S3/MinIO + Продакшн**
- Агент аудита для S3/MinIO
- Безопасность (mTLS, шифрование)
- Масштабирование (PostgreSQL, Redis)
