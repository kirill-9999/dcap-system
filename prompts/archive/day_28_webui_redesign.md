📋 ТЗ — ДЕНЬ 28: WEBUI РЕДИЗАЙН (ENTERPRISE UI)
Файл: prompts/tz/day_28_webui_redesign.md
Дата: 28.08.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Переработать WebUI для промышленного использования:

Единый дизайн-система — цвета, шрифты, отступы, компоненты

Enterprise-дашборд — виджеты, KPI, графики

Адаптивная верстка — работает на планшетах/телефонах

Темная/светлая тема — переключение через кнопку + сохранение в localStorage

Улучшенная навигация — боковое меню, хлебные крошки

Единый стиль таблиц, форм, модальных окон

Структура каталога webui/ — единообразие с будущей стандартизацией

📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ / СОЗДАНИЯ
НОВЫЕ ФАЙЛЫ (СОЗДАТЬ)
Файл	Назначение
webui/src/static/css/variables.css	CSS-переменные (цвета, шрифты, отступы)
webui/src/static/css/theme-light.css	Светлая тема
webui/src/static/css/theme-dark.css	Темная тема
webui/src/static/css/main.css	Главный CSS (импорты всех файлов)
webui/src/static/css/components/sidebar.css	Стили бокового меню
webui/src/static/css/components/header.css	Стили шапки
webui/src/static/css/components/cards.css	Стили карточек и KPI
webui/src/static/css/components/tables.css	Стили таблиц
webui/src/static/css/components/forms.css	Стили форм и фильтров
webui/src/static/css/components/modals.css	Стили модальных окон
webui/src/static/css/components/badges.css	Стили бейджей статусов
webui/src/static/css/pages/dashboard.css	Стили дашборда
webui/src/static/css/pages/catalog.css	Стили каталога
webui/src/static/css/pages/findings.css	Стили находок
webui/src/static/css/pages/resources.css	Стили ресурсов
webui/src/static/css/pages/audit.css	Стили аудита
webui/src/static/css/pages/access.css	Стили доступа
webui/src/static/css/pages/scanners.css	Стили сканеров
webui/src/static/js/main.js	Главный JS (инициализация, тема, навигация)
webui/src/static/js/theme.js	Переключение тем
webui/src/static/js/dashboard.js	Дашборд (виджеты, графики)
webui/src/static/js/table.js	Универсальная таблица
webui/src/static/js/filters.js	Фильтры и поиск
webui/src/static/js/api.js	HTTP-клиент (fetch)
webui/templates/base.html	Базовый шаблон (header, sidebar, footer)
webui/templates/dashboard.html	Дашборд
webui/templates/catalog.html	Каталог
webui/templates/findings.html	Находки
webui/templates/resources.html	Ресурсы
webui/templates/audit.html	Аудит
webui/templates/access.html	Доступ
webui/templates/scanners.html	Сканеры
webui/templates/settings.html	Настройки
webui/templates/components/card.html	Компонент карточки
webui/templates/components/table.html	Компонент таблицы
webui/templates/components/modal.html	Компонент модального окна
webui/templates/components/chart.html	Компонент графика
webui/templates/components/filter.html	Компонент фильтра
webui/templates/components/kpi-card.html	Компонент KPI-карточки
webui/src/core/config.py	Загрузка конфига
webui/src/core/logging.py	Настройка логирования
webui/config/config.json	Конфигурация WebUI
webui/.env.example	Пример переменных окружения
webui/Dockerfile	Docker-сборка
webui/requirements.txt	Зависимости
ИЗМЕНЕННЫЕ ФАЙЛЫ (ОБНОВИТЬ)
Файл	Изменение
webui/src/main.py	Полная переработка: новые маршруты, интеграция с шаблонами
webui/src/api/routes.py	Обновление прокси-эндпоинтов (приведение к новому стилю)
📋 ДЕТАЛЬНОЕ ТЗ
1. Структура каталога webui/
Привести структуру к единому стандарту:

