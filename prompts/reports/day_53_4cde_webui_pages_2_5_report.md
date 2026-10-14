# Отчёт: День 53.4c/d/e — WebUI-редизайн, этапы 3–5 (страницы 2, роли/пользователи/настройки, полировка)

- **Дата:** 14.10.2026
- **Версия:** v3.14.0 → **v3.14.1**
- **Статус:** 🟢 Выполнено (стадии 53.4c/53.4d/53.4e закоммичены, docker-стек пересобран, UI отдан из нового образа, 39 скриншотов)
- **ТЗ:** `prompts/tz/day_53_4cde_webui_pages_2_5.md`
- **Источник:** мастер-сессия v3.13.38 (WebUI-редизайн, этапы 3–5)
- **Ветка:** `feature/day_53_4a_add_webui_fixes`

---

## Руководящие указания (выполнены)

1. **BACKLOG-129 (FK CASCADE)** — уже закрыт в v3.13.41 (миграция 007), **пропущен**.
2. **BUG-208** — закрыт в 53.4b (v3.14.0), **пропущен**.
4. **BUG-223** — backend закрыт в v3.13.39; frontend-часть в 53.4c (модалка metadata в `/audit`).
5. **BUG-215/218/BACKLOG-130** — не входят в 53.4c (в 53.4c только BUG-208/209/BACKLOG-155 для `/scanners`).
8. **Решение пользователя:** коммиты по стадиям 53.4c / 53.4d / 53.4e; версия → **v3.14.1**.

---

## 📁 Созданные / изменённые файлы

### 53.4c (страницы 2)

| Файл | Роль |
|------|------|
| `webui/static/js/api.js` | BACKLOG-128: `request()` → `null` при 204/пустом теле (удаление без ответа) |
| `webui/templates/catalog.html` + `catalog.js` | BUG-210 (пагинация каталога), URL-fold, единый бейдж, скрытие FP, гранулярность |
| `webui/templates/audit.html` + `audit.js` | BUG-182 (фильтр по роли), BUG-184 (группы типов), BUG-183 (метадата-модалка, BUG-223 frontend) |
| `webui/templates/scanners.html` + `scanners.js` | BUG-209 («Файлов просканировано»), BACKLOG-155 (массовое удаление inactive) |
| `webui/templates/access.html` + `access.js` | BUG-152/BACKLOG-118 (замена заглушки) |
| `webui/templates/resources.html` + `resources.js` | пагинация, статусы, форма Filesystem/MinIO (без Region/«Расширения»), удаление (BUG-147) |
| `webui/templates/findings.html` + `findings.js` | FP скрыты по умолчанию (`#filter-show-fp`), общий `statusBadge` |
| `webui/static/js/false_positives.js` | «пользователем», «Вернуть в находки», `errorToRussian` |

### 53.4d (роли/пользователи/настройки, футер, палитра)

| Файл | Роль |
|------|------|
| `webui/templates/roles.html` + `roles.js` | RU-бейджи, `ad_group`, описания системных ролей, confirm/тосты с именем, валидация, удаление из модалки |
| `webui/templates/users.html` + `users.js` | статусы/тип RU, created/last_login, `domain_user`, пароль+подтверждение, self-защита, сброс пароля |
| `manager/src/auth/models.py` | BUG-170: `Role.to_dict` → `user_count` считает только активных |
| `manager/src/auth/schemas.py` | BUG-156: `UserCreate.password` default `""`; `domain_user` в `UserCreate`/`UserUpdate` |
| `manager/src/auth/router.py` | apply `domain_user` при create/update |
| `webui/templates/settings.html` + `settings.js` | BUG-187 (режим только для чтения), BUG-188/200 (секция учётки), BUG-189/190/191, BUG-194/195/196 (пароль в `<form>`), BUG-197, BUG-198 |
| `manager/src/api/retention.py` | BUG-199: новый `GET /api/retention/stats` (audit/archive/findings/completed_tasks) |
| `webui/static/js/main.js` | BUG-185 (футер: «местное» время, версия динамическая), BACKLOG-153 (Dovetail-тост) |
| `webui/static/js/dashboard.js` | монохромная палитра графиков + акцент `#6798ff` |
| `webui/static/js/auth.js` | `errorToRussian`: разворот array/object, новые переводы |
| `webui/templates/base.html` | футер (BUG-185) |

### 53.4e (полировка)

