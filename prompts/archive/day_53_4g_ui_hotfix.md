📋 ТЗ v3.14.5 — Хотфикс UI (RBAC, Settings, Responsive)
Файл: prompts/tz/day_53_4g_ui_hotfix.md
Дата: 20.10.2026
Версия: v3.14.4 → v3.14.5
Приоритет: 🔴 Блокер v3.0.0 (Критичный баг RBAC + UX)
Длительность: 0.5–1 день
Источник: Мастер-сессия ручного тестирования (Треки А и B)

🎯 Цель — 6 задач
ID	Название	Severity
BUG-NEW-4	dashboard.js → checkAuditAccess() не блокирует запросы к /api/audit/* под viewer (403-спам, тосты).	🔴
BUG-NEW-5	settings.html → при неверном старом пароле происходит редирект на /login (вместо тоста).	🟡
BUG-NEW-6	settings.html → не отображается «Последний запуск» (last_run) из /api/retention/status.	🟡
BUG-NEW-7	settings.html → CSS-баг: слипшийся текст «События аудита2065», «Находки900».	🟢
BUG-273	Dashboard (393px) → KPI-карточки вылезают за экран, горизонтальный скролл.	🔴
BUG-272	Dashboard → пустые графики Chart.js при 0 находок (нет плашки «Нет данных»).	🟡 (опц.)
Плюс backlog (если успеешь):

BACKLOG-326 — /users (393px): карточки вместо таблицы (правильный responsive).

📋 Задачи
🔴 BUG-NEW-4 — dashboard.js: RBAC-проверка не работает под viewer
Файл: webui/static/js/dashboard.js, webui/static/js/main.js

Проблема: В v3.14.4 была добавлена функция checkAuditAccess(), которая должна возвращать false для viewer. Однако в тестах она вернула true (или не успела инициализироваться), из-за чего запросы к /api/audit/* всё равно ушли и получили 403.

Причина: Функция полагается на RBAC.isAuditor(), но RBAC инициализируется асинхронно, и window.whenSessionReady() не дождался его готовности. Либо RBAC.isAuditor() возвращает true для viewer из-за ошибки в main.js.

Фикс:

В main.js (или auth.js) исправить RBAC.isAuditor(): он должен проверять наличие роли admin или auditor в Auth.me().roles.

В dashboard.js усилить checkAuditAccess():

javascript
async function checkAuditAccess() {
    // 1. Пробуем дождаться сессии (максимум 2 секунды)
    try {
        if (window.whenSessionReady) await window.whenSessionReady();
    } catch (e) { /* ignore */ }

    // 2. Пытаемся получить роли через Auth.me() (надежный источник)
    if (typeof Auth !== 'undefined' && Auth.me) {
        const me = await Auth.me().catch(() => null);
        const roles = (me && me.roles) || [];
        return roles.includes('admin') || roles.includes('auditor');
    }

    // 3. Fallback на RBAC (если Auth.me недоступен)
    if (typeof RBAC !== 'undefined' && RBAC.isAuditor) {
        return RBAC.isAuditor();
    }

    return false;
}
Файл: webui/static/js/api.js — убедиться, что e.status заполняется при 403 (BUG-266), чтобы console.warn не срабатывал.

🟡 BUG-NEW-5 — Settings: редирект на логин при неверном пароле
Файл: webui/static/js/settings.js (или inline-скрипт в settings.html)

Проблема: При отправке формы смены пароля с неверным старым паролем бэкенд возвращает 401 (или 403). Глобальный обработчик в api.js видит 401 и делает принудительный logout() + редирект на /login. Пользователь не видит текст ошибки.

Фикс:
В обработчике формы #passwordForm перехватить ошибку до того, как она попадет в глобальный api.js:

javascript
try {
    await api.post('/api/auth/change-password', {...});
    showToast('Пароль успешно изменен', 'success');
} catch (err) {
    if (err.status === 400 || err.status === 401 || err.status === 403) {
        // Не даем api.js сделать логаут
        showToast(err.message || 'Неверный текущий пароль', 'error');
    } else {
        throw err; // для остальных ошибок — стандартное поведение
    }
}
Также проверить, что в api.js редирект на /login при 401 не срабатывает для эндпоинта /api/auth/change-password.

