Файл ТЗ: prompts/tz/day_53_4f_bug263_test_fix.md
Дата: 17.10.2026
Версия: v3.14.3 (без bump — тест-инфра)
Приоритет: 🟡 (не блокер v3.0.0, но входит в цикл 53.4f)
Отчёт: prompts/reports/day_53_4f_bug263_report.md

🎯 Цель
Исправить устаревший E2E-тест test_webui_block5_v31322::test_webui_pages_with_filters, который проверяет наличие JS-функции loadFilterOptions в серверном HTML (/audit), хотя после WebUI-редизайна (v3.13.37–v3.14.1) функция находится в audit.js (правильно — JS не должен быть inline в HTML).

Диагноз подтверждён:

Компонент	Факт
webui/templates/audit.html:31	<script src="/static/js/audit.js"></script> — JS подключён
webui/static/js/audit.js:27	async function loadFilterOptions() — определена
webui/static/js/audit.js:172	await loadFilterOptions(); — вызывается в DOMContentLoaded
Тест tests/e2e/test_webui_block5_v31322.py:179	assert "loadFilterOptions" in tpl — ждёт в HTML ❌
UI корректен. Тест устарел.

📋 Задача
1. Фикс теста
Файл: tests/e2e/test_webui_block5_v31322.py
Функция: test_webui_pages_with_filters (строка 171)

Было (строка 177–179):

python
    tpl = requests.get(f"{webui_url}/audit", timeout=10).text
    assert "a-source" in tpl and "a-type" in tpl
    assert "loadFilterOptions" in tpl, "фильтры audit должны быть data-driven"
Стало:

python
    tpl = requests.get(f"{webui_url}/audit", timeout=10).text
    assert "a-source" in tpl and "a-type" in tpl
    # BUG-263: loadFilterOptions определена в audit.js (не inline в audit.html).
    # Серверный HTML не выполняет JS — проверяем подключение скрипта и содержимое JS.
    assert "/static/js/audit.js" in tpl, "audit.html должен подключать audit.js"
    js = requests.get(f"{webui_url}/static/js/audit.js", timeout=10).text
    assert "loadFilterOptions" in js, "audit.js должен определять loadFilterOptions"
Комментарий к фиксу: проверка стала двухуровневой:

HTML подключает audit.js (регресс-защита: если кто-то уберёт <script> — тест упадёт).

audit.js определяет loadFilterOptions (регресс-защита: если функцию переименуют/удалят — тест упадёт).

Это лучше, чем исходная проверка (которая ложно-отрицательна на корректном UI).

2. Проверка
powershell
# Точечно
pytest tests/e2e/test_webui_block5_v31322.py::test_webui_pages_with_filters -v
# Ожидание: 1 passed

# Весь модуль
pytest tests/e2e/test_webui_block5_v31322.py -v -rs
# Ожидание: без падений BUG-263 (остальные 2 падения — seed-findings, BUG-262 этап B)

# Полный E2E (стенд :18000/:18001, без предусловий)
pytest tests/e2e -q -rs 2>&1 | Select-Object -Last 10
# Ожидание: 48 passed, 12 skipped, 5 failed (было 47/12/6)
3. Обновление документации
Файл	Что
docs/testing.md	Раздел «E2E: предусловия и счётчики»: 47/12/6 → 48/12/5; BUG-263 → ✅ (тест-инфра, не UI)
STATE_TEST_SESSION.md	E2E: 48 passed, 12 skipped, 5 failed (без предусловий); 53/7 (цель). BUG-263 → ✅
STATE.md	BUG-263 → ✅ закрыт (v3.14.3, 53.4f). Unit: 517 passed (уточнить команду)
ROADMAP.md	BUG-263 → ✅. BUG-262 этап A → ✅; этап B — до 55; этап C — 55 (BACKLOG-046)
CHANGELOG.md	Запись v3.14.3 (тест-инфра): BUG-259/260/261/263, BUG-262 этап A, BACKLOG-317
4. Уточнение счётчика unit
В отчёте 53.4f указано 517 passed, но не указана команда. Уточнить и зафиксировать:

powershell
pytest tests/unit manager/tests -q 2>&1 | Select-Object -Last 3
Ожидание: 517 passed, 0 errors — без --ignore и без --basetemp (корневой conftest.py должен подхватить .pytest-tmp/).

Если требует --basetemp — значит conftest.py не подхватывается (проверить: он в корне репо E:\projects\dcap-system\conftest.py, не в tests/). Фикс — перенести/переименовать.

Если счётчик другой (не 517) — зафиксировать фактическое число и указать команду.

✅ Definition of Done
test_webui_pages_with_filters — PASSED (без seed-findings, т.к. проверка не зависит от данных).

pytest tests/e2e/test_webui_block5_v31322.py -v — без падений BUG-263.

pytest tests/e2e -q -rs → 48 passed, 12 skipped, 5 failed (было 47/12/6).

pytest tests/unit manager/tests -q → 517 passed (уточнить команду, зафиксировать).

Документация обновлена (docs/testing.md, STATE.md, STATE_TEST_SESSION.md, ROADMAP.md, CHANGELOG.md).

Отчёт prompts/reports/day_53_4f_bug263_report.md — краткий: диагноз, фикс, проверка, счётчики.

💾 Коммит
powershell
git add tests/e2e/test_webui_block5_v31322.py `
        docs/testing.md STATE.md STATE_TEST_SESSION.md ROADMAP.md CHANGELOG.md `
        prompts/tz/day_53_4f_bug263_test_fix.md `
        prompts/reports/day_53_4f_bug263_report.md
git commit -m "fix: BUG-263 — test_webui_pages_with_filters проверяет audit.js, не HTML (v3.14.3)

loadFilterOptions определена в webui/static/js/audit.js (строка 27) и
вызывается в DOMContentLoaded (строка 172); audit.html подключает скрипт
(строка 31). Тест ожидал функцию в серверном HTML — ложно-отрицательный
на корректном UI. Фикс: проверка подключения /static/js/audit.js в HTML +
наличие loadFilterOptions в JS. UI корректен.

Тесты: test_webui_pages_with_filters -> passed;
        tests/e2e -> 48 passed, 12 skipped, 5 failed (было 47/12/6);
        tests/unit manager/tests -> 517 passed (уточнить команду)."
📊 После фикса
Параметр	До	После
E2E (без предусловий)	47/12/6	48/12/5
E2E (цель с предусловиями)	53/7	53/7 (этап B — seed + маркеры)
Unit	517 (уточнить)	517 (зафиксировать в docs)
Остаётся 5 падений (BUG-262 этап B):

3 × сканер :9101 (маркер requires_scanner);

2 × seed-findings (маркер requires_seed).

После 53.4f + BUG-263 → Блок 14 (Settings) — ручной UI-прогон (не зависит от тест-инфры).

Конец ТЗ BUG-263 (53.4f)