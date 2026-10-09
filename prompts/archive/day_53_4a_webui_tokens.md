ТЗ: День 53.4a — WebUI-редизайн, этап 1: токены + base + компоненты
Файл: prompts/tz/day_53_4a_webui_tokens.md
Дата: 09.10.2026
Версия: v3.13.36 → v3.13.37
Статус: ✏️ Готово к разработке
Оценка: ~2–2.5 ч
Приоритет: 🔴 критично (BACKLOG-093, до GitHub-пакета; первый из 5 под-дней редизайна)
Родительская задача: BACKLOG-093 «WebUI-редизайн (Dovetail-style, DESIGN.md)»

🎯 ЦЕЛЬ

Перевести WebUI DCAP на тёмную тему Dovetail (`DESIGN.md`):
- тёмный command-center, Inter + JetBrains Mono, `#6798ff` единственный акцент;
- 8px радиусы, zero-shadow, grid-wireframe;
- все 14 страниц автоматически (через `base.html` и `components/*.css`);
- **без переписывания JS-логики и страниц** — они подхватят переменные.

Что НЕ входит в 53.4a:
- Переписывание контента страниц — 53.4b–53.4d.
- Палитра графиков Chart.js — 53.4d.
- `components/sidebar.css`, `cards.css`, `header.css`, `tables.css`, `forms.css`,
  `modals.css`, `badges.css` — не меняем (подхватят новые переменные).
- `findings.css` — не меняем (добавим `--font-mono` alias в `tokens.css`).
- Переход на stroke-SVG иконки — v3.1.0 (BACKLOG-101).
- Light-тема — v3.1.0 (BACKLOG-102).

📌 ПРЕДУСЛОВИЯ

- ✅ v3.13.36 закрыта, Manager/Scanner/S3 работают.
- ✅ WebUI запускается (`run_webui.py`, `:8001`, healthy).
- ✅ `DESIGN.md` — локально (в корне репо или `docs/DESIGN.md`).
- ✅ Кодер работает на той же машине (интернет есть, `curl` доступен).
- ✅ Unit-набор — 433 passed (не трогаем, но проверяем в конце).

📁 ФАЙЛЫ

Создаются:

| Файл | Назначение |
|------|------------|
| `webui/static/vendor/fonts/inter.woff2` | Inter Variable |
| `webui/static/vendor/fonts/inter.css` | `@font-face` для Inter |
| `webui/static/vendor/fonts/jetbrains-mono.woff2` | JetBrains Mono Variable |
| `webui/static/vendor/fonts/jetbrains-mono.css` | `@font-face` для JetBrains Mono |
| `webui/static/css/tokens.css` | CSS-переменные Dovetail (dark-only) |
| `webui/static/css/base.css` | глобальные стили, `@font-face`, скроллбар |
| `webui/static/css/components.css` | override Bootstrap-классов |
| `webui/static/css/grid-wireframe.css` | 1px `#1e1e1e` grid на `body::before` |

Изменяются:

| Файл | Что |
|------|-----|
| `webui/templates/base.html` | убрать `data-theme="light"`, добавить `<link>` на новые CSS, убрать `theme.js` + кнопку темы |
| `webui/templates/login.html` | убрать `data-theme="light"`, убрать inline-`<style>`, добавить `<link>` |
| `webui/static/css/main.css` | убрать `@import 'variables.css'` и `'theme-dark.css'`, добавить `@import 'tokens.css'`, `'base.css'`, `'components.css'`, `'grid-wireframe.css'` |

Удаляются:

| Файл | Почему |
|------|--------|
| `webui/static/css/variables.css` | всё перенесено в `tokens.css` |
| `webui/static/css/theme-dark.css` | dark-only, отдельный файл не нужен |
| `webui/static/js/theme.js` | переключателя темы больше нет |

🔧 ДЕТАЛЬНОЕ ТЗ

TASK-141 — Шрифты (`curl`)

