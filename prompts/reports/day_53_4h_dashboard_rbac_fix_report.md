# Отчёт по Дню 53.4h — Dashboard RBAC Fix (v3.14.5)

Дата: 20.10.2026
Ветка: feature/day_53_4a_add_webui_fixes
Коммит: 6321b2d
Версия: v3.14.5

## Проблема
При логине под viewer checkAuditAccess() в dashboard.js мог ошибочно вернуть 	rue из-за fallback на RBAC.isAuditor(), в результате шли запросы к /api/audit/* и появлялся 403-спам.

## Исправление
Файл: webui/static/js/dashboard.js
- Если Auth.me() вернул объект с массивом oles — проверка идёт только по oles. Если ролей нет среди dmin/uditor — возвращается alse без fallback на RBAC.isAuditor().
- Fallback на RBAC.isAuditor() используется только если Auth.me() недоступен или не вернул список ролей.

## Сборка
- docker compose build webui с VERSION=3.14.5 — образ dcap/webui:3.14.5 пересобран
- docker compose up -d --force-recreate webui — контейнер пересоздан, работает на dcap/webui:3.14.5

## Ручная проверка
1. Viewer → / — запросы к /api/audit/* отсутствуют, KPI «Ресурсов»/«Агентов» = «—», плашка «Нет прав на аудит».
2. Admin/Auditor → / — графики аудита загружаются, запросы к /api/audit/* уходят.
