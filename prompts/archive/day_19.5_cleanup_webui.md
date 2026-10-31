📋 ТЗ: УДАЛЕНИЕ ЛЕГАСИ WEBUI И РЕДИРЕКТ (ДЕНЬ 19.5 / CHORE)
Файл: prompts/tz/day_19.5_cleanup_webui.md

🎯 ЦЕЛЬ
Устранить двойственность WebUI в проекте:

Удалить все легаси-файлы, которые не используются

Настроить редирект с :8000 → :8001

Обновить документацию

Закрепить единую точку входа для UI

📁 ФАЙЛЫ ДЛЯ УДАЛЕНИЯ
Полностью удалить:
text
webui/main_final.py
webui/main_simple.py
webui/main_static.py
webui/static/index.html
webui/static/index_full.html
webui/static/index_simple.html
webui/static/js/app.js
webui/static/js/app_simple.js
webui/static/js/tasks.js
webui/static/css/style.css
webui/static/css/tasks.css
webui/templates/
Проверить и удалить (если пустые или не используются):
text
webui/static/                # если после удаления файлов папка пуста
webui/templates/             # если после удаления папка пуста
webui/api/__pycache__/       # кэш Python
Оставить (нетронутые):
text
webui/main.py                # ✅ каноничный UI
webui/run_webui.py           # ✅ точка входа
webui/api/                   # ✅ routes.py, schemas.py
webui/api/routes.py          # ✅ актуальные роуты
webui/api/schemas.py         # ✅ Pydantic схемы
webui/config.py              # ✅ конфигурация
webui/__init__.py            # ✅ пакет
📋 ИЗМЕНЕНИЯ В MANAGER
1. Убрать mount /static из manager/src/main.py
Найти и удалить:

python
app.mount("/static", StaticFiles(directory="webui/static"), name="static")
Или закомментировать с пояснением:

python
# UI перенесен на :8001 (webui/main.py)
# app.mount("/static", StaticFiles(directory="webui/static"), name="static")
2. Добавить редирект с :8000 → :8001
python
from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="http://localhost:8001")
📋 ИЗМЕНЕНИЯ В ДОКУМЕНТАЦИИ
1. Обновить AGENTS.md
markdown
## WebUI

**Каноничный WebUI:** `webui/main.py` (инлайн) на порту **:8001**.

- Запуск: `python run_webui.py`
- Manager на :8000 — чистое API; корневой путь редиректит на :8001
- Все изменения UI — только в `webui/main.py`
- Легаси-файлы удалены.
2. Обновить project_context.md
В разделе "Компоненты" убрать упоминания о static/, templates/ и легаси-файлах.

3. Обновить project_plan.md
Отметить День 19.5 как выполненный.

✅ КРИТЕРИИ ПРИЕМКИ
□ Все легаси-файлы удалены
□ manager/src/main.py не маунтит /static
□ manager/src/main.py редиректит / → :8001
□ python run_webui.py запускает WebUI на :8001
□ python -m uvicorn manager.src.main:app --port 8000 запускает API на :8000
□ Переход на http://localhost:8000 → http://localhost:8001
□ AGENTS.md обновлен
□ project_context.md обновлен
□ project_plan.md обновлен
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
powershell
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Запустить WebUI
python run_webui.py

# 3. Открыть в браузере
# http://localhost:8000 → должен редиректить на :8001

# 4. Проверить API
curl http://localhost:8000/api/health

# 5. Проверить WebUI
# открыть http://localhost:8001 → дашборд
# перейти по ссылкам (Находки, Ресурсы, Аудит) — работают
📁 СТРУКТУРА ПОСЛЕ ВЫПОЛНЕНИЯ
text
webui/
├── main.py                 # ✅ каноничный UI (инлайн)
├── run_webui.py            # ✅ точка входа
├── config.py               # ✅ конфиг
├── __init__.py             # ✅
└── api/
    ├── routes.py           # ✅ актуальные роуты
    └── schemas.py          # ✅ Pydantic схемы
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_19.5_cleanup_webui
git add webui/ manager/src/main.py AGENTS.md project_context.md project_plan.md
git commit -m "chore: День 19.5 — удаление легаси WebUI и редирект :8000 → :8001"
Разработчик (кодер), приступай! 🚀