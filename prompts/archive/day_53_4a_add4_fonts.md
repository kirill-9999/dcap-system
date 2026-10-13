# ТЗ 53.4a-доп4 — Fonts: unicode-range для кириллицы

**Дата:** 12.10.2026
**Версия:** v3.13.40
**Приоритет:** 🔴 блокер дизайна 53.4b–53.4e
**Длительность:** 0.5 дня
**Источник:** мастер-сессия v3.13.38

---

## 🎯 Цель

Inter и JetBrains Mono **не применяются к кириллице** — все русские тексты
в системном fallback (Segoe UI / Arial). Дизайн Dovetail **сломан**.

---

## 📋 BUG-212 — `unicode-range` latin-only

**Доказательство:**
- `inter.css` / `jetbrains-mono.css` — `unicode-range` без `U+0400-04FF`.
- Network → Font: **0 запросов**.
- Computed `font-family`: `ui-sans-serif`.
- **Тест подтвердил**: кириллица **есть** в woff2 ✅.

**Файлы:**
- `webui/static/vendor/fonts/inter.css`
- `webui/static/vendor/fonts/jetbrains-mono.css`

**Фикс:**

```css
/* inter.css */
@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-display: swap;
    font-weight: 100 900;
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
jetbrains-mono.css — то же (тот же unicode-range).

Действия:

Отредактировать оба файла.

Пересобрать WebUI: docker compose build webui && docker compose up -d webui
(или отключить volume, если файлы монтируются — проверить compose).

Проверить Network → Font → 2 запроса — 200.

Computed font-family → Inter, ....

Регресс — все 14 страниц.

✅ Definition of Done
Network → Font: 2 запроса (inter.woff2, jetbrains-mono.woff2) — 200.

Computed font-family: Inter, ui-sans-serif, ....

Русский текст — отрисован в Inter.

<code> / <pre> — JetBrains Mono.

Скриншот / до / после — визуальная разница.

📋 Обновить ARCHITECTURE.md
Раздел «Шрифты» — закрыть пункт «unicode-range … v3.1.0»,
отметить 53.4a-доп4.

Конец ТЗ 53.4a-доп4