text
webui/
├── Dockerfile
├── requirements.txt
├── .env.example
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── logging.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── schemas.py
│   └── static/
│       ├── css/
│       │   ├── main.css
│       │   ├── variables.css
│       │   ├── theme-light.css
│       │   ├── theme-dark.css
│       │   ├── components/
│       │   │   ├── sidebar.css
│       │   │   ├── header.css
│       │   │   ├── cards.css
│       │   │   ├── tables.css
│       │   │   ├── forms.css
│       │   │   ├── modals.css
│       │   │   └── badges.css
│       │   └── pages/
│       │       ├── dashboard.css
│       │       ├── catalog.css
│       │       ├── findings.css
│       │       ├── resources.css
│       │       ├── audit.css
│       │       ├── access.css
│       │       └── scanners.css
│       ├── js/
│       │   ├── main.js
│       │   ├── theme.js
│       │   ├── dashboard.js
│       │   ├── table.js
│       │   ├── filters.js
│       │   └── api.js
│       └── vendor/
│           ├── bootstrap/
│           ├── fontawesome/
│           └── chart.js/
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── catalog.html
│   ├── findings.html
│   ├── resources.html
│   ├── audit.html
│   ├── access.html
│   ├── scanners.html
│   ├── settings.html
│   └── components/
│       ├── card.html
│       ├── table.html
│       ├── modal.html
│       ├── chart.html
│       ├── filter.html
│       └── kpi-card.html
├── config/
│   └── config.json
├── data/
├── logs/
└── tests/
    ├── unit/
    └── integration/
2. CSS-переменные и темы (webui/src/static/css/)
2.1 variables.css
css
/* webui/src/static/css/variables.css */
:root {
    /* ===== COLORS ===== */
    /* Primary */
    --color-primary: #2563eb;
    --color-primary-dark: #1d4ed8;
    --color-primary-light: #60a5fa;
    --color-primary-bg: #eff6ff;
    
    /* Secondary */
    --color-secondary: #7c3aed;
    --color-secondary-bg: #f5f3ff;
    
    /* Status */
    --color-success: #22c55e;
    --color-success-bg: #f0fdf4;
    --color-warning: #f59e0b;
    --color-warning-bg: #fffbeb;
    --color-danger: #ef4444;
    --color-danger-bg: #fef2f2;
    --color-info: #06b6d4;
    --color-info-bg: #ecfeff;
    
    /* Neutrals */
    --color-bg: #f8fafc;
    --color-surface: #ffffff;
    --color-text: #0f172a;
    --color-text-secondary: #475569;
    --color-text-muted: #94a3b8;
    --color-border: #e2e8f0;
    --color-border-hover: #cbd5e1;
    
    /* ===== SHADOWS ===== */
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
    --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
    --shadow-xl: 0 20px 25px rgba(0,0,0,0.15);
    
    /* ===== SPACING ===== */
    --spacing-1: 4px;
    --spacing-2: 8px;
    --spacing-3: 12px;
    --spacing-4: 16px;
    --spacing-5: 20px;
    --spacing-6: 24px;
    --spacing-8: 32px;
    --spacing-10: 40px;
    --spacing-12: 48px;
    
    /* ===== BORDER RADIUS ===== */
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-xl: 16px;
    --radius-full: 9999px;
    
    /* ===== FONT ===== */
    --font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --font-size-xs: 11px;
    --font-size-sm: 13px;
    --font-size-md: 15px;
    --font-size-lg: 18px;
    --font-size-xl: 22px;
    --font-size-2xl: 28px;
    --font-size-3xl: 36px;
    
    /* ===== TRANSITIONS ===== */
    --transition-fast: 150ms ease;
    --transition-base: 250ms ease;
    --transition-slow: 400ms ease;
    
    /* ===== LAYOUT ===== */
    --sidebar-width: 240px;
    --sidebar-collapsed-width: 64px;
    --header-height: 60px;
}

