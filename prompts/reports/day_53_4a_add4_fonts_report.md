# Отчёт: День 53.4a-доп4 — Fonts: unicode-range для кириллицы

- **Дата:** 12.10.2026
- **Версия:** v3.13.39 → **v3.13.40**
- **Статус:** ✅ Выполнено
- **ТЗ:** `prompts/archive/day_53_4a_add4_fonts.md`
- **Источник:** мастер-сессия v3.13.38 (BUG-212, блокер дизайна 53.4b–53.4e)
- **Ветка:** `feature/day_53_4a_add_webui_fixes`

---

## 🎯 Цель

Inter и JetBrains Mono не применялись к кириллице → русский UI уходил в системный
fallback (Segoe UI / Arial), дизайн Dovetail был сломан. BUG-212 закрыт.

---

## 🔑 Что сделано

### 1. `unicode-range` с кириллицей в обоих @font-face

По тексту ТЗ в `webui/static/vendor/fonts/inter.css` и `jetbrains-mono.css`:

```css
@font-face {
    font-family: 'Inter';              /* 'JetBrains Mono' — аналогично */
    font-style: normal;
    font-display: swap;
    font-weight: 100 900;              /* JetBrains Mono: 100 800 */
    src: url('./inter.woff2') format('woff2-variations');
    unicode-range:
        /* Latin */
        U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA,
        U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+2074, U+20AC,
        U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD,
        /* Cyrillic (основная) */
        U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116,
        /* Cyrillic (расширенная) */
        U+0460-052F, U+1C80-1C88, U+20B4, U+2DE0-2DFF, U+A640-A69F,
        /* Latin Extended Additional */
        U+1E00-1EFF;
}
```

### 2. ⚠️ Отклонение от ТЗ (важно): замена `jetbrains-mono.woff2`

При проверке выяснилось: `unicode-range` были **не единственной** причиной BUG-212.

| Файл | Было | Глифов | Кириллица (U+0400-045F) |
|------|------|--------|--------------------------|
| `inter.woff2` | Inter Variable (rsms) | 2852 | ✅ 96 базовых + 155 extended |
| `jetbrains-mono.woff2` | **Fontsource latin-wght-normal подмножество** | **229** | ❌ **0** |

Даже после фикса CSS браузер запросил бы `jetbrains-mono.woff2` для кириллицы в
`<code>/<pre>`, но глифы в нём отсутствуют → fallback на системный моноширинный.
DoD «<code> / <pre> — JetBrains Mono» (для русского текста) был невыполним.

**Решение:** `jetbrains-mono.woff2` заменён на официальный **JetBrains Mono v2.304**
(ветка релиза, юр.лицензия SIL OFL 1.1): `fonts/variable/JetBrainsMono[wght].ttf`
→ variable woff2 (`fontTools`: `flavor='woff2'`).

| После | Значение |
|-------|----------|
| Размер | 113 484 байта (было 40 404) |
| Глифов в cmap | 1363 (было 229) |
| Базовая кириллица | 92/96 |
| Ось `wght` | 100–800 (совпадает с `@font-face: font-weight: 100 800`, `woff2-variations`) |

Добавлен `webui/static/vendor/fonts/OFL.txt` (SIL OFL 1.1, JetBrains Mono).
`inter.woff2` не менялся (уже полный variable с кириллицей).

Команда воспроизведения (если понадобится пересобрать woff2):

```python
from fontTools.ttLib import TTFont
f = TTFont('JetBrainsMono[wght].ttf'); f.flavor = 'woff2'
f.save('jetbrains-mono.woff2')
```

---

## 📁 Файлы

| Файл | Изменение |
|------|-----------|
| `webui/static/vendor/fonts/inter.css` | unicode-range + Cyrillic base/ext |
| `webui/static/vendor/fonts/jetbrains-mono.css` | unicode-range + Cyrillic base/ext |
| `webui/static/vendor/fonts/jetbrains-mono.woff2` | **заменён** (официальный JetBrains Mono v2.304 variable, кириллица) |
| `webui/static/vendor/fonts/OFL.txt` | **NEW** — лицензия SIL OFL 1.1 |
| `.env` / `.env.example` / `docker-compose.yml` / `.test.yml` / `.s3.yml` | `VERSION=3.13.40` |

`ARCHITECTURE.md` — в переработке архитектора, **в code-коммит не входит**;
готовый патч — в Приложении A (в дополнение к патчу add3).

---

## 🧪 Критерии приёмки

