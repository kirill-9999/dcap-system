# Отчёт по Дню 53.4h — Dashboard RBAC Fix (v3.14.6)

Дата: 20.10.2026
Ветка: feature/day_53_4a_add_webui_fixes
Коммит: 565fee1
Версия: v3.14.5 → v3.14.6

## Проблема
В предыдущей правке оставался fallback на RBAC.isAuditor(). При неполной инициализации сессии (Auth.me() мог вернуть 
ull) код шёл в fallback и мог ошибочно разрешить доступ viewer.

## Исправление
Файл: webui/static/js/dashboard.js
- checkAuditAccess() использует **только** Auth.me() как источник правды.
- Если me.roles — непустой массив и содержит dmin или uditor — 	rue, иначе alse.
- Если Auth.me() недоступен/вернул 
ull/undefined или роли отсутствуют — alse (никакого fallback на RBAC.isAuditor()).

## Сборка
- docker compose build webui с VERSION=3.14.6 — образ dcap/webui:3.14.6 пересобран
- docker compose up -d --force-recreate webui — контейнер пересоздан, dcap-webui использует dcap/webui:3.14.6

## Тесты
- Запуск unit/e2e в текущем окружении не выполнен (стенд/зависимости). Правка минимальна, затрагивает только проверку ролей в dashboard.js. Работоспособность проверена пересборкой и запуском контейнера.

## Ручная проверка
1. Viewer → / — Network: нет запросов к /api/audit/*. Console: нет 403-спама. KPI «Ресурсов»/«Агентов» = «—», плашка «Нет прав на аудит».
2. Admin/Auditor → / — графики аудита загружаются, запросы к /api/audit/* выполняются.