/* ===== DARK THEME ===== */
[data-theme="dark"] {
    --color-bg: #0f172a;
    --color-surface: #1e293b;
    --color-text: #f1f5f9;
    --color-text-secondary: #94a3b8;
    --color-text-muted: #64748b;
    --color-border: #334155;
    --color-border-hover: #475569;
    --color-primary-bg: #1e293b;
    --color-secondary-bg: #2d1f3d;
    --color-success-bg: #1a2e1a;
    --color-warning-bg: #2d2416;
    --color-danger-bg: #2d1a1a;
    --color-info-bg: #162a30;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.4);
    --shadow-lg: 0 10px 15px rgba(0,0,0,0.5);
    --shadow-xl: 0 20px 25px rgba(0,0,0,0.6);
}
2.2 theme-light.css / theme-dark.css
css
/* webui/src/static/css/theme-light.css */
/* Только переопределения для светлой темы, если нужны */
/* Основные переменные уже в :root, этот файл может быть пустым или содержать специфичные стили */
css
/* webui/src/static/css/theme-dark.css */
/* Дополнительные стили для темной темы, которых нет в переменных */
/* Например, скроллбары, селекты, календари */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: var(--color-bg);
}
::-webkit-scrollbar-thumb {
    background: var(--color-border-hover);
    border-radius: var(--radius-full);
}
::-webkit-scrollbar-thumb:hover {
    background: var(--color-text-muted);
}

select, input, textarea {
    background: var(--color-surface) !important;
    color: var(--color-text) !important;
    border-color: var(--color-border) !important;
}

select option {
    background: var(--color-surface);
    color: var(--color-text);
}
2.3 main.css
css
/* webui/src/static/css/main.css */
/* Импорт всех CSS файлов */

/* Variables & Themes */
@import 'variables.css';
@import 'theme-light.css';
@import 'theme-dark.css';

/* Components */
@import 'components/sidebar.css';
@import 'components/header.css';
@import 'components/cards.css';
@import 'components/tables.css';
@import 'components/forms.css';
@import 'components/modals.css';
@import 'components/badges.css';

/* Pages */
@import 'pages/dashboard.css';
@import 'pages/catalog.css';
@import 'pages/findings.css';
@import 'pages/resources.css';
@import 'pages/audit.css';
@import 'pages/access.css';
@import 'pages/scanners.css';

/* ===== GLOBAL RESET ===== */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html, body {
    height: 100%;
    font-family: var(--font-family);
    font-size: var(--font-size-md);
    background: var(--color-bg);
    color: var(--color-text);
    transition: background var(--transition-base), color var(--transition-base);
}

a {
    color: var(--color-primary);
    text-decoration: none;
}

a:hover {
    color: var(--color-primary-dark);
}

/* ===== LAYOUT ===== */
.app {
    display: flex;
    min-height: 100vh;
}

.main-content {
    flex: 1;
    margin-left: var(--sidebar-width);
    min-height: 100vh;
    transition: margin-left var(--transition-base);
}

.main-content.expanded {
    margin-left: var(--sidebar-collapsed-width);
}