| # | DoD | Результат |
|---|-----|-----------|
| 1 | Network → Font: 2 запроса (inter.woff2, jetbrains-mono.woff2) — 200 | ✅ server-side: оба 200 (inter 352 240 б, jetbrains-mono 113 484 б); CSS-цепочка `main.css → base.css → @import inter.css/jetbrains-mono.css` связана, страницы содержат кириллицу → браузер запрашивает оба файла. Визуальная часть (Network-вкладка DevTools) — ручная проверка пользователем |
| 2 | Computed font-family: Inter, ui-sans-serif, … | ✅ `tokens.css`: `--font-inter: 'Inter', ui-sans-serif, system-ui, …`; `--font-jetbrains-mono: 'JetBrains Mono', ui-monospace, …`; `--font-mono: var(--font-jetbrains-mono)`; `base.css` вешает их на body и `code/pre` |
| 3 | Русский текст отрисован в Inter | ✅ глифы: Inter — П/р/и/в/е/т/Ж/У/К/я в cmap (96 базовых); `unicode-range`-матчинг эмулирован: выборка полностью попадает в диапазоны |
| 4 | `<code>` / `<pre>` — JetBrains Mono | ✅ **после замены woff2**: JetBrains Mono — 10/10 тестовых глифов в cmap (было 0) |
| 5 | Скриншот до/после | ⏳ ручная (нет браузерной автоматизации в стеке); server-side-доказательства — выше |
| 6 | Регресс 14 страниц | ✅ **14/14 → 200** |
| 7 | Обновлён ARCHITECTURE.md («Шрифты») | ⏳ файл переписывает архитектор (708+/909-); **патч — Приложение A** |

---

## 🔧 Как проверить вручную (DevTools)

1. `docker compose build webui && docker compose up -d webui` (уже сделано).
2. Открыть `http://127.0.0.1:8001/login`, DevTools → Network → при фильтре **Font**
   должны появиться 2 запроса: `inter.woff2` и `jetbrains-mono.woff2` → **200**.
3. Выбрать русский текст → Computed → `font-family: Inter, ui-sans-serif, …`.
4. Открыть Findings → идентификатор фрагмента/лога в `<code>` → `JetBrains Mono`.

---

## 💾 Коммит

```bash
git add webui/static/vendor/fonts/inter.css \
        webui/static/vendor/fonts/jetbrains-mono.css \
        webui/static/vendor/fonts/jetbrains-mono.woff2 \
        webui/static/vendor/fonts/OFL.txt \
        .env .env.example \
        docker-compose.yml docker-compose.test.yml docker-compose.s3.yml \
        STATE.md CHANGELOG.md ROADMAP.md \
        prompts/archive/day_53_4a_add4_fonts.md \
        prompts/reports/day_53_4a_add4_fonts_report.md

git commit -m "fix: 53.4a-доп4 — fonts unicode-range кириллицы (v3.13.40)

- BUG-212: inter.css/jetbrains-mono.css — unicode-range расширен кириллицей
  (U+0400-045F base + U+0460-052F/1C80-1C88/20B4/2DE0-2DFF/A640-A69F ext + U+1E00-1EFF).
- jetbrains-mono.woff2 заменён: Fontsource latin-подмножество (229 глифов, кириллицы 0)
  -> официальный JetBrains Mono v2.304 variable (1363 глифа, кириллица 92/96, wght 100-800);
  добавлен OFL.txt (SIL OFL 1.1).
- Проверка: оба woff2 200; глифы в cmap (Inter 10/10, JBM 10/10); unicode-range-матчинг
  кириллицы подтверждён; регресс WebUI 14/14 страниц 200.
- WebUI+Manager пересобраны, VERSION=3.13.40; /api/health -> 3.13.40.
- ARCHITECTURE.md не трогал (в переработке архитектора); патч раздела «Шрифты» - в отчёте.

Backlog: BUG-212 закрыт (шрифты Dovetail работают для русского текста)
docs: обновлены STATE.md (v3.13.40), CHANGELOG.md, ROADMAP.md"
```

---

## Приложение A — Патч ARCHITECTURE.md для архитектора

В раздел «Шрифты» (строки 613–622, 646, 1049–1050 в рабочем дереве):

1. **Закрыть** пункт ТЗ-списка `unicode-range кириллицы в обоих @font-face` →
   ✅ **v3.13.38** (ошибочно проставлен v3.1.0; актуально **53.4a-доп4, v3.13.40**).
2. **Таблица файлов** (строки 617–619): `jetbrains-mono.woff2` — заменить описание
   `40 KB, Fontsource (latin-wght-normal), ⚠️ latin-only` на:
   **`113 KB, JetBrains Mono v2.304 variable (wght 100-800), кириллица`**; `inter.woff2` — без изменений (352 KB, Inter Variable, кириллица есть).
3. **Снять предупреждения** (строки 621–622): `unicode-range` теперь включает
   **Cyrillic base** (U+0400-045F, U+0490-0491, U+04B0-04B1, U+0301, U+2116),
   **Cyrillic Extended** (U+0460-052F, U+1C80-1C88, U+20B4, U+2DE0-2DFF, U+A640-A69F)
   и Latin Extended Additional (U+1E00-1EFF) в обоих файлах — русский UI и `<code>/<pre>`
   отрисовываются без fallback.
4. **Строки 1049–1050** (риски): JetBrains Mono/Inter «потенциально latin-only» — закрыть ✅ v3.13.40 (53.4a-доп4); отметить, что часть BUG-212 была в самом woff2 (0 кириллических глифов), а не только в unicode-range.
5. **Строка 993** (53.4a): `JetBrains Mono Variable (40 KB, latin-only)` → `133 KB, v2.304, кириллица`.

Конец отчёта 53.4a-доп4.