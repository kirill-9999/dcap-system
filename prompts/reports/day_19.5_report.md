# 📋 Отчет: День 19.5 — Удаление легаси WebUI и редирект

**Дата:** 25.08.2026
**ТЗ:** `prompts/tz/day_19.5_cleanup_webui.md`
**Статус:** ✅ Выполнено полностью

---

## 🎯 Что сделано

### 1. Удалены легаси-файлы (17 шт.)

| Файл | Статус |
|------|--------|
| `webui/main_final.py` | 🗑 удалён |
| `webui/main_simple.py` | 🗑 удалён |
| `webui/main_static.py` | 🗑 удалён |
| `webui/static/index.html` | 🗑 удалён |
| `webui/static/index_full.html` | 🗑 удалён |
| `webui/static/index_simple.html` | 🗑 удалён |
| `webui/static/js/app.js` | 🗑 удалён |
| `webui/static/js/app_simple.js` | 🗑 отсутствовал |
| `webui/static/js/tasks.js` | 🗑 удалён |
| `webui/static/css/style.css` | 🗑 удалён |
| `webui/static/css/tasks.css` | 🗑 отсутствовал |
| `webui/templates/` (6 html) | 🗑 удалена |
| `webui/static/bootstrap.min.css` | 🗑 удалён (остаток v2 вне списка ТЗ, ссылок нет) |
| `webui/__pycache__/`, `webui/api/__pycache__/` | 🗑 кэш очищен |
| пустые `static/js/`, `static/css/` | 🗑 папки удалены |

`webui/static/` сохранена — не пуста: в ней **`vendor/`** (локальные bootstrap/fontawesome/chart.js для каноничного UI).

### 2. Manager — чистое API (`manager/src/main.py`)

- ❌ Убраны `StaticFiles`, mount `/static`, FileResponse-роуты `/` и `/index.html`, print-диагностика путей (заодно неиспользуемые импорты `StaticFiles`, `FileResponse`, `os`)
- ✅ Добавлен редирект по ТЗ:
```python
from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="http://localhost:8001")
```

### 3. Документация

- **AGENTS.md**: раздел WebUI переписан — каноничный UI только `webui/main.py` (:8001), легаси удалены и «не восстанавливать», Manager на :8000 — чистое API с редиректом; убраны строки про легаси `app.js`/`style.css` и «эксперименты» `main_final/simple/static.py`
- **project_context.md**: структура webui/ обновлена (+run_webui.py в корне, static/vendor/, пометка об удалении легаси)
- **project_plan.md**: День 19.5 отмечен выполненным, файлы Дня 19 скорректированы (убраны легаси-пути), добавлена сводка хотфикса Дня 19

---

## 🧪 Тестирование

### Smoke (TestClient) — 5/5 OK
```
OK  / -> 307 http://localhost:8001
OK  /api/health -> {'status': 'healthy', 'version': '2.0.0-alpha'}
OK  /static/* -> 404 (mount удалён)
OK  /index.html -> 404 (легаси-роут удалён)
OK  API-роуты живы: 15 маршрутов
```

### E2E реальным HTTP — ALL OK
```
redirect: 307 -> http://localhost:8001
followed -> 200 | UI page: True (страница «Аудит» отдаётся)
health: healthy | webui audit stats: доступен
```

### Рабочие процессы
- Manager на :8000 перезапущен на новом коде: `http://localhost:8000/` → 307 → `:8001` → дашборд ✅
- WebUI :8001 не тронут, работает (127.0.0.1, vendor-статика, no-store)

### Критерии приемки ТЗ — все ✅
- [x] Все легаси-файлы удалены (+1 остаток вне списка)
- [x] manager/src/main.py не маунтит /static
- [x] manager/src/main.py редиректит / → :8001
- [x] python run_webui.py запускает WebUI на :8001
- [x] uvicorn manager.src.main:app запускает API (проверено на :8010 и рабочем :8000)
- [x] http://localhost:8000 → редирект на :8001 (проверено e2e)
- [x] AGENTS.md / project_context.md / project_plan.md обновлены

Примечание: `structure.txt` содержит упоминания легаси, но по AGENTS.md он помечен устаревшим («сверяйся с кодом») — сознательно не тронут.

---

## 💾 Команда для коммита

```bash
git checkout -b feature/day_19.5_cleanup_webui
git add -A webui/ manager/src/main.py AGENTS.md project_context.md project_plan.md prompts/tz/day_19.5_cleanup_webui.md prompts/archive/ prompts/reports/day_19.5_report.md
git commit -m "chore: День 19.5 — удаление легаси WebUI и редирект :8000 → :8001"
```