/* ===== UTILITY ===== */
.text-truncate {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.flex {
    display: flex;
}
.flex-center {
    display: flex;
    align-items: center;
    justify-content: center;
}
.flex-between {
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.gap-2 { gap: var(--spacing-2); }
.gap-3 { gap: var(--spacing-3); }
.gap-4 { gap: var(--spacing-4); }

.mt-2 { margin-top: var(--spacing-2); }
.mt-3 { margin-top: var(--spacing-3); }
.mt-4 { margin-top: var(--spacing-4); }
.mb-2 { margin-bottom: var(--spacing-2); }
.mb-3 { margin-bottom: var(--spacing-3); }
.mb-4 { margin-bottom: var(--spacing-4); }

/* Скрытие элементов при коллапсе сайдбара */
.sidebar.collapsed .hide-on-collapse {
    display: none !important;
}
3. Боковое меню (Sidebar)
html
<!-- webui/templates/components/sidebar.html -->
<aside class="sidebar" id="sidebar">
    <div class="sidebar-header">
        <div class="logo">
            <span class="logo-icon">🛡️</span>
            <span class="logo-text hide-on-collapse">DCAP</span>
        </div>
        <button class="sidebar-toggle" onclick="toggleSidebar()" aria-label="Toggle sidebar">
            <i class="fas fa-bars"></i>
        </button>
    </div>
    
    <nav class="sidebar-nav">
        <a href="/" class="nav-item active" data-page="dashboard">
            <span class="nav-icon"><i class="fas fa-chart-pie"></i></span>
            <span class="nav-label hide-on-collapse">Дашборд</span>
        </a>
        <a href="/catalog" class="nav-item" data-page="catalog">
            <span class="nav-icon"><i class="fas fa-folder-tree"></i></span>
            <span class="nav-label hide-on-collapse">Каталог</span>
            <span class="nav-badge hide-on-collapse" id="catalogBadge">0</span>
        </a>
        <a href="/findings" class="nav-item" data-page="findings">
            <span class="nav-icon"><i class="fas fa-exclamation-triangle"></i></span>
            <span class="nav-label hide-on-collapse">Находки</span>
            <span class="nav-badge danger hide-on-collapse" id="findingsBadge">0</span>
        </a>
        <a href="/resources" class="nav-item" data-page="resources">
            <span class="nav-icon"><i class="fas fa-database"></i></span>
            <span class="nav-label hide-on-collapse">Ресурсы</span>
        </a>
        <a href="/audit" class="nav-item" data-page="audit">
            <span class="nav-icon"><i class="fas fa-history"></i></span>
            <span class="nav-label hide-on-collapse">Аудит</span>
        </a>
        <a href="/access" class="nav-item" data-page="access">
            <span class="nav-icon"><i class="fas fa-lock"></i></span>
            <span class="nav-label hide-on-collapse">Доступ</span>
        </a>
        <a href="/scanners" class="nav-item" data-page="scanners">
            <span class="nav-icon"><i class="fas fa-microscope"></i></span>
            <span class="nav-label hide-on-collapse">Сканеры</span>
            <span class="nav-status hide-on-collapse" id="scannersStatus"></span>
        </a>
    </nav>
    
    <div class="sidebar-footer">
        <div class="user-info">
            <div class="user-avatar">👤</div>
            <span class="user-name hide-on-collapse">admin</span>
        </div>
        <div class="sidebar-actions hide-on-collapse">
            <button class="theme-toggle" onclick="toggleTheme()" title="Переключить тему">
                <i class="fas fa-moon" id="themeIcon"></i>
            </button>
            <button class="logout-btn" onclick="logout()" title="Выйти">
                <i class="fas fa-sign-out-alt"></i>
            </button>
        </div>
    </div>
</aside>
4. Базовый шаблон (base.html)
html
<!-- webui/templates/base.html -->
<!DOCTYPE html>
<html lang="ru" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}DCAP System{% endblock %}</title>
    
    <!-- Vendor CSS -->
    <link rel="stylesheet" href="/static/vendor/bootstrap/bootstrap.min.css">
    <link rel="stylesheet" href="/static/vendor/fontawesome/css/all.min.css">
    
    <!-- Main CSS -->
    <link rel="stylesheet" href="/static/css/main.css">
    
    {% block head %}{% endblock %}
</head>
<body>
    <div class="app">
        <!-- Sidebar -->
        {% include "components/sidebar.html" %}
        
        <!-- Main Content -->
        <main class="main-content" id="mainContent">
            <!-- Header -->
            <header class="page-header">
                <div class="header-left">
                    <nav aria-label="Breadcrumb">
                        <ol class="breadcrumb">
                            {% block breadcrumb %}
                            <li class="breadcrumb-item active">{{ page|default('Главная') }}</li>
                            {% endblock %}
                        </ol>
                    </nav>
                </div>
                <div class="header-right">
                    <span class="last-updated" id="lastUpdated">Обновлено: только что</span>
                    <button class="btn btn-sm btn-primary" onclick="refreshPage()">
                        <i class="fas fa-sync-alt"></i> Обновить
                    </button>
                </div>
            </header>
            
            <!-- Page Content -->
            <div class="page-content">
                {% block content %}{% endblock %}
            </div>
            
            <!-- Footer -->
            <footer class="page-footer">
                <span>DCAP System v3.0.0</span>
                <span class="footer-divider">|</span>
                <span id="footerTime"></span>
            </footer>
        </main>
    </div>
    
    <!-- Vendor JS -->
    <script src="/static/vendor/bootstrap/bootstrap.bundle.min.js"></script>
    <script src="/static/vendor/chart.js/chart.min.js"></script>
    
    <!-- Main JS -->
    <script src="/static/js/api.js"></script>
    <script src="/static/js/theme.js"></script>
    <script src="/static/js/main.js"></script>
    
    {% block scripts %}{% endblock %}
</body>
</html>
5. Дашборд (dashboard.html)
html
<!-- webui/templates/dashboard.html -->
{% extends "base.html" %}

{% block title %}DCAP — Дашборд{% endblock %}

{% block breadcrumb %}
<li class="breadcrumb-item active">Дашборд</li>
{% endblock %}

{% block content %}
<div class="dashboard">
    <!-- KPI Cards -->
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-icon" style="color: var(--color-primary); background: var(--color-primary-bg);">
                <i class="fas fa-database"></i>
            </div>
            <div class="kpi-content">
                <div class="kpi-value" id="kpiResources">—</div>
                <div class="kpi-label">Ресурсов</div>
                <div class="kpi-change" id="kpiResourcesChange"></div>
            </div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="color: var(--color-danger); background: var(--color-danger-bg);">
                <i class="fas fa-exclamation-triangle"></i>
            </div>
            <div class="kpi-content">
                <div class="kpi-value" id="kpiFindings">—</div>
                <div class="kpi-label">Находок</div>
                <div class="kpi-change" id="kpiFindingsChange"></div>
            </div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="color: var(--color-success); background: var(--color-success-bg);">
                <i class="fas fa-server"></i>
            </div>
            <div class="kpi-content">
                <div class="kpi-value" id="kpiAgents">—</div>
                <div class="kpi-label">Агентов онлайн</div>
                <div class="kpi-change" id="kpiAgentsChange"></div>
            </div>
        </div>
        <div class="kpi-card">
            <div class="kpi-icon" style="color: var(--color-warning); background: var(--color-warning-bg);">
                <i class="fas fa-bell"></i>
            </div>
            <div class="kpi-content">
                <div class="kpi-value" id="kpiAlerts">—</div>
                <div class="kpi-label">Алертов</div>
                <div class="kpi-change" id="kpiAlertsChange"></div>
            </div>
        </div>
    </div>
    
    <!-- Charts -->
    <div class="charts-grid">
        <div class="card chart-card">
            <div class="card-header">
                <h3 class="card-title"><i class="fas fa-chart-line"></i> Активность аудита</h3>
                <div class="card-actions">
                    <select class="filter-select" id="chartPeriod" onchange="updateChart(this.value)">
                        <option value="24h">24 часа</option>
                        <option value="7d" selected>7 дней</option>
                        <option value="30d">30 дней</option>
                    </select>
                </div>
            </div>
            <div class="card-body">
                <canvas id="auditChart" height="250"></canvas>
            </div>
        </div>
        <div class="card chart-card">
            <div class="card-header">
                <h3 class="card-title"><i class="fas fa-chart-pie"></i> Типы находок</h3>
            </div>
            <div class="card-body">
                <canvas id="findingsChart" height="250"></canvas>
            </div>
        </div>
    </div>
    
    <!-- Recent Events -->
    <div class="card">
        <div class="card-header">
            <h3 class="card-title"><i class="fas fa-clock"></i> Последние события аудита</h3>
            <a href="/audit" class="btn btn-sm btn-outline">Все события →</a>
        </div>
        <div class="card-body">
            <div class="table-container">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Время</th>
                            <th>Пользователь</th>
                            <th>Файл</th>
                            <th>Тип</th>
                            <th>Источник</th>
                        </tr>
                    </thead>
                    <tbody id="recentEvents">
                        <tr><td colspan="5" class="text-center text-muted">Загрузка...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/dashboard.js"></script>
<script>
    document.addEventListener('DOMContentLoaded', function() {
        loadDashboard();
        // Автообновление каждые 30 секунд
        setInterval(loadDashboard, 30000);
    });
</script>
{% endblock %}
6. JavaScript — theme.js
javascript
// webui/src/static/js/theme.js

/**
 * Переключение темы
 */
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('dcap-theme', newTheme);
    
    // Обновление иконки
    const icon = document.getElementById('themeIcon');
    if (icon) {
        icon.className = newTheme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
    }
}

