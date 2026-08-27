📋 ТЗ: РЕЛИЗ V2.1.0 (ДЕНЬ 27)
Файл: prompts/tz/day_27_release_v2.1.0.md

🎯 ЦЕЛЬ
Оформить релиз версии v2.1.0 — завершение разработки Linux-агента аудита, унификации формата событий и интеграции с Windows-агентом. Обновить документацию, создать релизный тег и подготовить итоговый отчет.

📋 ЗАДАЧИ
1. Тестирование (проверка работоспособности)
Проверить, что все компоненты работают корректно:

□ Windows-агент — отправляет события в Manager
□ Linux-агент — отправляет события в Manager
□ WebUI — фильтр по источнику событий работает
□ WebUI — удаление агентов и сканеров работает
□ Дашборд — показывает статус агентов (онлайн/офлайн)
□ Унифицированный формат — события от обоих агентов имеют одинаковую структуру
2. Обновить документацию
Обновить следующие файлы:

Файл	Что изменить
project_context.md	Версия → v2.1.0, статус → "Linux агент готов"
project_plan.md	Отметить День 27 как выполненный, обновить прогресс
AGENTS.md	Добавить информацию о Linux-агенте, инструкцию по запуску
README.md	Обновить раздел "Установка" (Linux-агент)
backlog.txt	Переместить BACKLOG-007, BACKLOG-008, BACKLOG-009 в ✅
3. Релиз
□ Создать тег v2.1.0 в Git
□ Подготовить Release Notes
□ Итоговый отчет по v2.1.0
📊 ЧТО ВКЛЮЧАЕТ V2.1.0
Новые компоненты
Компонент	Описание
audit-agent-linux/	Легкий агент аудита для Linux (inotify)
shared/event_schema.py	Унифицированный формат событий (UnifiedEvent)
webui/api/routes.py	Фильтр по источнику событий
webui/main.py	Удаление агентов и сканеров через UI
Ключевые изменения
Изменение	Описание
Унификация	Единый формат для Windows и Linux-агентов
Heartbeat	Автоматический offline при >2 минут без heartbeat
Фильтр	По источнику событий (Windows/Linux/Все)
Управление	Удаление агентов и сканеров через UI
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Запустить WebUI
python run_webui.py

# 3. Запустить Windows-агент
cd audit-agent
python main.py

# 4. Запустить Linux-агент (WSL)
cd ~/dcap-system/audit-agent-linux
./start.sh --daemon

# 5. Создать события в Windows
echo "test" > D:\test_audit\test.txt
del D:\test_audit\test.txt

# 6. Создать события в Linux
echo "test" > ~/test_audit/test.txt
rm ~/test_audit/test.txt

# 7. Проверить WebUI
# http://localhost:8001 → Аудит
# Должны быть события от обоих агентов с иконками 🪟 и 🐧
📝 RELEASE NOTES (ШАБЛОН)
markdown
# Release Notes — DCAP System v2.1.0

**Дата:** 2026-08-27
**Версия:** v2.1.0
**Статус:** ✅ Стабильный релиз

---

## 🎯 Обзор

DCAP System v2.1.0 — завершение Linux-фазы. Система теперь поддерживает аудит файловой системы на Windows и Linux через легкие агенты, с единым форматом событий и единой точкой управления в WebUI.

---

## 🆕 Что нового

### Linux-агент аудита
- Отслеживание событий через inotify (watchdog)
- Буферизация в SQLite
- Автозапуск через start.sh или systemd/crontab
- Работает без systemd (для WSL)

### Унифицированный формат событий
- Единая Pydantic-схема UnifiedEvent
- event_source: windows_agent, linux_agent, scanner, api
- Обратная совместимость с историческими данными

### WebUI
- Фильтр по источнику событий
- Иконки для Windows 🪟 и Linux 🐧
- Удаление агентов и сканеров через UI
- Автоматический offline-статус по heartbeat

---

## 📁 Структура проекта
dcap-system/
├── manager/ # FastAPI :8000 (чистое API)
├── scanner/ # тяжелый агент сканирования
├── audit-agent/ # Windows-агент аудита
├── audit-agent-linux/# Linux-агент аудита (NEW)
├── webui/ # каноничный UI :8001
├── shared/ # общие компоненты (event_schema)
└── tests/ # интеграционные тесты

text

---

## 🚀 Как запустить

### Windows
```bash
python -m uvicorn manager.src.main:app --port 8000
python run_webui.py
cd audit-agent && python main.py
Linux
bash
cd ~/dcap-system/audit-agent-linux
./start.sh --daemon
📊 Тестирование
Компонент	Статус
Windows-агент	✅
Linux-агент	✅
WebUI	✅
Интеграционные тесты	✅ (47/48)
🔜 Следующие планы
v3.0.0 — Промышленная система

S3/MinIO аудит

Безопасность (mTLS, шифрование)

Масштабирование (PostgreSQL, Redis)

Мониторинг (Prometheus/Grafana)

text

---

## 💾 КОМАНДА ДЛЯ КОММИТА

```bash
git checkout -b feature/day_27_release_v2.1.0
git add project_context.md project_plan.md AGENTS.md README.md backlog.txt
git commit -m "release: v2.1.0 — Linux-агент аудита, унифицированный формат, WebUI фильтр"
git tag -a v2.1.0 -m "v2.1.0 — Linux-агент аудита, унифицированный формат, WebUI фильтр"
✅ КРИТЕРИИ ПРИЕМКИ
□ Windows-агент работает
□ Linux-агент работает
□ WebUI показывает события от обоих агентов
□ Фильтр по источнику работает
□ Документация обновлена
□ Тег v2.1.0 создан
□ Release Notes подготовлены
Разработчик, приступай! 🚀