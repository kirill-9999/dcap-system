# Отчет: Исправление агента аудита + День 19.5

**Дата:** 25.08.2026
**Статус:** Все исправления выполнены и проверены

---

## Что сделано

### Часть 1: День 19.5 — Удаление легаси WebUI (chore)

| Действие | Результат |
|----------|-----------|
| Удалены `main_final.py`, `main_simple.py`, `main_static.py` | Done |
| Удалены `static/index*.html`, `static/js/*`, `static/css/*` | Done |
| Удалены `templates/` (6 html), кэши `__pycache__` | Done |
| Удалён остаток `static/bootstrap.min.css` (вне ТЗ, ссылок нет) | Done |
| Manager (`:8000`) — чистое API, `/` редиректит на `:8001` (307) | Done |
| WebUI vendor-ассеты (bootstrap, font-awesome, chart.js) скачаны локально | Done |
| `WEBUI_HOST` → `127.0.0.1`, `Cache-Control: no-store` на `/` | Done |
| AGENTS.md / project_context.md / project_plan.md обновлены | Done |

Проверки: TestClient 5/5, E2E реальным HTTP (redirect 307 → :8001 → UI с аудитом),的所有 10/10 критериев ТЗ.

### Часть 2: Хотфикс Дня 19 — Inline-JS

| Проблема | Причина | Фикс |
|----------|---------|------|
| Ссылки в WebUI не нажимались | `\n` и `\'` в alert/onclick ломали синтаксис всего JS | Экранирование `\\n` (20 мест) + `\\'` (6 мест) в `webui/main.py` |
| Антивирус блокировал страницу | CDN-сссылки (jsdelivr/cdnjs) — мишени веб-фильтров | Vendor локально в `webui/static/vendor/` |

---

### Часть 3: Исправление агента аудита (5 багов)

#### Баг 1: SQLite threading error

**Симптом:** Лог завален ошибками `SQLite objects created in a thread can only be used in that same thread`.

**Причина:** `BufferManager` создавал `sqlite3.connect()` без `check_same_thread=False`. Служба запускает агент в `threading.Thread`, а SQLite-объект создавался в главном потоке службы.

**Фикс:** `buffer.py:19` — добавлен `check_same_thread=False`.

---

#### Баг 2: Относительные пути в службе

**Симптом:** Служба стартовала, но `state.json` и `buffer/` создавались в `C:\Windows\System32\` (CWD службы), а не в `audit-agent/`. Агент тихо работал, но ничего не собирал.

**Причина:** `main.py` использовал `Path("state.json")` и `Path("buffer")` — относительные пути, резолвились от CWD процесса.

**Фикс:** `main.py:22,57,64` — все пути через `self.base_dir = config_path.parent`:
- `self.base_dir / "state.json"`
- `self.base_dir / self.config.get("buffer_dir", "buffer")`

---

#### Баг 3: Текстовый парсер не работал на русской Windows

**Симптом:** wevtutil отдавал события, но парсер возвращал 0. Даже после исправления бага 2 агент не собирал события.

**Причина:** `collector.py` читал Text-вывод (`/f:Text`), где поля локализованы: `Event ID:` вместо `EventId:`, `Имя учетной записи:` вместо `SubjectUserName:`, `Имя объекта:` вместо `ObjectName:`.

**Фикс:** Полная переработка `collector.py`:
- `/f:Text` → `/f:XML` (теги `EventID`, `SubjectUserName` и т.д. всегда на английском)
- Парсинг через `xml.etree.ElementTree`
- Удаление namespace `xmlns=...` перед парсингом (ломал `findall('Event')`)
- Авто-обёртка голых `<Event>` в `<Events>` (wevtutil без `/e Events` отдаёт без корневого элемента)

---

#### Баг 4: XPath `TimeCreated` не работает в wevtutil

**Симптом:** Запрос `*[System[TimeCreated[@SystemTime>='...']]]` возвращал пустоту — wevtutil не поддерживает этот XPath.

**Причина:** wevtutil использует урезанную реализацию XPath 1.0, `TimeCreated` с атрибутом `@SystemTime` не поддерживается.

**Фикс:** `collect_events()` — фильтр по `EventID` в XPath-запросе (`EventID=4656 or EventID=4660 or ...`), фильтр по времени в Python после парсинга.

---

#### Баг 5: `/e Events` / space-syntax

**Симптом:** `Указано слишком много аргументов` — wevtutil не понимал `/f XML` через пробел.

**Причина:** wevtutil требует colon-syntax: `/f:XML`, а не `/f XML`. Параметр `/e Events` также вызывал проблемы.

**Фикс:**
- `/q`, `/f`, `/c` → colon-syntax: `/q:...`, `/f:XML`, `/c:1000`
- `/e Events` убран — wevtutil отдаёт голые `<Event>`, парсер оборачивает в `<Events>` автоматически

---

## Результат

Служба `DCAPAuditAgent` работает:
```
Отправлено 22 событий
Отправлено 1 событий
```
- `state.json`: `agent_id: 1`, `last_read` обновляется
- `buffer/buffer.db`: создаётся и работает
- Дашборд WebUI: события отображаются в разделе «Аудит»
- Сервис稳定性: ошибок в логе нет

---

## Изменённые файлы

| Файл | Изменения |
|------|-----------|
| `audit-agent/buffer.py` | `check_same_thread=False` |
| `audit-agent/main.py` | `base_dir = config_path.relative`, пути через `self.base_dir` |
| `audit-agent/collector.py` | Полная переработка: XML + ElementTree, namespace strip, bare Event wrap, colon-syntax, EventID query, Python time filter |
| `manager/src/main.py` | Убран mount /static, FileResponse, добавлен RedirectResponse на :8001 |
| `webui/main.py` | Экранирование `\n`/`\'` в inline-JS, vendor-ссылки в `<head>`, no-store |
| `webui/config.py` | `WEBUI_HOST` → `127.0.0.1` |
| `webui/api/routes.py` | Добавлены `GET /api/audit`, `GET /api/audit/stats` |
| `webui/static/vendor/` | Локальные bootstrap, font-awesome, chart.js |
| `AGENTS.md` | Обновлен раздел WebUI, фиксы описаны |
| `project_context.md` | Структура webui/ обновлена |
| `project_plan.md` | День 19.5 отмечен выполненным |

---

## Рекомендации для следующих ТЗ

1. **Тестирование на русской Windows** — все ТЗ по аудиту/агенту нужно проверять на локализованной системе. wevtutil Text-вывод локализован, XML — нет. XPath тоже нестабилен.
2. **Служба vs консоль** — пути должны быть абсолютными (от `config_path.parent`), CWD службы ≠ CWD консоли.
3. **SQLite + threading** — всегда `check_same_thread=False` для многопоточных сервисов.
4. **wevtutil colon-syntax** — `/f:XML`, `/q:...`, `/c:N` (не через пробел).
5. **CDN vs vendor** — антивирусы блокируют jsdelivr/cdnjs, полагаться на CDN нельзя.