/**
 * Инициализация темы
 */
function initTheme() {
    const savedTheme = localStorage.getItem('dcap-theme') || 'light';
    const html = document.documentElement;
    html.setAttribute('data-theme', savedTheme);
    
    const icon = document.getElementById('themeIcon');
    if (icon) {
        icon.className = savedTheme === 'light' ? 'fas fa-moon' : 'fas fa-sun';
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', initTheme);
7. JavaScript — main.js
javascript
// webui/src/static/js/main.js

/**
 * Переключение состояния сайдбара
 */
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');
    
    sidebar.classList.toggle('collapsed');
    mainContent.classList.toggle('expanded');
    
    localStorage.setItem('dcap-sidebar-collapsed', sidebar.classList.contains('collapsed') ? 'true' : 'false');
}

/**
 * Инициализация сайдбара
 */
function initSidebar() {
    const collapsed = localStorage.getItem('dcap-sidebar-collapsed') === 'true';
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');
    
    if (collapsed) {
        sidebar.classList.add('collapsed');
        mainContent.classList.add('expanded');
    }
}

/**
 * Обновление времени в футере
 */
function updateFooterTime() {
    const el = document.getElementById('footerTime');
    if (el) {
        el.textContent = new Date().toLocaleString('ru-RU');
    }
}

/**
 * Обновление страницы
 */
function refreshPage() {
    location.reload();
}

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    initSidebar();
    updateFooterTime();
    setInterval(updateFooterTime, 10000);
    
    // Подсветка активного пункта меню
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(item => {
        const href = item.getAttribute('href');
        if (href === currentPath || (href !== '/' && currentPath.startsWith(href))) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
});
8. JavaScript — dashboard.js
javascript
// webui/src/static/js/dashboard.js

let auditChartInstance = null;
let findingsChartInstance = null;

/**
 * Загрузка данных для дашборда
 */
async function loadDashboard() {
    try {
        // Загрузка статистики аудита
        const auditStats = await api.get('/api/audit/stats', { days: 7 });
        updateKPIs(auditStats);
        updateRecentEvents(auditStats);
        
        // Загрузка статистики находок
        const findingsStats = await api.get('/api/findings/stats');
        updateCharts(auditStats, findingsStats);
        
        // Загрузка статистики агентов
        const agents = await api.get('/api/audit/agents');
        updateAgentsStatus(agents);
        
    } catch (error) {
        console.error('Ошибка загрузки дашборда:', error);
    }
}

/**
 * Обновление KPI-карточек
 */
function updateKPIs(stats) {
    // Ресурсы
    document.getElementById('kpiResources').textContent = stats.resources || '—';
    // Находки
    document.getElementById('kpiFindings').textContent = stats.total || '—';
    // Алерты
    document.getElementById('kpiAlerts').textContent = stats.alerts || '—';
}

/**
 * Обновление графиков
 */
function updateCharts(auditStats, findingsStats) {
    // График аудита
    const ctx1 = document.getElementById('auditChart').getContext('2d');
    if (auditChartInstance) {
        auditChartInstance.destroy();
    }
    auditChartInstance = new Chart(ctx1, {
        type: 'line',
        data: {
            labels: auditStats.dates || [],
            datasets: [{
                label: 'События',
                data: auditStats.values || [],
                borderColor: getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim(),
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
    
    // Pie chart находок
    const ctx2 = document.getElementById('findingsChart').getContext('2d');
    if (findingsChartInstance) {
        findingsChartInstance.destroy();
    }
    findingsChartInstance = new Chart(ctx2, {
        type: 'doughnut',
        data: {
            labels: findingsStats.labels || ['PII', 'Credentials', 'Code'],
            datasets: [{
                data: findingsStats.values || [0, 0, 0],
                backgroundColor: [
                    getComputedStyle(document.documentElement).getPropertyValue('--color-danger').trim(),
                    getComputedStyle(document.documentElement).getPropertyValue('--color-warning').trim(),
                    getComputedStyle(document.documentElement).getPropertyValue('--color-info').trim()
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' }
            }
        }
    });
}

/**
 * Обновление списка последних событий
 */
function updateRecentEvents(stats) {
    const tbody = document.getElementById('recentEvents');
    const events = stats.recent || [];
    
    if (events.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Нет событий</td></tr>';
        return;
    }
    
    let html = '';
    for (const event of events) {
        const time = new Date(event.created_at).toLocaleString('ru-RU');
        const sourceIcon = getSourceIcon(event.event_source);
        const typeIcon = getTypeIcon(event.event_type);
        
        html += `
            <tr onclick="window.location.href='/audit'">
                <td>${time}</td>
                <td>${event.user || '—'}</td>
                <td class="text-truncate" style="max-width: 200px;">${event.file_path || '—'}</td>
                <td><span class="badge badge-${event.event_type}">${typeIcon} ${event.event_type}</span></td>
                <td>${sourceIcon} ${event.event_source || '—'}</td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

/**
 * Обновление статуса агентов
 */
function updateAgentsStatus(agents) {
    const online = agents.filter(a => a.status === 'online').length;
    const total = agents.length;
    document.getElementById('kpiAgents').textContent = online;
    document.getElementById('kpiAgentsChange').textContent = `из ${total}`;
    
    // Обновление статуса в сайдбаре
    const statusEl = document.getElementById('scannersStatus');
    if (statusEl) {
        statusEl.className = 'nav-status' + (online > 0 ? '' : ' offline');
    }
}

/**
 * Вспомогательные функции
 */
function getSourceIcon(source) {
    const icons = {
        'windows_agent': '🪟',
        'linux_agent': '🐧',
        'scanner': '📡',
        'api': '🔌',
        's3_agent': '☁️'
    };
    return icons[source] || '📋';
}

function getTypeIcon(type) {
    const icons = {
        'read': '📖',
        'write': '✏️',
        'delete': '🗑️',
        'move': '📦',
        'rename': '✏️'
    };
    return icons[type] || '📋';
}

/**
 * Обновление графика при смене периода
 */
function updateChart(period) {
    loadDashboard();
}
9. JavaScript — api.js
javascript
// webui/src/static/js/api.js

const API_BASE = '/api';

/**
 * Универсальный HTTP-клиент
 */
const api = {
    async get(endpoint, params = {}) {
        const url = new URL(endpoint, window.location.origin);
        Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
                url.searchParams.append(key, params[key]);
            }
        });
        
        const response = await fetch(url.toString());
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    },
    
    async post(endpoint, data = {}) {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    },
    
    async put(endpoint, data = {}) {
        const response = await fetch(endpoint, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    },
    
    async delete(endpoint) {
        const response = await fetch(endpoint, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    }
};
10. Обновление main.py
python
# webui/src/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import httpx
import os
import logging

from .core.config import load_config
from .core.logging import setup_logging

# Загрузка конфига
config = load_config()
setup_logging(config)

app = FastAPI(
    title="DCAP WebUI",
    version="3.0.0",
    description="Enterprise UI для DCAP System"
)

# Пути
BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "src" / "static"

# Статика
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Шаблоны
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Manager API URL
MANAGER_URL = config.get("manager", {}).get("url", "http://localhost:8000")

# ===== СТРАНИЦЫ =====

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "page": "Дашборд"}
    )

@app.get("/catalog", response_class=HTMLResponse)
async def catalog_page(request: Request):
    return templates.TemplateResponse(
        "catalog.html",
        {"request": request, "page": "Каталог"}
    )

@app.get("/findings", response_class=HTMLResponse)
async def findings_page(request: Request):
    return templates.TemplateResponse(
        "findings.html",
        {"request": request, "page": "Находки"}
    )

@app.get("/resources", response_class=HTMLResponse)
async def resources_page(request: Request):
    return templates.TemplateResponse(
        "resources.html",
        {"request": request, "page": "Ресурсы"}
    )

@app.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request):
    return templates.TemplateResponse(
        "audit.html",
        {"request": request, "page": "Аудит"}
    )

@app.get("/access", response_class=HTMLResponse)
async def access_page(request: Request):
    return templates.TemplateResponse(
        "access.html",
        {"request": request, "page": "Доступ"}
    )

@app.get("/scanners", response_class=HTMLResponse)
async def scanners_page(request: Request):
    return templates.TemplateResponse(
        "scanners.html",
        {"request": request, "page": "Сканеры"}
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "page": "Настройки"}
    )

# ===== API ПРОКСИ =====

@app.get("/api/audit/stats")
async def proxy_audit_stats(days: int = 7):
    """Прокси к статистике аудита"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{MANAGER_URL}/api/audit/stats", params={"days": days})
        return response.json()

@app.get("/api/audit")
async def proxy_audit_events(
    limit: int = 100,
    offset: int = 0,
    since: str = None,
    event_type: str = None,
    event_source: str = None,
    user: str = None,
    file_path: str = None
):
    """Прокси к событиям аудита"""
    params = {
        "limit": limit,
        "offset": offset
    }
    if since: params["since"] = since
    if event_type: params["event_type"] = event_type
    if event_source: params["event_source"] = event_source
    if user: params["user"] = user
    if file_path: params["file_path"] = file_path
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{MANAGER_URL}/api/audit", params=params)
        return response.json()

@app.get("/api/findings/stats")
async def proxy_findings_stats():
    """Прокси к статистике находок"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{MANAGER_URL}/api/findings/stats")
        return response.json()

@app.get("/api/audit/agents")
async def proxy_audit_agents():
    """Прокси к списку агентов"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{MANAGER_URL}/api/audit/agents")
        return response.json()

# ===== ЗАПУСК =====
if __name__ == "__main__":
    import uvicorn
    port = config.get("port", 8001)
    uvicorn.run(app, host="0.0.0.0", port=port)
11. config.json
json
{
    "port": 8001,
    "manager": {
        "url": "http://localhost:8000"
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
}
✅ КРИТЕРИИ ПРИЕМКИ
Структура
□ Все файлы созданы согласно структуре каталога
□ CSS разделен на компоненты и страницы
□ JavaScript разделен на модули
Дизайн
□ Единая цветовая схема (primary, secondary, success, danger, warning)
□ Боковое меню с иконками и активным состоянием
□ Карточки с тенями и hover-эффектами
□ Таблицы с сортировкой и чередованием цветов
□ Статусы (online/offline/pending) с цветными бейджами
□ KPI-карточки на дашборде с иконками
Функциональность
□ Переключение темной/светлой темы (сохраняется в localStorage)
□ Сворачивание/разворачивание бокового меню (сохраняется в localStorage)
□ Адаптивная верстка (mobile, tablet, desktop)
□ Навигация по всем разделам
□ Хлебные крошки для навигации
□ Даташборд с графиками (Chart.js)
□ Данные загружаются асинхронно (AJAX)
Производительность
□ Время загрузки < 2 секунд
□ Кэширование статики
Тестирование
□ Проверка в Chrome, Firefox, Safari
□ Проверка на мобильных устройствах (эмуляция)
□ Проверка переключения тем
□ Проверка всех ссылок и кнопок
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Запустить WebUI (новая структура)
cd webui
python -m src.main

# 3. Открыть http://localhost:8001

# 4. Проверить дашборд
# - KPI карточки отображают данные
# - Графики отображаются
# - Последние события загружаются

# 5. Проверить навигацию
# - Клик по пунктам меню → переход на страницы
# - Активный пункт подсвечен

# 6. Проверить тему
# - Клик по иконке 🌓 → переключение темы
# - Тема сохраняется после перезагрузки

# 7. Проверить сайдбар
# - Клик по ☰ → сворачивание
# - Состояние сохраняется после перезагрузки

# 8. Проверить адаптивность
# - Уменьшить окно браузера → меню сворачивается
# - На мобильном устройстве → меню скрыто, гамбургер-меню
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_28_webui_redesign
git add webui/
git commit -m "feat: День 28 — WebUI редизайн (Enterprise UI)

- Единая дизайн-система (CSS переменные, темы)
- Боковое меню с коллапсом
- KPI-карточки на дашборде
- Графики активности аудита и типов находок (Chart.js)
- Темная/светлая тема (localStorage)
- Адаптивная верстка (mobile-first)
- Структура компонентов для будущей стандартизации
- JavaScript модули (api, theme, dashboard, main)"
Разработчик (кодер), приступай! 🚀