```bash
cd webui/static/vendor
mkdir -p fonts
cd fonts

# Inter Variable
curl -L -o inter.woff2 \
  "https://cdn.jsdelivr.net/gh/rsms/inter@master/docs/font-files/InterVariable.woff2"

# JetBrains Mono Variable
curl -L -o jetbrains-mono.woff2 \
  "https://cdn.jsdelivr.net/gh/JetBrains/JetBrainsMono@master/fonts/variable/JetBrainsMono[wght].woff2"
⚠️ Если URL не работает (CDN блокируется) — использовать Google Fonts Fontsource:

bash
curl -L -o inter.woff2 \
  "https://cdn.jsdelivr.net/npm/@fontsource-variable/inter@latest/files/inter-latin-wght-normal.woff2"

curl -L -o jetbrains-mono.woff2 \
  "https://cdn.jsdelivr.net/npm/@fontsource-variable/jetbrains-mono@latest/files/jetbrains-mono-latin-wght-normal.woff2"
Проверка размера:

powershell
ls webui\static\vendor\fonts\
# Ожидание: inter.woff2 ~300-400 KB, jetbrains-mono.woff2 ~100-150 KB
Создать webui/static/vendor/fonts/inter.css:

css
@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-display: swap;
    font-weight: 100 900;
    src: url('./inter.woff2') format('woff2-variations');
    unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA,
                   U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+2074, U+20AC,
                   U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}
Создать webui/static/vendor/fonts/jetbrains-mono.css:

css
@font-face {
    font-family: 'JetBrains Mono';
    font-style: normal;
    font-display: swap;
    font-weight: 100 800;
    src: url('./jetbrains-mono.woff2') format('woff2-variations');
    unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA,
                   U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+2074, U+20AC,
                   U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}
TASK-142 — tokens.css (новый)

Полный код:

css
/* DCAP WebUI — tokens.css
 * Design system Dovetail (dark-only).
 * Заменяет variables.css + theme-dark.css (v3.13.37).
 *
 * ⚠️ Имена переменных сохранены как в variables.css (--color-bg, --color-text,
 * --color-surface, --color-border, --color-primary и т.д.), чтобы
 * components/*.css подхватили новые значения АВТОМАТИЧЕСКИ.
 */

:root {
    /* ============================================================
     * ДИЗАЙН-ТОКЕНЫ DOVETAIL (dark-only)
     * ============================================================ */

    /* Цвета */
    --color-blue-cornflower: #6798ff;   /* единственный акцент */
    --color-page-ink:        #0a0a0a;   /* canvas */
    --color-card-carbon:     #1e1e1e;   /* card surface */
    --color-deep-coal:       #141414;   /* alternate surface */
    --color-onyx:            #000000;   /* SVG fills */
    --color-steel-border:    #313131;   /* hairline borders */
    --color-graphite:        #454545;   /* outline button borders */
    --color-fog:             #7c7c7c;   /* disabled */
    --color-ash:             #a7a7a7;   /* secondary text */
    --color-snow:            #ffffff;   /* primary text */

    /* Типографика — семейства */
    --font-inter: 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
                  "Segoe UI", Roboto, sans-serif;
    --font-jetbrains-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo,
                           Monaco, Consolas, monospace;
    /* Alias для findings.css */
    --font-mono: var(--font-jetbrains-mono);

    /* Типографика — размеры */
    --text-caption:     12px;
    --leading-caption:  1.4;
    --tracking-caption: 0.85px;

    --text-body-sm:     14px;
    --leading-body-sm:  1.5;
    --tracking-body-sm: -0.17px;

    --text-body:        16px;
    --leading-body:     1.5;
    --tracking-body:    -0.19px;

    --text-subheading:     20px;
    --leading-subheading:  1.4;
    --tracking-subheading: -0.42px;

    --text-heading-sm:     24px;
    --leading-heading-sm:  1.33;
    --tracking-heading-sm: -0.5px;

    --text-heading:        40px;
    --leading-heading:     1.2;
    --tracking-heading:    -0.84px;

    --text-heading-lg:     56px;
    --leading-heading-lg:  1.14;
    --tracking-heading-lg: -2.02px;

    --text-display:        64px;
    --leading-display:     1.13;
    --tracking-display:    -2.3px;

    /* Spacing (базовый unit 8px) */
    --spacing-8:   8px;
    --spacing-16:  16px;
    --spacing-24:  24px;
    --spacing-32:  32px;
    --spacing-40:  40px;
    --spacing-64:  64px;
    --spacing-96:  96px;
    --spacing-200: 200px;

    /* Радиусы (Dovetail) */
    --radius-tags:    4px;
    --radius-cards:   8px;
    --radius-inputs:  8px;
    --radius-buttons: 8px;

    /* Layout */
    --page-max-width: 1200px;
    --section-gap:    64px;
    --card-padding:   24px;
    --element-gap:    16px;

    /* ============================================================
     * LEGACY-АЛИАСЫ (сохранены под components/*.css)
     * ============================================================ */

    /* Цвета — surface */
    --color-bg:              var(--color-page-ink);
    --color-surface:         var(--color-card-carbon);
    --color-bg-elevated:     var(--color-deep-coal);

    /* Цвета — text */
    --color-text:            var(--color-snow);
    --color-text-secondary:  var(--color-ash);
    --color-text-muted:      var(--color-fog);
    --color-text-disabled:   var(--color-fog);

    /* Цвета — border */
    --color-border:          var(--color-steel-border);
    --color-border-hover:    var(--color-graphite);
    --color-border-subtle:   var(--color-card-carbon);

    /* Цвета — primary / accent */
    --color-primary:         var(--color-blue-cornflower);
    --color-primary-dark:    #4d7de6;
    --color-primary-light:   #98b8ff;
    --color-primary-bg:      #1a1f2e;      /* намёк на синий на тёмном */

    /* Семантика (приглушённая) */
    --color-success:      #4ea87a;
    --color-success-bg:   #1a2a20;
    --color-warning:      #b8974a;
    --color-warning-bg:   #2a2418;
    --color-danger:       #d67272;
    --color-danger-bg:    #2a1a1a;
    --color-info:         var(--color-blue-cornflower);
    --color-info-bg:      #1a1f2e;

    /* Тени — ЗАПРЕЩЕНЫ в Dovetail. Оставлены пустыми для совместимости. */
    --shadow-sm: none;
    --shadow-md: none;
    --shadow-lg: none;
    --shadow-xl: none;

    /* Legacy spacing (используются в components/*.css) */
    --spacing-1: 4px;
    --spacing-2: 8px;
    --spacing-3: 12px;
    --spacing-4: 16px;
    --spacing-5: 20px;
    --spacing-6: 24px;

    /* Legacy radius */
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 8px;
    --radius-xl: 8px;
    --radius-full: 9999px;

    /* Legacy font-family */
    --font-family: var(--font-inter);

    /* Legacy font-size */
    --font-size-xs:  12px;
    --font-size-sm:  14px;
    --font-size-md:  16px;
    --font-size-lg:  20px;
    --font-size-xl:  24px;
    --font-size-2xl: 40px;

    /* Транзишены */
    --transition-fast: 150ms ease;
    --transition-base: 250ms ease;
    --transition-slow: 400ms ease;

    /* Sidebar / header */
    --sidebar-width:           240px;
    --sidebar-collapsed-width:  64px;
    --header-height:            56px;
}

html {
    color-scheme: dark;
}
TASK-143 — base.css (новый)

css
/* DCAP WebUI — base.css
 * Глобальные стили, шрифты, скроллбар. Применяется ко всем страницам.
 */

@import url('/static/vendor/fonts/inter.css');
@import url('/static/vendor/fonts/jetbrains-mono.css');

* { margin: 0; padding: 0; box-sizing: border-box; }

html, body {
    height: 100%;
    font-family: var(--font-inter);
    font-size: var(--text-body-sm);
    line-height: var(--leading-body-sm);
    letter-spacing: var(--tracking-body-sm);
    font-weight: 400;
    background: var(--color-page-ink);
    color: var(--color-snow);
    transition: background var(--transition-base), color var(--transition-base);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* Заголовки — Inter 600, negative tracking */
h1, h2, h3, h4, h5, h6 {
    font-family: var(--font-inter);
    font-weight: 600;
    color: var(--color-snow);
    letter-spacing: var(--tracking-heading-sm);
    line-height: var(--leading-heading-sm);
    margin-bottom: var(--spacing-16);
}

h1 { font-size: var(--text-heading);      letter-spacing: var(--tracking-heading);      line-height: var(--leading-heading); }
h2 { font-size: var(--text-heading-sm);   letter-spacing: var(--tracking-heading-sm); }
h3 { font-size: var(--text-subheading);   letter-spacing: var(--tracking-subheading); }
h4 { font-size: var(--text-body);         letter-spacing: var(--tracking-body); }
h5, h6 { font-size: var(--text-body-sm);  letter-spacing: var(--tracking-body-sm); }

/* Ссылки — accent */
a {
    color: var(--color-blue-cornflower);
    text-decoration: none;
    transition: color var(--transition-fast);
}
a:hover { color: var(--color-primary-light); }

/* Code / mono */
code, pre, kbd, samp {
    font-family: var(--font-jetbrains-mono);
    font-size: 0.9em;
    background: var(--color-deep-coal);
    padding: 1px 4px;
    border-radius: var(--radius-tags);
    color: var(--color-snow);
}

/* Скроллбар */
::-webkit-scrollbar        { width: 8px; height: 8px; }
::-webkit-scrollbar-track  { background: var(--color-page-ink); }
::-webkit-scrollbar-thumb  { background: var(--color-steel-border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--color-graphite); }

/* Form controls (override Bootstrap) */
select, input, textarea {
    background: var(--color-deep-coal) !important;
    color: var(--color-snow) !important;
    border-color: var(--color-steel-border) !important;
}
select option { background: var(--color-card-carbon); color: var(--color-snow); }

/* Selection */
::selection { background: var(--color-blue-cornflower); color: var(--color-page-ink); }
TASK-144 — components.css (новый)

css
/* DCAP WebUI — components.css
 * Override Bootstrap-компонентов под Dovetail (dark-only).
 * Bootstrap 5.x. CSS-переменные --bs-* переопределены там, где возможно;
 * иначе — прямые правила.
 */

/* ============================================================
 * Bootstrap CSS variables (5.3+, безопасно для 5.0–5.2)
 * ============================================================ */
:root {
    --bs-body-bg:        var(--color-page-ink);
    --bs-body-color:     var(--color-snow);
    --bs-border-color:   var(--color-steel-border);
    --bs-primary:        var(--color-blue-cornflower);
    --bs-link-color:     var(--color-blue-cornflower);
    --bs-link-hover-color: var(--color-primary-light);
    --bs-secondary-color: var(--color-ash);
    --bs-emphasis-color: var(--color-snow);
}

/* ============================================================
 * Кнопки
 * ============================================================ */
.btn {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-8);
    padding: 10px 16px;
    border-radius: var(--radius-buttons);
    font-family: var(--font-inter);
    font-size: 14px;
    font-weight: 500;
    line-height: 1;
    letter-spacing: var(--tracking-body-sm);
    border: 1px solid transparent;
    cursor: pointer;
    transition: background var(--transition-fast), border-color var(--transition-fast),
                color var(--transition-fast);
    box-shadow: none;
}

/* Primary — dark carbon (не blue!) */
.btn-primary {
    background: var(--color-card-carbon);
    color: var(--color-snow);
    border-color: var(--color-steel-border);
}
.btn-primary:hover, .btn-primary:focus {
    background: var(--color-deep-coal);
    border-color: var(--color-graphite);
    color: var(--color-snow);
}

/* Secondary / outline */
.btn-outline-secondary,
.btn-outline-primary {
    background: transparent;
    border: 1px solid var(--color-graphite);
    color: var(--color-snow);
}
.btn-outline-secondary:hover,
.btn-outline-primary:hover {
    background: var(--color-deep-coal);
    border-color: var(--color-ash);
    color: var(--color-snow);
}

.btn-outline-danger {
    background: transparent;
    border: 1px solid var(--color-danger);
    color: var(--color-danger);
}
.btn-outline-danger:hover {
    background: var(--color-danger-bg);
    color: var(--color-danger);
}

/* Danger solid */
.btn-danger {
    background: var(--color-danger);
    color: var(--color-snow);
    border-color: transparent;
}
.btn-danger:hover { background: #b85a5a; }

.btn-success {
    background: var(--color-success);
    color: var(--color-snow);
    border-color: transparent;
}
.btn-success:hover { background: #3f8862; }

/* Размеры */
.btn-sm { padding: 6px 10px; font-size: 12px; }
.btn-lg { padding: 12px 20px; font-size: 16px; }
.btn-link { background: none; border: none; color: var(--color-blue-cornflower); padding: 0; }
.btn-link:hover { color: var(--color-primary-light); text-decoration: underline; }

/* ============================================================
 * Карточки
 * ============================================================ */
.card {
    background: var(--color-card-carbon);
    border: 1px solid var(--color-card-carbon);
    border-radius: var(--radius-cards);
    box-shadow: none;
    color: var(--color-snow);
    margin-bottom: var(--spacing-16);
}
.card-header {
    background: transparent;
    border-bottom: 1px solid var(--color-steel-border);
    padding: 16px 24px;
    color: var(--color-snow);
    font-weight: 600;
}
.card-body   { padding: 24px; color: var(--color-snow); }
.card-footer { background: transparent; border-top: 1px solid var(--color-steel-border); padding: 16px 24px; }
.card-title  { color: var(--color-snow); font-weight: 600; }

/* ============================================================
 * Формы
 * ============================================================ */
.form-control, .form-select {
    background: var(--color-deep-coal);
    color: var(--color-snow);
    border: 1px solid var(--color-steel-border);
    border-radius: var(--radius-inputs);
    padding: 8px 12px;
    font-family: var(--font-inter);
    font-size: 14px;
    transition: border-color var(--transition-fast);
}
.form-control:focus, .form-select:focus {
    background: var(--color-deep-coal);
    color: var(--color-snow);
    border-color: var(--color-blue-cornflower);
    box-shadow: 0 0 0 3px rgba(103, 152, 255, 0.15);
    outline: none;
}
.form-control::placeholder { color: var(--color-fog); }
.form-label { color: var(--color-ash); font-size: 13px; margin-bottom: 4px; }
.form-text  { color: var(--color-fog); font-size: 12px; }
.form-check-input {
    background: var(--color-deep-coal);
    border-color: var(--color-graphite);
}
.form-check-input:checked {
    background-color: var(--color-blue-cornflower);
    border-color: var(--color-blue-cornflower);
}
.form-check-label { color: var(--color-snow); }

/* ============================================================
 * Modal
 * ============================================================ */
.modal {
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(2px);
}
.modal-content {
    background: var(--color-card-carbon);
    border: 1px solid var(--color-steel-border);
    border-radius: var(--radius-cards);
    color: var(--color-snow);
    box-shadow: none;
}
.modal-header {
    border-bottom: 1px solid var(--color-steel-border);
    padding: 16px 24px;
}
.modal-header h3 { font-size: var(--text-subheading); margin: 0; }
.modal-body   { padding: 24px; }
.modal-footer { border-top: 1px solid var(--color-steel-border); padding: 16px 24px; }

/* ============================================================
 * Badge
 * ============================================================ */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: var(--radius-tags);
    font-size: 11px;
    font-weight: 500;
    line-height: 1.4;
    letter-spacing: 0.4px;
}
.badge-primary, .bg-primary    { background: var(--color-blue-cornflower); color: var(--color-page-ink); }
.badge-secondary, .bg-secondary{ background: var(--color-graphite);        color: var(--color-snow); }
.badge-success, .bg-success    { background: var(--color-success);          color: var(--color-snow); }
.badge-warning, .bg-warning    { background: var(--color-warning);          color: var(--color-page-ink); }
.badge-danger, .bg-danger      { background: var(--color-danger);           color: var(--color-snow); }
.badge-info, .bg-info          { background: var(--color-info);             color: var(--color-page-ink); }
.badge-light, .bg-light        { background: var(--color-deep-coal);        color: var(--color-ash); }

/* ============================================================
 * Таблицы
 * ============================================================ */
.table {
    color: var(--color-snow);
    border-color: var(--color-steel-border);
}
.table thead th {
    background: var(--color-deep-coal);
    color: var(--color-ash);
    border-bottom: 1px solid var(--color-steel-border);
    font-weight: 500;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 10px 12px;
}
.table tbody td {
    border-top: 1px solid var(--color-steel-border);
    padding: 10px 12px;
    color: var(--color-snow);
}
.table tbody tr:hover { background: var(--color-deep-coal); }
.table-striped tbody tr:nth-of-type(odd) { background: rgba(255, 255, 255, 0.02); }

/* ============================================================
 * Alert
 * ============================================================ */
.alert {
    padding: 12px 16px;
    border-radius: var(--radius-cards);
    border: 1px solid var(--color-steel-border);
    background: var(--color-deep-coal);
    color: var(--color-snow);
    margin-bottom: 16px;
}
.alert-danger  { border-color: var(--color-danger);  background: var(--color-danger-bg); }
.alert-warning { border-color: var(--color-warning); background: var(--color-warning-bg); }
.alert-info    { border-color: var(--color-info);    background: var(--color-info-bg); }
.alert-success { border-color: var(--color-success); background: var(--color-success-bg); }

/* ============================================================
 * Dropdown / nav
 * ============================================================ */
.dropdown-menu {
    background: var(--color-card-carbon);
    border: 1px solid var(--color-steel-border);
    border-radius: var(--radius-cards);
}
.dropdown-item { color: var(--color-snow); }
.dropdown-item:hover { background: var(--color-deep-coal); color: var(--color-snow); }

/* ============================================================
 * Pagination
 * ============================================================ */
.page-link {
    background: var(--color-deep-coal);
    color: var(--color-snow);
    border-color: var(--color-steel-border);
}
.page-link:hover {
    background: var(--color-card-carbon);
    color: var(--color-blue-cornflower);
    border-color: var(--color-steel-border);
}
.page-item.active .page-link {
    background: var(--color-blue-cornflower);
    border-color: var(--color-blue-cornflower);
    color: var(--color-page-ink);
}
.page-item.disabled .page-link {
    background: var(--color-deep-coal);
    color: var(--color-fog);
    border-color: var(--color-steel-border);
}

/* ============================================================
 * Progress
 * ============================================================ */
.progress { background: var(--color-deep-coal); border-radius: 8px; height: 8px; overflow: hidden; }
.progress-bar { background: var(--color-blue-cornflower); }

/* ============================================================
 * Utilities
 * ============================================================ */
.text-muted { color: var(--color-ash) !important; }
.text-secondary { color: var(--color-ash) !important; }
.text-body { color: var(--color-snow) !important; }
.border { border-color: var(--color-steel-border) !important; }
.bg-body { background: var(--color-page-ink) !important; }
.bg-light { background: var(--color-deep-coal) !important; }
.bg-white { background: var(--color-card-carbon) !important; }
TASK-145 — grid-wireframe.css (новый)

css
/* DCAP WebUI — grid-wireframe.css
 * Тонкая сетка 1px #1e1e1e на фоне #0a0a0a — blueprint-мотив Dovetail.
 * Рисуется через body::before, не мешает контенту (z-index: -1).
 */

body::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    background-image:
        repeating-linear-gradient(
            to right,
            #1e1e1e 0,
            #1e1e1e 1px,
            transparent 1px,
            transparent 40px
        ),
        repeating-linear-gradient(
            to bottom,
            #1e1e1e 0,
            #1e1e1e 1px,
            transparent 1px,
            transparent 40px
        );
    opacity: 0.6;
}

/* Контент — поверх сетки */
.app, .main-content, .sidebar {
    position: relative;
    z-index: 1;
}
TASK-146 — base.html (правки)

Найти:

html
<html lang="ru" data-theme="light">
Заменить на:

html
<html lang="ru" data-theme="dark">
В <head> после bootstrap.min.css и fontawesome.min.css добавить:

html
    <link rel="stylesheet" href="/static/css/tokens.css">
    <link rel="stylesheet" href="/static/css/base.css">
    <link rel="stylesheet" href="/static/css/components.css">
    <link rel="stylesheet" href="/static/css/grid-wireframe.css">
Порядок важен: Bootstrap → FA → tokens → base → components → grid-wireframe → main.css.

Найти в сайдбаре (в .sidebar-actions):

html
<button onclick="toggleTheme()" title="Тема"><i class="fas fa-moon" id="themeIcon"></i></button>
Заменить на заглушку (кнопка убирается или остаётся только logout):

html
<button onclick="Auth && Auth.logout()" title="Выход"><i class="fas fa-sign-out-alt"></i></button>
Найти в конце <body>:

html
<script src="/static/js/theme.js"></script>
Удалить строку.

TASK-147 — login.html (правки)

Найти:

html
<html lang="ru" data-theme="light">
Заменить на:

html
<html lang="ru" data-theme="dark">
В <head> добавить после fontawesome.min.css:

html
    <link rel="stylesheet" href="/static/css/tokens.css">
    <link rel="stylesheet" href="/static/css/base.css">
    <link rel="stylesheet" href="/static/css/components.css">
    <link rel="stylesheet" href="/static/css/grid-wireframe.css">
Найти inline-<style> в <head>:

html
<style>
    body.login-body { ... }
    .login-card { ... }
    ...
</style>
Заменить на:

html
<style>
    body.login-body {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--color-page-ink);
    }
    .login-card {
        width: 100%;
        max-width: 400px;
        border-radius: var(--radius-cards);
        box-shadow: none;
    }
    .login-card .card-header {
        border-bottom: 1px solid var(--color-steel-border);
        text-align: center;
        padding: 32px 24px 16px;
        background: transparent;
    }
    .login-card .card-header h4 { margin-bottom: 4px; color: var(--color-snow); }
    .login-card .card-body { padding: 16px 32px 32px; }
    #modeBadge { font-size: 0.8rem; }
</style>
TASK-148 — main.css (правки)

Найти:

css
@import 'variables.css';
@import 'theme-dark.css';
@import 'components/sidebar.css';
Заменить на:

css
@import 'tokens.css';
@import 'base.css';
@import 'components.css';
@import 'grid-wireframe.css';
@import 'components/sidebar.css';
Удалить из main.css верхнеуровневые правила, которые теперь в base.css:

* { margin: 0; ... }

html, body { height: 100%; ... }

a { color: var(--color-primary); ... }

a:hover { ... }

code { background: var(--color-bg); ... }

select, input, textarea { ... } (перенесено в base.css)

Оставить в main.css: .app, .main-content, .page-content, .btn (можно убрать — override в components.css), .text-center, .text-muted, @media.

Проверить, что .btn-primary в main.css не конфликтует с новым .btn-primary (dark carbon) — если конфликтует, удалить правило .btn-primary из main.css, оно теперь в components.css.

TASK-149 — удалить файлы

bash
git rm webui/static/css/variables.css
git rm webui/static/css/theme-dark.css
git rm webui/static/js/theme.js
🧪 КРИТЕРИИ ПРИЁМКИ

#	Критерий	Проверка
1	webui/static/vendor/fonts/ содержит inter.woff2 + inter.css + jetbrains-mono.woff2 + jetbrains-mono.css	ls
2	tokens.css, base.css, components.css, grid-wireframe.css созданы	ls
3	variables.css, theme-dark.css, theme.js удалены	git status
4	base.html: data-theme="dark", новые <link>, нет theme.js, нет кнопки темы	grep
5	login.html: data-theme="dark", новые <link>	grep
6	main.css: импорты обновлены	grep
7	Login-страница тёмная	ручная (browser)
8	Все 14 страниц тёмные (dashboard, findings, catalog, ...)	ручная
9	Кнопка «Выход» в сайдбаре работает	ручная
10	Формы, модалки, таблицы — тёмные, без белых пятен	ручная
11	Шрифт — Inter (не системный)	DevTools → Computed
12	code, pre — JetBrains Mono	DevTools
13	Unit-набор — 433 passed	pytest tests/unit/ -q
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ

Проверить файлы:

powershell
ls webui\static\vendor\fonts\
ls webui\static\css\
Проверить, что variables.css, theme-dark.css, theme.js удалены:

powershell
git status
Перезапустить WebUI (если нужно):

powershell
# Если WebUI в Docker:
docker compose restart webui

# Если run_webui.py — Ctrl+C и заново:
python run_webui.py
Открыть login:

text
http://localhost:8001/login
Ожидание: тёмный фон (#0a0a0a), карточка #1e1e1e, шрифт Inter, акцент #6798ff на ссылке (если есть). Никаких белых пятен.

Войти и проверить все страницы:

/ (dashboard)

/catalog

/findings

/false-positives

/resources

/audit

/access

/scanners

/users (если admin)

/roles (если admin)

/settings (если admin)

/findings/{id} (детали находки)

Ожидание: все тёмные. Сайдбар #1e1e1e, активный пункт с #6798ff акцентом. Кнопки #1e1e1e. Формы #141414.

Открыть DevTools → Computed для body:

Ожидание: font-family: Inter, ui-sans-serif, ... (не system-ui как fallback).

Проверить code/pre:

Ожидание: font-family: JetBrains Mono, ....

Скриншот (для отчёта): login + dashboard + findings + resources.

Unit-набор:

powershell
pytest tests/unit/ -q
Ожидание: 433 passed.

📝 СВОДКА ПРАВОК

#	Файл	Действие
1	webui/static/vendor/fonts/inter.woff2	Создан (curl)
2	webui/static/vendor/fonts/inter.css	Создан
3	webui/static/vendor/fonts/jetbrains-mono.woff2	Создан (curl)
4	webui/static/vendor/fonts/jetbrains-mono.css	Создан
5	webui/static/css/tokens.css	Создан
6	webui/static/css/base.css	Создан
7	webui/static/css/components.css	Создан
8	webui/static/css/grid-wireframe.css	Создан
9	webui/templates/base.html	Изменён
10	webui/templates/login.html	Изменён
11	webui/static/css/main.css	Изменён
12	webui/static/css/variables.css	Удалён
13	webui/static/css/theme-dark.css	Удалён
14	webui/static/js/theme.js	Удалён
⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ

Контент страниц (dashboard, findings, catalog, ...) не переделывается — они подхватят новые переменные, но их внутренняя разметка останется прежней. Детализация — 53.4b–53.4d.

Chart.js — не трогаем (палитра графиков — 53.4d). На тёмной теме графики могут «выпадать» (дефолтная Chart.js-палитра не под Dovetail) — это ожидаемо для 53.4a, починим в 53.4d.

Grid-wireframe — тонкая сетка (3% контраста). Если визуально не видно — усилить до #161616 (в 53.4e при полировке).

--shadow-sm/md/lg/xl = none — все тени удалены. Если что-то «потеряет глубину» — это ожидаемо (Dovetail: zero-shadow, поверхности разделяются тоном).

--color-primary = #6798ff (cornflower) — используется на ссылках, акцентах. Кнопки .btn-primary теперь #1e1e1e, а не синие — это правило Dovetail.

Иконки FA — остаются как есть (переход на stroke-SVG — BACKLOG-101).

📋 ОТКРЫТЫЕ ВОПРОСЫ

data-theme="dark" в <html> — оставляем для совместимости (если когда-то вернём light-тему). Или убираем совсем?
Решение: оставляем data-theme="dark" — на будущее.

Bootstrap 5.3 — если в нём есть --bs-* переменные, override через них (в components.css уже сделано).

vendor/fonts/ — размер репо +~1 МБ. Приемлемо.

⚠️ ЧТО НЕ ДЕЛАЕМ

Не переделываем components/sidebar.css, cards.css, header.css, tables.css, forms.css, modals.css, badges.css — подхватят переменные.

Не трогаем findings.css — добавили --font-mono alias.

Не трогаем JS-логику (api.js, auth.js, dashboard.js, findings.js, ...).

Не трогаем Chart.js палитру.

Не трогаем страницы (dashboard.html, findings.html, ...).

Не меняем Bootstrap/FA-библиотеки (только override).

Не трогаем webui/main.py, webui/api/routes.py.

💾 КОМАНДА ДЛЯ КОММИТА

bash
git checkout -b feature/day_53_4a_webui_tokens

git add webui/static/vendor/fonts/ \
        webui/static/css/tokens.css \
        webui/static/css/base.css \
        webui/static/css/components.css \
        webui/static/css/grid-wireframe.css \
        webui/templates/base.html \
        webui/templates/login.html \
        webui/static/css/main.css \
        STATE.md CHANGELOG.md ROADMAP.md \
        prompts/reports/day_53_4a_report.md

git rm webui/static/css/variables.css \
       webui/static/css/theme-dark.css \
       webui/static/js/theme.js

git commit -m "feat: День 53.4a — WebUI-редизайн, этап 1: токены + base + компоненты (v3.13.37)

- webui/static/vendor/fonts/ — Inter Variable + JetBrains Mono Variable (локально, CDN запрещён)
- webui/static/css/tokens.css — CSS-переменные Dovetail (dark-only):
  page ink #0a0a0a, card #1e1e1e, cornflower #6798ff, ash #a7a7a7,
  Inter + JetBrains Mono, tracking -0.17…-2.3px, 8px радиусы, zero-shadow
- webui/static/css/base.css — глобальные стили, @font-face, скроллбар
- webui/static/css/components.css — override Bootstrap (btn/card/form/modal/badge/table/alert)
- webui/static/css/grid-wireframe.css — 1px #1e1e1e grid на body::before
- webui/templates/base.html + login.html — data-theme='dark', новые <link>
- webui/static/css/main.css — импорты обновлены
- удалены: variables.css, theme-dark.css, theme.js

BACKLOG-093 (этап 1/5)
docs: обновлены STATE.md (v3.13.37), CHANGELOG.md, ROADMAP.md"
📊 ОБНОВЛЕНИЕ ПЛАНА

День	Задача	Статус
53.4a	WebUI-редизайн (этап 1)	🔄 В РАБОТЕ
53.4b	login, dashboard, resources, findings	📋
53.4c	finding_detail, catalog, audit, scanners, access	📋
53.4d	roles, users, settings, footer, графики	📋
53.4e	полировка, скриншоты, docs/DESIGN.md	📋
55	GitHub-пакет — после 53.4e	📋
📌 ПОСЛЕ ВЫПОЛНЕНИЯ

Обновить STATE.md: версия v3.13.37, следующий шаг — 53.4b.

Обновить CHANGELOG.md — секция [3.13.37].

Обновить ROADMAP.md — 53.4a ✅.

Переместить ТЗ в prompts/archive/day_53_4a_webui_tokens.md.

Отчёт — prompts/reports/day_53_4a_report.md:

список созданных/удалённых файлов,

скриншоты (login, dashboard, findings, resources),

подтверждение, что все 14 страниц тёмные,

pytest tests/unit/ -q — 433 passed.

Автор ТЗ: архитектор
Дата: 09.10.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.37 — WebUI в тёмной теме Dovetail (14 страниц), Inter + JetBrains Mono, 8px радиусы, zero-shadow, grid-wireframe.