🟡 BUG-NEW-6 — Settings: не отображается «Последний запуск»
Файл: webui/static/js/settings.js

Проблема: На странице «Настройки» в блоке хранения данных поле «Последний запуск: —» пустое, хотя в /api/retention/status есть last_run.

Фикс:
При загрузке страницы (или при нажатии кнопки «Dry-run» / «Запустить архивацию») сделать запрос:

javascript
const status = await api.get('/api/retention/status');
if (status.last_run) {
    // Формат: 2026-10-20T15:33:41
    const d = new Date(status.last_run);
    document.getElementById('lastRun').textContent = d.toLocaleString('ru-RU');
} else {
    document.getElementById('lastRun').textContent = 'Никогда';
}
Убедиться, что в settings.html есть элемент с id="lastRun" (например, <span id="lastRun">—</span>).

🟢 BUG-NEW-7 — Settings: слипшийся текст счётчиков
Файл: webui/static/css/settings.css (или tables.css)

Проблема: На скриншоте видно «События аудита2065», «Находки900». Отсутствует пробел/отступ между названием поля и цифрой.

Фикс:
В HTML добавить отступы (например, <span class="me-2">События аудита</span><strong>2065</strong>).
Или в CSS:

css
.stat-item .label { margin-right: 8px; }
🔴 BUG-273 — Dashboard: сломанный responsive (393px)
Файл: webui/static/css/main.css (или dashboard.css), webui/templates/dashboard.html

Проблема: На 393px KPI-карточки вылезают за край экрана, появляется горизонтальный скролл.

Фикс:
Найти контейнер с KPI-карточками (скорее всего <div class="row" id="kpiRow">) и добавить CSS:

css
@media (max-width: 480px) {
    .kpi-card {
        flex: 0 0 100%; /* каждая карточка на всю ширину */
        max-width: 100%;
        margin-bottom: 1rem;
    }
    /* Убираем горизонтальный скролл */
    body, .main-content {
        overflow-x: hidden;
    }
}
Проверить, что карточки «Ресурсов», «Находок», «Агентов», «Алертов» идут в столбик и не вылезают за пределы экрана.

🟡 BUG-272 (опционально) — Dashboard: пустые графики при 0 находок
Файл: webui/static/js/dashboard.js

Проблема: Если findings = 0, Chart.js отрисовывает пустые оси/контейнеры без данных.

Фикс:
В renderFindingsCharts и renderAuditCharts добавить проверку:

javascript
if (!findings.length) {
    document.getElementById('findingsByCategoryChart').style.display = 'none';
    document.getElementById('findingsByCategoryChart').parentElement.innerHTML = '<div class="text-muted text-center p-4">Нет находок</div>';
    return;
}
Или использовать плагин Chart.js emptyData (или просто скрыть canvas).

