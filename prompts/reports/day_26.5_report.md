# Отчет: День 26.5 — Управление агентами и сканерами (удаление)

**Дата:** 27.08.2026
**ТЗ:** `prompts/tz/day_26.5_agent_scanner_management.md`
**Статус:** Выполнено

---

## Результат

Удаление агентов аудита и сканеров через WebUI. Кнопки 🗑️ в таблицах, confirm-диалог,.toast-уведомления. DELETE-эндпоинты в Manager API и WebUI routes.

---

## Измененные файлы

| Файл | Изменение |
|------|-----------|
| `manager/src/api/audit.py` | `DELETE /api/audit/agents/{id}` — отвязка событий (agent_id=NULL), удаление |
| `manager/src/api/scanner.py` | `DELETE /api/scanner/{id}` — освобождение задач при force=true |
| `webui/api/routes.py` | `DELETE /api/scanners/{id}`, `DELETE /api/audit/agents/{id}` (raw SQLite) |
| `webui/main.py` | Кнопки 🗑️ в таблицах, JS deleteScanner/deleteAuditAgent, confirm() |

---

## Проверка

- `DELETE /api/audit/agents/999` → 404 (Agent not found)
- `DELETE /api/scanners/999` → 404 (Scanner not found)
- `DELETE /api/audit/agents/2` → 200 (deleted), agent 2 удалён
- `DELETE /api/scanners/5` → 200 (deleted), scanner 5 удалён
- События удалённого агента сохранились в БД (agent_id=NULL)

---

## Удаленные записи

| Тип | ID | Имя |
|-----|----|-----|
| Агент | 2 | test-reg-agent |
| Сканер | 5 | hb-check-scanner |

---

## Команда для коммита (уже выполнен)

```bash
git add webui/main.py webui/api/routes.py manager/src/api/audit.py manager/src/api/scanner.py
git commit -m "feat: День 26.5 — удаление агентов и сканеров через WebUI"
```

---

## Дополнительные багфиксы (27.08.2026)

### Навигационные ссылки (`bbe5a40`)

**Проблема:** `<a>` без `href` не отображаются как кликабельные (нет pointer cursor, браузер не считает ссылкой).

**Фикс:** добавлен `href="#"` + `return false;` во все 7 nav-link (Дашборд, Находки, Задания, Сканеры, Ресурсы, Доступ, Аудит).

### JS синтаксис в onclick (`e4e8e26`)

**Проблема 1:** Передача имени через `onclick="deleteScanner(id, 'name')"` ломала JS. Python `\'` = `'`, а `\\'` заканчивает Python-строку. В HTML.onclick получалось `''` (пустая строка) вместо кавычки → `SyntaxError: Unexpected string` → весь `<script>` блок не парсится → `switchPage is not defined`.

**Фикс:** передаём `this` + читаем имя из `data-name` атрибута:
```js
onclick="deleteScanner(id, this)" data-name="..."
function deleteScanner(id, btn) { var name = btn.getAttribute('data-name'); ... }
```

**Проблема 2:** `\n` в `confirm()` — браузер видит реальный перенос строки внутри JS-строки → `SyntaxError: Invalid or unexpected token`.

**Фикс:** убран `\n` из confirm-сообщений.

**Важно для будущего:** AGENTS.md гласит `\' → \\\'`, но `\\'` в Python-строке закрывает строку. Решение: передавать данные через `data-*` атрибуты, не через inline JS-аргументы.
