# ТЗ 53.4b — WebUI-редизайн, этап 2

**Дата:** 12.10.2026
**Версия:** v3.14.0
**Приоритет:** 🔴 WebUI
**Длительность:** 3–5 дней
**Источник:** мастер-сессия v3.13.38

---

## 🎯 Цель

Редизайн **login / dashboard / findings** + **frontend RBAC** + **Responsive**
(sidebar, гамбургер, Chart.js, модалки).

---

## 📋 Задачи

### 🔴 BUG-213 — Frontend RBAC не работает

**Файлы:** `webui/static/js/main.js`, `auth.js`, `base.html`.

**Фикс:**
1. Sidebar — фильтровать по `user.roles`:
   ```js
   const ROLES = { admin: [...], auditor: [...], scanner: [...] };
   // Скрывать разделы по ролям
Router — редирект на / при 403.

Кнопки — скрывать по ролям.

Сообщения — на русском.

Связано: BUG-216, 219, 222, 224, 227, 217.

🔴 BUG-228 / 233 — Sidebar + гамбургер
Файлы: webui/static/css/main.css, webui/static/js/main.js.

CSS:

css
@media (max-width: 1024px) {
  .sidebar { width: 60px; }
  .sidebar .label { display: none; }
}

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: -250px;
    width: 250px;
    transition: left 0.3s;
    z-index: 1000;
  }
  .sidebar.open { left: 0; }
  .sidebar-overlay { display: none; }
  .sidebar-overlay.open { display: block; }
  .main-content { margin-left: 0; }
}
JS:

js
document.getElementById('sidebar-toggle').addEventListener('click', () => {
  document.querySelector('.sidebar').classList.toggle('open');
  document.querySelector('.sidebar-overlay').classList.toggle('open');
});
Связано: BUG-231.

🔴 BUG-229 — Chart.js адаптив
Файл: webui/static/js/dashboard.js.

js
new Chart(ctx, {
  type: 'doughnut',
  options: {
    responsive: true,
    maintainAspectRatio: false,
    aspectRatio: 1,
    plugins: {
      legend: { position: window.innerWidth < 768 ? 'bottom' : 'right' }
    }
  }
});
Обёртка:

html
<div style="position: relative; height: 300px;">
  <canvas id="chart"></canvas>
</div>
Связано: Chart.js палитра (53.4d).

🔴 BUG-232 — Модалки на mobile
Файл: webui/static/css/components.css.

css
@media (max-width: 480px) {
  .modal-dialog { max-width: 100%; margin: 0; }
  .modal-content {
    border-radius: 0;
    max-height: 100vh;
    overflow-y: auto;
  }
  .modal-body {
    max-height: calc(100vh - 200px);
    overflow-y: auto;
  }
}
🟡 BUG-216 — Ошибки RBAC на русском
Файл: webui/static/js/api.js (+ i18n).

js
function errorToRussian(detail) {
  const map = {
    'Required roles: admin': 'Недостаточно прав. Обратитесь к администратору',
    'Invalid credentials': 'Неверный логин или пароль',
    'Current password is incorrect': 'Неверный текущий пароль',
    'Passwords do not match': 'Пароли не совпадают',
    'Cannot delete yourself': 'Вы не можете удалить себя',
    'Cannot disable yourself': 'Вы не можете заблокировать себя',
  };
  return map[detail] || detail;
}
Связано: BUG-165, BACKLOG-106.

🟡 BUG-142 — Dashboard KPI «Ресурсов» (frontend)
js
const resourcesResp = await api.get('/api/resources?limit=1');
document.getElementById('kpi-resources').textContent =
  resourcesResp.headers.get('X-Total-Count') || '0';
🟡 BUG-141 — Время UTC → локализовать
Файл: новый webui/static/js/datetime.js.

js
function formatDate(isoStr) {
  const d = new Date(isoStr + 'Z');  // backend отдаёт UTC без Z
  return d.toLocaleString('ru-RU');
}
Затронуто: /audit, /scanners, /findings/{id}, /false-positives.

🟡 BUG-205/206/207 — Findings UI
BUG-205 — placeholder overflow.

BUG-206 — ✓/✗ стиль Dovetail.

BUG-207 — badge new → новое.

🟡 BUG-146 — Login наезжает
Файл: webui/templates/login.html.

Фикс: flex + gap, ограничение ширины.

🟡 BUG-203/204 — Dashboard KPI
BUG-203 — KPI «Алерты» — убрать или реализовать.

BUG-204 — «Находки по ресурсам» пусто — проверить API.

🟡 BACKLOG-119 — Убрать hybrid badge
Файл: webui/templates/login.html.

🟡 BACKLOG-121 — .btn-primary → white filled
Файл: webui/static/css/components.css.

✅ Definition of Done
RBAC — работает на frontend (sidebar, router, кнопки).

Sidebar — адаптивна (768 / 393).

Гамбургер — работает.

Chart.js — адаптивен.

Модалки — адаптивны.

Ошибки — на русском.

/login, /, /findings — в Dovetail.

Скриншоты на 3 разрешениях: 1920 / 768 / 393.

Конец ТЗ 53.4b