🧪 Тесты
Unit — tests/unit/test_hotfix_v3145.py (new)
python
"""Tests for BUG-NEW-4/5/6/7, BUG-273, BUG-272 (v3.14.5)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_dashboard_rbac_uses_auth_me():
    """BUG-NEW-4: dashboard.js использует Auth.me() для надежной проверки ролей."""
    src = (ROOT / "webui/static/js/dashboard.js").read_text(encoding="utf-8")
    assert "Auth.me()" in src, "dashboard.js должен использовать Auth.me()"

def test_api_skips_401_redirect():
    """BUG-NEW-5: api.js не делает редирект на /login при 401 в change-password."""
    src = (ROOT / "webui/static/js/api.js").read_text(encoding="utf-8")
    assert "change-password" in src.lower() or "isLoginPage" in src

def test_settings_shows_last_run():
    """BUG-NEW-6: settings.html содержит элемент для lastRun."""
    tpl = (ROOT / "webui/templates/settings.html").read_text(encoding="utf-8")
    assert 'id="lastRun"' in tpl or 'last_run' in tpl

def test_kpi_cards_mobile_css():
    """BUG-273: CSS для KPI-карточек на мобильных."""
    css = (ROOT / "webui/static/css/main.css").read_text(encoding="utf-8")
    assert "max-width: 480px" in css
    assert "kpi-card" in css or "kpiRow" in css
E2E — tests/e2e/test_hotfix_v3145.py (new)
python
import pytest
import requests

@pytest.mark.e2e
def test_dashboard_kpi_mobile(webui_url):
    """BUG-273: На 393px нет горизонтального скролла (проверяем CSS-класс)."""
    html = requests.get(f"{webui_url}/", timeout=10).text
    assert "kpi-card" in html or "kpiRow" in html

@pytest.mark.e2e
def test_settings_last_run(webui_url):
    """BUG-NEW-6: На странице настроек есть элемент lastRun."""
    html = requests.get(f"{webui_url}/settings", timeout=10).text
    assert 'id="lastRun"' in html
📋 Ручная проверка
Rebuild

powershell
docker compose build webui
docker compose up -d webui
Viewer → / (Dashboard)

Залогиниться под viewer (viewer123).

F12 → Console: должно быть 0 ошибок 403. Если есть [DOM] — это нормально (не связано с API).

F12 → Network: фильтр audit — запросы к /api/audit/* не должны появляться.

KPI «Ресурсов» и «Агентов» = «—».

Вместо графиков — плашка «Нет прав на аудит».

Admin → /settings

Залогиниться под admin.

Перейти в «Настройки».

BUG-NEW-6: «Последний запуск» должен показывать дату (если запуск был) или «Никогда».

BUG-NEW-7: Цифры счётчиков отделены от названий (нет слипшегося текста).

Попробовать сменить пароль на неверный старый → должен появиться тост «Неверный пароль», без редиректа на логин.

Admin → / (Dashboard) 393px

Открыть DevTools → 393px.

BUG-273: KPI-карточки идут в столбик, нет горизонтального скролла.

Viewer → / (Dashboard) при 0 находок (на тестовом стенде)

BUG-272 (опционально): вместо пустых графиков — плашка «Нет данных».

✅ Definition of Done
#	Проверка	Статус
1	Viewer / — 0 ошибок 403 в Console, 0 запросов к /api/audit/*	⏳
2	Viewer / — KPI «—», плашка «Нет прав»	⏳
3	Admin /settings — «Последний запуск» отображается	⏳
4	Admin /settings — смена пароля (неверный) без редиректа на /login	⏳
5	Admin /settings — CSS счётчиков исправлен (нет слипшегося текста)	⏳
6	Admin / (393px) — KPI-карточки в столбик, нет скролла	⏳
7	Unit 525+ passed	⏳
8	E2E +2 (hotfix)	⏳
💾 Коммит
powershell
git add webui/static/js/dashboard.js webui/static/js/api.js webui/static/js/settings.js `
        webui/templates/dashboard.html webui/templates/settings.html `
        webui/static/css/main.css webui/static/css/settings.css `
        tests/unit/test_hotfix_v3145.py tests/e2e/test_hotfix_v3145.py `
        docker-compose.yml `
        ARCHITECTURE.md ROADMAP.md STATE.md STATE_TEST_SESSION.md CHANGELOG.md `
        prompts/tz/day_53_4g_ui_hotfix.md `
        prompts/reports/day_53_4g_ui_hotfix_report.md
git commit -m "fix: 53.4g UI hotfix — RBAC dashboard + Settings + Responsive (v3.14.5)

BUG-NEW-4: dashboard.js — надежная проверка ролей через Auth.me()
BUG-NEW-5: settings.js — обработка 401 при смене пароля без редиректа
BUG-NEW-6: settings.html — отображение last_run
BUG-NEW-7: settings.css — исправлен слипшийся текст счётчиков
BUG-273: main.css — responsive KPI-карточек на 393px
BUG-272 (опц.): dashboard.js — плашка «Нет данных» при 0 находок

Tests: test_hotfix_v3145.py (4 unit), test_hotfix_v3145.py (2 e2e).
Unit 525+ passed. E2E +2.
VERSION 3.14.5."