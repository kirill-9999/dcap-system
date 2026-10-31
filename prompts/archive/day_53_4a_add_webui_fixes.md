ТЗ: День 53.4a-доп — WebUI-редизайн, фиксы регрессий и UX
Файл: prompts/tz/day_53_4a_add_webui_fixes.md
Дата: 10.10.2026
Версия: v3.13.37 → v3.13.38
Статус: ✏️ Готово к разработке
Оценка: ~2–2.5 ч
Приоритет: 🔴 критично (закрывает приёмку 53.4a, блокирует 53.4b)
Родительская задача: BACKLOG-093 «WebUI-редизайн (Dovetail-style, DESIGN.md)», день 53.4a

🎯 ЦЕЛЬ
Закрыть три дефекта, найденных при приёмке 53.4a:

BUG-139 — Font Awesome webfonts/ пуст → иконки рендерятся как цветные emoji, sidebar не соответствует Dovetail.

BUG-138 — finding_detail.js:137 содержит onerror="..." с </div> внутри HTML-атрибута → браузер рвёт атрибут → SyntaxError: missing ) after argument list в Console на /findings/{id}.

BUG-140 — Reveal-логика в finding_detail.js:

для image_region (OCR PNG) кнопка reveal бессмысленна — PNG уже показывает оригинал;

#fragment перезаписывается насовсем — вернуться к исходной картинке нельзя;

кнопка не блокируется после успеха → спам audit_logs (finding_reveal при каждом клике);

line_text и match_text дублируются в выводе;

bg-light — белое пятно на тёмной теме (Dovetail-нарушение).

Что НЕ входит в 53.4a-доп:

Переписывание разметки страниц — 53.4b–53.4d.

Качество детекции (finding 2043 — FP presidio person="Дата") — TEST-NOTE-10.15, отдельный день.

Chart.js палитра — 53.4d.

components/*.css — не трогаем.

Переход на stroke-SVG — BACKLOG-101 (v3.1.0).

📌 ПРЕДУСЛОВИЯ
✅ 53.4a (v3.13.37) закрыт по 13 критериям ТЗ.

✅ webui/static/vendor/webfonts/ — пусто (баг BUG-139), нужно наполнить.

✅ WebUI в Docker (dcap-webui:3.13.37, healthy) — пересборка обязательна после правок.

✅ Kaspersky-инжект отключён (иначе маскирует ошибки).

✅ Unit-набор — 433 passed (не трогаем, но проверяем в конце).

📁 ФАЙЛЫ
Создаются
Файл	Назначение
webui/static/vendor/webfonts/fa-solid-900.woff2	Solid (для fas fa-*)
webui/static/vendor/webfonts/fa-solid-900.ttf	Solid (TTF fallback)
webui/static/vendor/webfonts/fa-regular-400.woff2	Regular (для far)
webui/static/vendor/webfonts/fa-regular-400.ttf	Regular (TTF)
webui/static/vendor/webfonts/fa-brands-400.woff2	Brands (для fab)
webui/static/vendor/webfonts/fa-brands-400.ttf	Brands (TTF)
Изменяются
Файл	Что
webui/static/js/finding_detail.js	BUG-138: убрать onerror="..." из HTML, вынести обработку в addEventListener. BUG-140: условный рендеринг кнопки reveal, toggle-логика, устранение дублирования, тёмная тема.
Не изменяются
webui/static/vendor/css/fontawesome.min.css — уже содержит @font-face с путями ../webfonts/fa-solid-900.woff2 и т.д. Файлы просто нужно положить в webfonts/.

components/*.css, findings.css, tokens.css, base.css, components.css, grid-wireframe.css — не трогаем.

Остальные JS-файлы (api.js, auth.js, dashboard.js, findings.js) — не трогаем.

Backend (manager/src/api/findings.py) — не трогаем в этом ТЗ (см. TASK-4).

🔧 ДЕТАЛЬНОЕ ТЗ
TASK-201 — BUG-139: Наполнить webfonts/ (Font Awesome 6.4.0)
Файлы уже скачаны (см. скрин сессии):

Файл	Размер
fa-solid-900.woff2	150 124 B
fa-solid-900.ttf	394 628 B
fa-regular-400.woff2	24 948 B
fa-regular-400.ttf	63 952 B
fa-brands-400.woff2	108 020 B
fa-brands-400.ttf	187 208 B
Действие:

Убедиться, что файлы лежат в webui/static/vendor/webfonts/.

Пересобрать WebUI-контейнер:

powershell
cd E:\projects\dcap-system
docker compose build webui
docker compose up -d --force-recreate webui
Проверить через DevTools → Network (фильтр woff2) — 3 шрифта должны грузиться с 200 OK:

fa-solid-900.woff2 (~150 KB)

inter.woff2 (~350 KB)

jetbrains-mono.woff2 (~40 KB)

Проверка .dockerignore (важно!):

powershell
Get-Content .dockerignore
Get-Content webui\.dockerignore -ErrorAction SilentlyContinue
Если есть *.woff2 / **/vendor / webui/static/vendor — убрать (иначе пересборка не поможет).