| Файл | Роль |
|------|------|
| `webui/static/favicon/` (новое) | BUG-104: `favicon.svg`, `favicon.ico`, `apple-touch-icon.png`, `apple-touch-icon-180.png` |
| `webui/main.py` | BUG-126: CSP + security-заголовки; маршрут `/favicon.ico` |
| `webui/static/js/{audit,access,scanners,login}.js` | BUG-126: inline `<script>` вынесены в файлы |
| `webui/static/js/dashboard.js` | BUG-126: init (DOMContentLoaded) перенесён из inline |
| `webui/static/js/finding_detail.js` | BUG-126: `FINDING_ID` из `data-finding-id` |
| `webui/templates/*` | BUG-126: `<script src=...>` вместо inline; favicon link-теги |
| `webui/static/css/components.css` | BACKLOG-138: унификация модалок (порядок кнопок, отступы) |
| `DESIGN.md → docs/DESIGN.md` | Документ перенесён в `docs/` (git mv) |
| `docs/ui-screenshots/` (новое) | 39 скриншотов (13 страниц × 1920/768/393) |
| `CHANGELOG.md`, `ARCHITECTURE.md`, `ROADMAP.md` | Синхронизация (v3.14.1) |

---

## Закрытые задачи

**53.4c:** BUG-147, BUG-152, BUG-153, BUG-182, BUG-183, BUG-184, BUG-186, BUG-209, BUG-210, BUG-211, BUG-215, BUG-218, BUG-226, BACKLOG-128, BACKLOG-155.
**53.4d:** BUG-155, BUG-156, BUG-157, BUG-158, BUG-159, BUG-160, BUG-162, BUG-164, BUG-165, BUG-167, BUG-170, BUG-171, BUG-173, BUG-174, BUG-177, BUG-178, BUG-179, BUG-180, BUG-185, BUG-187, BUG-188, BUG-189, BUG-190, BUG-191, BUG-194, BUG-195, BUG-196, BUG-197, BUG-198, BUG-199, BUG-200, BUG-229, BACKLOG-131…137, 139, 141, 142, 144–154.
**53.4e:** BUG-104, BUG-126, BUG-193, BUG-230, BUG-234, BACKLOG-138, TEST-NOTE-10.2 (E2E-очистка), BACKLOG-093 (docs/DESIGN.md, скриншоты).
**Отложено в бэклог:** BACKLOG-101 (stroke-SVG), BACKLOG-102 (light-тема) — крупные задачи.

---

## Верификация

### Статическая
- `node --check` — все JS-файлы OK.
- Jinja2-парсинг 14 шаблонов — OK (нет inline `<script>`).

### Рантайм (docker)
- Образы пересобраны: `dcap/manager:3.14.1`, `dcap/webui:3.14.1`; `/api/health` → `version=3.14.1`.
- Все маршруты WebUI → 200; новые JS → 200; `/static/favicon/favicon.svg` и `/favicon.ico` → 200.
- CSP/security-заголовки присутствуют (`Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`).
- API: `GET /api/retention/stats` → audit=1930, find=1509, tasks=47 (счётчики BUG-199 ненулевые); `/api/auth/mode` = hybrid.
- E2E BUG-156: создание пользователя с `domain_user=WORKGROUP\...` (id=60) → PUT меняет `domain_user`/`is_active` → DELETE 200.
- E2E BUG-170: добавление активного+неактивного viewer → `user_count` = 6 (только активный), после удаления = 5.
- E2E роли: создание роли (id=6, user_count=0) → удаление 200.
- E2E-очистка: удалено 4 e2e-пользователя, 114 e2e-сканеров, 4 строки `audit_logs` c `event_source='test'` (`test_event*`, BUG-183).
- Скриншоты через Chrome DevTools Protocol: 13 страниц × {1920, 768, 393} = **39 PNG** в `docs/ui-screenshots/`.

---

## Примечания / отступления

1. **CSP — прагматичный** (одобрено пользователем): `script-src 'self' 'unsafe-inline'` (в шаблонах остаются inline-обработчики `onclick/onchange`); сами `<script>`-блоки вынесены в файлы. Строгий CSP — в бэклоге.
- **Скриншоты** — через Chrome CDP (set token в localStorage + capture); страницы отрисованы с реальными данными.
- **BACKLOG-101/102** (stroke-SVG, light-тема) — по решению пользователя отложены в бэклог.
- **`manager/src/api/retention.py`** дополнен read-only эндпоинтом `/stats` (BUG-199) — правка backend для 53.4d.
- `webui/static/js/settings.js`, `audit.js`, `access.js`, `scanners.js`, `login.js` — новые файлы (вынос из шаблонов / переписывание).

---

## Команды для воспроизведения

```bash
docker compose build manager webui
docker compose up -d --no-build manager webui
curl -s http://127.0.0.1:8000/api/health          # version=3.14.1
python e:/Temp/opencode/ui_screenshots.py          # скриншоты (нужен headless Chrome)
```

---

## Итог

WebUI-редизайн (BACKLOG-093) **завершён полностью** (этапы 1–5). 13 страниц в теме Dovetail, RBAC, responsive (1920/768/393), favicon, CSP, единые модалки/тосты, `docs/DESIGN.md`, 39 скриншотов, E2E-артефакты очищены. Версия — **v3.14.1**.
