# Интеграционные тесты DCAP

## Запуск

```powershell
# 1. Установить pytest (если нет)
pip install pytest

# 2. Запустить сервисы (3 консоли)
python -m uvicorn manager.src.main:app --port 8000
python run_webui.py

# 3. Запустить тесты (из корня проекта)
pytest tests/integration/ -v
```

## Структура

```
tests/integration/
  conftest.py       # Фикстуры: manager_url, webui_url, db_conn
  test_api.py       # Manager API (health, resources, tasks, findings, catalog, permissions, audit)
  test_scanner.py   # Scanner (регистрация, heartbeat, задания)
  test_audit.py     # Audit Agent (регистрация, heartbeat, события)
  test_webui.py     # WebUI (дашборд, страницы, API, vendor-статика)
  test_e2e.py       # Сквозные тесты (полный цикл)
```

## Примечания

- Тесты работают с реальными сервисами (Manager :8000, WebUI :8001)
- Тестовые агенты/ресурсы создаются и автоматически очищаются
- E2E тест проверяет полный цикл: health -> агент -> событие -> API -> отчет
