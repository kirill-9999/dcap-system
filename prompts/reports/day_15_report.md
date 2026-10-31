# Отчет: День 15 — Тестирование модуля управления доступом

**Дата:** 2026-08-14
**Файл ТЗ:** `prompts/tz/day_15_testing.md`

## 🎯 Цель

Полное тестирование модуля управления доступом (Дни 9-14): API-эндпоинты Manager, логика
AccessService, коллекторы прав, корректность сохранения в БД. Создан автотест-скрипт и
инструкция ручного тестирования WebUI.

## 📁 Созданные файлы

| Файл | Статус |
|------|--------|
| `test_access_management.py` | ✅ создан (10 сценариев из ТЗ) |
| `WEBUI_TEST.md` | ✅ создан (чек-лист ручного тестирования WebUI) |

Существующие файлы (`manager/src/api/permissions.py`, `services/access_service.py`,
`connectors/permissions/local.py`, `db/models.py`) **не изменялись** — только проверены.

> Примечание: ТЗ ссылался на `webui/static/index.html`, `js/app.js`, `css/style.css` как на
> реализацию Дня 14, но фактическая страница «Управление доступом» реализована инлайн в
> `webui/main.py` (актуальный WebUI). `WEBUI_TEST.md` составлен под реальный код (страница на
> `:8001`).

## 📊 Результаты прогона

Окружение: Windows, Python `/d/dev/anaconda3/python` (PYTHONUTF8=1), Manager
`uvicorn manager.src.main:app --port 8000`, ресурс id=1 (`D:\Projects\dcap-system\test_files`).

```
✅ Manager доступен
✅ Тест 1: Режим = local
✅ Тест 2: Синхронизировано 3 записей (entries_saved=3, alerts_generated=1)
✅ Тест 3: Найдено 3 записей прав (SYSTEM/full_control, Authenticated Users/modify, BUILTIN\Users/read)
✅ Тест 4: Эффективные права для BUILTIN\Users = ['read']
✅ Тест 5: Найдено 1 избыточных прав (wide_access: NT AUTHORITY\Authenticated Users — modify)
✅ Тест 6: Наследуемых 3, прямых 0 (100.0%)
✅ Тест 7: Полный отчет получен (3 записи, 2 алерта)
✅ Тест 8: Найдено 2 алертов (warning/wide_access)
✅ Тест 9: Алерт 2 → acknowledged → open (восстановлен)
✅ Тест 10: режим подтвержден (local); переключение на remote — 503 (см. замечания)
✅ Пройдено: 10/10
```

## 🔄 Адаптация скрипта под реальный контракт API

ТЗ содержало несколько несоответствий фактическому API — адаптировано:

| Пункт ТЗ | Факт (реальный API) | Решение |
|----------|---------------------|---------|
| `data["entries_saved"]` в ответе sync | поле лежит в `data["result"]["entries_saved"]` | читаем из `result` |
| `data["alerts"]` в ответе excessive | фактически `data["issues"]` + `data["count"]` | читаем `issues` |
| Переключение режима local→remote | `POST /mode {"mode":"remote"}` → **503** "Collector remote is not available" | тест корректно обрабатывает отказ (warning) и продолжает |

## ⚠️ Замечания (найти/дефекты)

1. **Режим не персистится.** `AccessService.switch_mode()` меняет только in-memory экземпляр;
   `GET /mode` после переключения создаёт новый сервис и возвращает режим из конфига
   (`access_config.json` отсутствует → всегда `local`). Переключение «взаправду» на другой режим
   между запросами не сохраняется. Рекомендация: сохранять режим в конфиг-файл
   (`config/access_config.json`) в `switch_mode`. (Файл `access_service.py` не менялся — по ТЗ.)
2. **Remote/AD коллекторы недоступны на этой машине** (нет Scanner/AD) — `POST /mode {"mode":"remote"}`
   возвращает 503. Это ожидаемое ограничение платформы, API корректно отказывает.
3. **Дублирующиеся алерты.** В БД 2 алерта `wide_access` с одинаковым principal/статусом
   (созданы разными синками до дедупликации). `_generate_alerts` обновляет существующие, но
   исторические дубли остаются. Не блокер, отметить для Дня 15/Недели 4.
4. **Синк пересоздаёт записи прав** (delete + insert) — id растут, `granted_at` сбрасывается.
   Работает корректно, но история изменений (PermissionChange) при этом не фиксируется.

## 🧪 Как проверить

```powershell
# Терминал 1
python -m uvicorn manager.src.main:app --port 8000

# Терминал 2
python test_access_management.py          # ожидаем "Пройдено: 10/10"

# Ручная проверка WebUI — см. WEBUI_TEST.md (перед запуском скопировать БД)
copy manager/dcap.db manager/src/db/dcap.db
python run_webui.py                        # страница «Управление доступом» на :8001
```

## 📁 Структура после выполнения

```
dcap-system/
├── test_access_management.py      # ✅ создан
├── WEBUI_TEST.md                  # ✅ создан (опционально, по ТЗ)
├── prompts/
│   ├── tz/day_15_testing.md       # ✅ это ТЗ
│   └── reports/day_15_report.md   # ✅ этот отчет
```

## 💾 Команда для коммита

```bash
git checkout -b feature/day_15_testing
git add test_access_management.py WEBUI_TEST.md
git commit -m "test: День 15 — тестирование модуля управления доступом"
git push -u origin feature/day_15_testing
```
