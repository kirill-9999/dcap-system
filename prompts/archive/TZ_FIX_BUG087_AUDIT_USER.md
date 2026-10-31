# TZ_FIX_BUG087_AUDIT_USER — БUG-087: `audit_logs.user` вместо пользователя (TASK-060, v3.13.23)

> ⚠️ **Архивная копия (реконструкция).** Файл ТЗ отсутствовал в `prompts/tz/`
> (задание было передано в чате), поэтому здесь зафиксировано содержание задачи
> по итогам выполнения. Оригинальный текст для будущих ТЗ должен сохраняться
> в `prompts/tz/` перед началом работы.

**Дата:** 27.09.2026 · **Версия:** v3.13.22 → v3.13.23 · **Отчёт:** `prompts/reports/day_48.1_bug087_audit_user_report.md`

## Задача

Диагностировать и исправить ситуацию, при которой аудит раскрытия находки
(`POST /api/findings/{id}/reveal`) записывает в `audit_logs.user` значение `dcap`
(имя сервисной/Docker-роли) вместо реального пользователя, вошедшего в систему.

## Требования

1. Проверить гипотезы подмены:
   - H1 — SQLAlchemy `event.listens_for` / `before_insert`;
   - H2 — DEFAULT/TRIGGER на уровне PostgreSQL;
   - H3 — подмена `request.state.user` в middleware;
   - H4 — `require_auditor` возвращает service-user;
   - H5 — дублирующее создание `AuditLog` для того же события;
   - H6 — `_log_reveal` вызывается с другим пользователем;
   - H7 — hook на `session.commit()`.
2. Найти корень и исправить, если подмена подтверждена.
3. Покрыть регрессией: `tests/unit/test_audit_reveal_user_v31323.py`,
   `tests/e2e/test_audit_reveal_user_e2e.py`.
4. Проверить остальные эндпоинты, пишущие аудит (`auth_login`, `user_created`).
5. Критерии приёмки: тесты зелёные, live-проверка показывает реального
   пользователя, версия 3.13.23, STATE/ROADMAP/CHANGELOG обновлены.

## Результат

- 🔴 **Баг не подтверждён.** Подмены нет ни в коде, ни в БД: реальный `INSERT`
  в PostgreSQL содержит `'auditor'`.
- **Корень ложного срабатывания** — диагностический SQL ТЗ: колонка `user`
  указана без кавычек, а в PostgreSQL `user` ≡ `CURRENT_USER` (роль БД `dcap`).
  Корректно: `SELECT "user" FROM audit_logs`.
- Правки production-кода **не потребовались**; закрыто регрессионными тестами
  (7 unit + 3 E2E), описанием ловушки в `docs/admin-guide/10-troubleshooting.md`
  и live-доказательством (`revealed_by=auditor`, `SELECT "user"` → `auditor`).
- ⚠️ ID `BUG-087` уже занят Днём 48 (TASK-054) — зафиксировано как **BUG-094**.