Критерий приёмки:

Sidebar-иконки — серые (--color-ash), активный пункт — cornflower (--color-blue-cornflower).

DevTools → Network — 3 woff2 загружены.

Никаких «цветных emoji» на месте иконок.

TASK-202 — BUG-138: finding_detail.js — убрать onerror из HTML
Файл: webui/static/js/finding_detail.js

Проблема: в renderFragment() строка:

js
onerror="this.style.display='none'; this.insertAdjacentHTML('afterend','<div class=\'alert alert-warning\'>Фрагмент недоступен</div>')"
HTML-парсер рвёт атрибут onerror="..." на </div> внутри строки → JS-обработчик обрезается → SyntaxError.

Правка 1 — renderFragment() (строки 118–126):

Найти:

js
  renderFragment(f) {
    if (f.fragment_type === 'image_region') {
      return f.has_fragment || f.bounding_box
        ? `<img id="fragment-image" src="" class="img-fluid finding-image"
                  style="display:none"
                  alt="Фрагмент находки #${f.id}"
                  data-bbox='${JSON.stringify(f.bounding_box || {})}'
                  onerror="this.style.display='none'; this.insertAdjacentHTML('afterend','<div class=\'alert alert-warning\'>Фрагмент недоступен</div>')">`
        : '<span class="text-muted">(изображение без вырезанного фрагмента)</span>';
    }
Заменить на:

js
  renderFragment(f) {
    if (f.fragment_type === 'image_region') {
      return f.has_fragment || f.bounding_box
        ? `<img id="fragment-image" class="img-fluid finding-image"
                  style="display:none"
                  alt="Фрагмент находки #${f.id}"
                  data-bbox='${escapeHtml(JSON.stringify(f.bounding_box || {}))}'>`
        : '<span class="text-muted">(изображение без вырезанного фрагмента)</span>';
    }
Что изменилось:

❌ Убран src="" (не триггерит onerror мгновенно).

❌ Убран onerror="..." (невалидный HTML).

✅ data-bbox экранирован через escapeHtml (защита от ' в JSON).

Правка 2 — loadImageFragment() (строки 68–90):

Найти:

js
  async loadImageFragment() {
    const img = document.getElementById('fragment-image');
    if (!img) return;
    const meta = document.getElementById('fragment-meta');
    try {
Заменить на:

js
  async loadImageFragment() {
    const img = document.getElementById('fragment-image');
    if (!img) return;
    const meta = document.getElementById('fragment-meta');

    // BUG-138: обработка ошибки через DOM API (addEventListener),
    // не через onerror-атрибут с HTML внутри.
    img.addEventListener('error', () => {
      img.style.display = 'none';
      if (!meta) return;
      const div = document.createElement('div');
      div.className = 'alert alert-warning';
      div.textContent = 'Фрагмент недоступен';
      meta.insertAdjacentElement('beforebegin', div);
    }, { once: true });

    try {
Проверка после правки:

Открыть http://localhost:8001/findings/2046 → Ctrl+F5.

DevTools → Console — пусто.

Фрагмент (PNG Phone: +7 900 123-45-67 …) — отображается.

TASK-203 — BUG-140: Reveal-логика для finding_detail
Файл: webui/static/js/finding_detail.js

Проблемы:

Для image_region reveal не имеет смысла (PNG = оригинал).

#fragment перезаписывается → потеря исходного блока.

Кнопка не блокируется после успеха → спам аудита.

line_text и match_text дублируются.

bg-light — светлый фон на тёмной теме.

Правка 3 — renderFragment() возвращает также data-fragment-type (для условного рендеринга кнопки).

Модификация render() — убрать кнопку reveal-btn для image_region:

Найти в render() (в блоке <div class="card-body">):

js
          <div class="mt-3">
            ${f.can_reveal ? `<button class="btn btn-outline-primary" id="reveal-btn"><i class="fas fa-eye me-1"></i>Показать оригинал</button>` : ''}
          </div>
Заменить на:

js
          <div class="mt-3">
            ${f.can_reveal && f.fragment_type !== 'image_region'
              ? `<button class="btn btn-outline-primary" id="reveal-btn"><i class="fas fa-eye me-1"></i>Показать оригинал</button>`
              : ''}
          </div>
Правка 4 — bindEvents() — toggle-логика reveal.

Найти:

js
  bindEvents() {
    const revealBtn = document.getElementById('reveal-btn');
    if (revealBtn) {
      revealBtn.addEventListener('click', async () => {
        try {
          const r = await api.post(`/api/findings/${window.FINDING_ID}/reveal`);
          const box = document.getElementById('fragment');
          if (box) {
            box.innerHTML =
              `<div class="alert alert-warning py-2 small">Оригинал показан (операция записана в аудит)</div>` +
              `<pre class="bg-light p-2 small mb-1">${escapeHtml(r.line_text || '(строка недоступна)')}</pre>` +
              `<div><code>${escapeHtml(r.match_text || '')}</code></div>`;
          }
        } catch (e) {
          showError(e.message);
        }
      });
    }
Заменить на:

js
  bindEvents() {
    const revealBtn = document.getElementById('reveal-btn');
    if (revealBtn) {
      // BUG-140: toggle + кэш, чтобы не спамить аудит.
      // Оригинальное содержимое #fragment сохраняем и восстанавливаем.
      let revealed = false;
      let cachedReveal = null;
      const fragmentOriginalHTML = document.getElementById('fragment').innerHTML;

      revealBtn.addEventListener('click', async () => {
        const box = document.getElementById('fragment');
        if (!box) return;

        if (revealed) {
          // Возврат к маскированному виду — без POST, из кэша HTML.
          box.innerHTML = fragmentOriginalHTML;
          revealed = false;
          revealBtn.innerHTML = '<i class="fas fa-eye me-1"></i>Показать оригинал';
          return;
        }

        revealBtn.disabled = true;
        try {
          if (!cachedReveal) {
            cachedReveal = await api.post(`/api/findings/${window.FINDING_ID}/reveal`);
          }
          const r = cachedReveal;

          // Убираем дублирование line_text / match_text:
          // если match входит в line — подсвечиваем match внутри line.
          let blockHtml;
          const line = r.line_text || '';
          const match = r.match_text || '';
          if (line && match && line.includes(match)) {
            const escaped = escapeHtml(line);
            const escapedMatch = escapeHtml(match);
            const highlighted = escaped.replace(
              escapedMatch,
              `<mark>${escapedMatch}</mark>`
            );
            blockHtml = `<pre class="reveal-block p-2 small mb-1">${highlighted}</pre>`;
          } else if (line) {
            blockHtml = `<pre class="reveal-block p-2 small mb-1">${escapeHtml(line)}</pre>`;
          } else if (match) {
            blockHtml = `<div><code>${escapeHtml(match)}</code></div>`;
          } else {
            blockHtml = `<div class="text-muted">(недоступно)</div>`;
          }

          box.innerHTML =
            `<div class="alert alert-warning py-2 small">Оригинал показан (операция записана в аудит)</div>` +
            blockHtml;

          revealed = true;
          revealBtn.innerHTML = '<i class="fas fa-eye-slash me-1"></i>Скрыть оригинал';
        } catch (e) {
          showError(e.message);
        } finally {
          revealBtn.disabled = false;
        }
      });
    }
Правка 5 — CSS: .reveal-block вместо bg-light.

Добавить в webui/static/css/findings.css:

css
/* BUG-140: reveal-блок в тёмной теме (замена bg-light) */
.reveal-block {
    background: var(--color-deep-coal);
    color: var(--color-snow);
    border-radius: var(--radius-tags);
    white-space: pre-wrap;
    word-break: break-all;
}
.reveal-block mark {
    background: var(--color-blue-cornflower);
    color: var(--color-page-ink);
    padding: 0 2px;
    border-radius: 2px;
}
Аудит: только при первом POST для каждой сессии страницы (в коде — cachedReveal). При toggle «скрыть → показать» — без повторного POST.

TASK-204 — Диагностика (не фикс, обсудить с архитектором)
Finding 2043: finding_type=pii, category=person, detector=presidio, confidence=0.85, но:

/findings/2043 → match_text = "Дата: 15.09.2026".

/findings/2043/reveal → line_text = "Дата: 15.09.2026", match_text = "Дата".

Вопрос: /reveal возвращает line_text — всю строку или только match? Ожидание — вся строка (ИНН: +7 900 234-56-789 Дата: 15.09.2026 Подпись: ___).

Действие: открыть manager/src/api/findings.py, найти reveal, проверить, что возвращается. Правку не делать без подтверждения архитектора — возможно, это не баг backend, а FP presidio (person="Дата"). Тогда — TEST-NOTE-10.15 (отдельный день «Качество детекции»).

Для 53.4a-доп: если backend возвращает корректную line_text, оставить как есть. Если возвращает урезанную — fix в 53.4a-доп, добавить в отчёт.

🧪 КРИТЕРИИ ПРИЁМКИ
#	Критерий	Проверка
1	webui/static/vendor/webfonts/ содержит 6 файлов (3 × woff2 + 3 × ttf)	ls
2	WebUI-контейнер пересобран, healthy	docker ps
3	DevTools → Network: fa-solid-900.woff2 → 200, ~150 KB	ручная
4	Sidebar-иконки серые, активный пункт — cornflower	ручная
5	DevTools → Console на /findings/2046 — пусто	ручная
6	/findings/2046 — фрагмент PNG отображается	ручная
7	/findings/2043 — кнопки reveal нет (fragment_type=text_line → есть, но у нас person)	ручная
8	/findings/2046 (image_region) — кнопки reveal нет	ручная
9	/findings/{text_line} — reveal toggle работает (Показать ⇄ Скрыть)	ручная
10	Повторные клики reveal не пишут дублей finding_reveal в audit_logs	SQL
11	line_text + match_text не дублируются	ручная
12	Никаких bg-light (белых пятен) на тёмной теме	ручная
13	Unit-набор — 433 passed	pytest tests/unit/ -q
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
Проверка BUG-139 (webfonts)
powershell
# 1. Файлы на месте
ls webui\static\vendor\webfonts\

# 2. Пересборка
docker compose build webui
docker compose up -d --force-recreate webui

# 3. Проверка
docker ps --filter "name=webui"
В браузере:

/ → Ctrl+F5.

DevTools → Network → filter woff2 → 3 файла с 200.

Sidebar-иконки серые.

Проверка BUG-138 (Console)
/findings/2046 → Ctrl+F5.

DevTools → Console — пусто.

Фрагмент PNG — отображается.

Проверка BUG-140 (reveal)
На image_region (/findings/2046):

Кнопки «Показать оригинал» — нет.

Фрагмент PNG — отображается.

На text_line (/findings/{id} с fragment_type=text_line):

Открыть — видно маскированное.

Клик «Показать оригинал» → расшифрованное + подсветка <mark> (если match ⊂ line).

Кнопка меняется на «Скрыть оригинал».

Клик «Скрыть» → возврат к маскированному (без POST).

Клик снова «Показать» → то же расшифрованное (из кэша JS, без POST).

Открыть в другой вкладке /audit — там один finding_reveal за все клики.

Unit-набор
powershell
pytest tests/unit/ -q
Ожидание: 433 passed.

📝 СВОДКА ПРАВОК
#	Файл	Действие
1	webui/static/vendor/webfonts/fa-solid-900.woff2	Создан (curl)
2	webui/static/vendor/webfonts/fa-solid-900.ttf	Создан
3	webui/static/vendor/webfonts/fa-regular-400.woff2	Создан
4	webui/static/vendor/webfonts/fa-regular-400.ttf	Создан
5	webui/static/vendor/webfonts/fa-brands-400.woff2	Создан
6	webui/static/vendor/webfonts/fa-brands-400.ttf	Создан
7	webui/static/js/finding_detail.js	Изменён (BUG-138 + BUG-140)
8	webui/static/css/findings.css	Изменён (.reveal-block вместо bg-light)
9	.dockerignore	Возможно (убрать *.woff2 если есть)
⚠️ ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ
match_text vs line_text для finding 2043 — семантический вопрос backend. Не чиним в 53.4a-доп, если это FP presidio (TEST-NOTE-10.15).

Качество детекции (~40 % FP: url, organization, us_driver_license, nrp) — TEST-NOTE-10.15, отдельный день.

Chart.js — палитра не под Dovetail, 53.4d.

Grid-wireframe тонкий — 53.4e.

FA иконки остаются (BACKLOG-101 — v3.1.0).

📋 ОТКРЫТЫЕ ВОПРОСЫ
.dockerignore — если есть *.woff2 / **/vendor, убрать или добавить исключение !webui/static/vendor/webfonts/. Проверить перед пересборкой.

finding 2043 — FP presidio person="Дата". Это data-quality, не UI. Подтвердить: TEST-NOTE-10.15, не BUG-140.

/reveal возвращает line_text — проверить backend. Если урезанная — fix в 53.4a-доп, если нет — оставить.

image_region без reveal — оставляем кнопку скрытой (моё предложение). Альтернатива — «Скачать PNG» (в 53.4c).

⚠️ ЧТО НЕ ДЕЛАЕМ
Не переделываем components/*.css — sidebar/header/cards/tables/forms/modals/badges.

Не трогаем tokens.css, base.css, components.css, grid-wireframe.css.

Не трогаем Chart.js.

Не трогаем разметку страниц (dashboard.html, findings.html, ...).

Не трогаем backend (manager/src/api/findings.py) без подтверждения.

Не меняем fontawesome.min.css — только докладываем файлы в webfonts/.

💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_53_4a_add_webui_fixes

git add webui/static/vendor/webfonts/ \
        webui/static/js/finding_detail.js \
        webui/static/css/findings.css \
        STATE.md CHANGELOG.md ROADMAP.md \
        prompts/reports/day_53_4a_add_webui_fixes_report.md

git commit -m "fix: 53.4a-доп — WebUI fixes (BUG-138/139/140)

- BUG-139: Font Awesome webfonts (6 файлов, FA 6.4.0) — sidebar monochrome,
  соответствует DESIGN.md (--color-ash + --color-blue-cornflower)
- BUG-138: finding_detail.js — onerror через addEventListener,
  убран HTML в атрибуте (устранён SyntaxError: missing ) after argument list)
- BUG-140: reveal-логика в finding_detail.js:
  - для fragment_type=image_region кнопка reveal СКРЫТА (PNG = оригинал)
  - toggle «Показать / Скрыть» без перезаписи #fragment
  - кэш reveal — повторные клики не спамят audit_logs
  - устранено дублирование line_text/match_text (подсветка <mark>)
  - .reveal-block вместо bg-light (тёмная тема)
- findings.css: .reveal-block + <mark>

Backlog: BACKLOG-093 (этап 1/5, доработка)
docs: обновлены STATE.md (v3.13.38), CHANGELOG.md, ROADMAP.md"
📊 ОБНОВЛЕНИЕ ПЛАНА
День	Задача	Статус
53.4a	WebUI-редизайн (этап 1)	✅ v3.13.37
53.4a-доп	BUG-138/139/140 (webfonts + finding_detail)	🔄 в работе
53.4b	login, dashboard, resources, findings	📋
53.4c	finding_detail, catalog, audit, scanners, access	📋
53.4d	roles, users, settings, footer, графики	📋
53.4e	полировка, скриншоты, docs/DESIGN.md	📋
55	GitHub-пакет — после 53.4e	📋
📌 ПОСЛЕ ВЫПОЛНЕНИЯ
Обновить STATE.md: версия v3.13.38, в «Открытых проблемах»:

BUG-138 ✅ fixed

BUG-139 ✅ fixed

BUG-140 ✅ fixed

TEST-NOTE-10.15 (FP presidio) — открыт, отдельный день.

Обновить CHANGELOG.md — секция [3.13.38].

Обновить ROADMAP.md — 53.4a-доп ✅, следующий — 53.4b.

Переместить ТЗ в prompts/archive/day_53_4a_add_webui_fixes.md.

Отчёт — prompts/reports/day_53_4a_add_webui_fixes_report.md:

список файлов,

скриншоты (sidebar до/после, reveal toggle),

Console чистая,

SQL: SELECT count(*) FROM audit_logs WHERE event_type='finding_reveal' AND created_at > NOW() - INTERVAL '10 min' — не более 1 записи на finding за сессию.

Автор ТЗ: архитектор
Дата: 10.10.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.38 — sidebar-иконки Dovetail, чистая Console, корректная reveal-логика. 53.4a закрыт полностью, переход в 53.4b.