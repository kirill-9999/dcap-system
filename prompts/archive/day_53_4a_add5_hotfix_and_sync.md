ТЗ 53.4a-доп5 — Hotfix + синхронизация ARCHITECTURE.md
Файл: prompts/tz/day_53_4a_add5_hotfix_and_sync.md
Дата: 12.10.2026
Версия: v3.13.41
Приоритет: 🔴 Блокер v3.0.0
Длительность: 2–3 дня
Источник: ревизия ARCHITECTURE.md v3.13.40 + мастер-сессия v3.13.38
Отчёт: prompts/reports/day_53_4a_add5_hotfix_and_sync_report.md

🎯 Цель
Закрыть 2 критичных бага (BUG-150, BUG-149) + 2 UI-задачи
(BACKLOG-121, BACKLOG-119) + синхронизировать ARCHITECTURE.md с реальным кодом.

📋 Задачи
🔴 BUG-150 — DELETE /api/resources/{id} → 500 (FK violation)
Проблема: 9+ FK с NO ACTION не позволяют удалить ресурс.
Падает sqlalchemy.exc.IntegrityError: failed_files_task_id_fkey.

Файлы: manager/src/db/migrations/007_add_cascade_deletes.py (NEW).

Решение: Alembic-миграция с ON DELETE CASCADE для FK, ссылающихся
на resources.id и scan_tasks.id.

python
"""Add ON DELETE CASCADE to foreign keys referencing resources and scan_tasks

Revision ID: 007
Revises: 006
Create Date: 2026-10-12
"""
from alembic import op

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None

CASCADE_FKS = [
    ('findings',           'resource_id', 'resources',  'id', 'findings_resource_id_fkey'),
    ('findings',           'task_id',     'scan_tasks', 'id', 'findings_task_id_fkey'),
    ('scan_tasks',         'resource_id', 'resources',  'id', 'scan_tasks_resource_id_fkey'),
    ('catalog_entries',    'resource_id', 'resources',  'id', 'catalog_entries_resource_id_fkey'),
    ('access_entries',     'resource_id', 'resources',  'id', 'access_entries_resource_id_fkey'),
    ('access_alerts',      'resource_id', 'resources',  'id', 'access_alerts_resource_id_fkey'),
    ('permission_changes', 'resource_id', 'resources',  'id', 'permission_changes_resource_id_fkey'),
    ('failed_files',       'task_id',     'scan_tasks', 'id', 'failed_files_task_id_fkey'),
    ('schedules',          'resource_id', 'resources',  'id', 'schedules_resource_id_fkey'),
]


def upgrade():
    for table, col, ref_table, ref_col, cname in CASCADE_FKS:
        op.drop_constraint(cname, table, type_='foreignkey')
        op.create_foreign_key(cname, table, ref_table, [col], [ref_col], ondelete='CASCADE')


def downgrade():
    for table, col, ref_table, ref_col, cname in CASCADE_FKS:
        op.drop_constraint(cname, table, type_='foreignkey')
        op.create_foreign_key(cname, table, ref_table, [col], [ref_col])
⚠️ Не трогать: audit_logs (партиционированная), findings_old (legacy),
findings.reviewed_by (FK → users.id).

⚠️ Имена constraint'ов уточнить в БД: \d findings в psql.

Тест: tests/unit/test_delete_resource_v31341.py — создание ресурса → scan →
findings → delete → 204 → проверка, что findings удалены.

Связано: BACKLOG-128 (нет кнопки удаления в UI), BACKLOG-129 (FK без CASCADE).

🔴 BUG-149 — S3LineConnector возвращает 0 files
Проблема: после BUG-148 (ENV читается) S3-скан всё равно возвращает 0 files.

Файлы: scanner/connectors/s3_line_connector.py.

Диагностика (есть доступ к MinIO):

ENV: S3_ACCESS_KEY / S3_SECRET_KEY подхватились из .env? Лог [LineScan] S3LineConnector: ....

prefix: в scan_config.connector.s3.prefix — что? В path — s3://bucket/prefix/?

list_objects_v2: логи DEBUG — сколько ключей вернулось?

endpoint: совпадает с реальным MinIO (host.docker.internal:9000)?

bucket: совпадает с реальным (dcap-audit-logs)?

_discover_keys: prefix or self._prefix — что подставляется?

Возможные причины:

prefix в scan_config пустой, path игнорируется (53.3-fix-s3-bucket) → 0 files.

endpoint не совпадает.

ENV не подхватились (BUG-148 — проверить).

Тест: tests/e2e/test_s3_scan_v31341.py — S3-скан MinIO → > 0 files, ≥ 9 находок.

🟡 BACKLOG-121 — .btn-primary → white filled
Проблема: в 53.4a было отклонение от DESIGN.md — dark carbon #1e1e1e.
Решение сессии: вернуть white filled #ffffff.

Файл: webui/static/css/components.css.

css
.btn-primary {
    background-color: var(--color-snow);  /* #ffffff */
    color: var(--color-page-ink);         /* #0a0a0a */
    border: none;
}
.btn-primary:hover {
    background-color: var(--color-ash);   /* #a7a7a7 */
    color: var(--color-page-ink);
}
.btn-primary:focus,
.btn-primary:active {
    background-color: var(--color-snow);
    color: var(--color-page-ink);
    box-shadow: none;
}
.btn-primary:disabled,
.btn-primary.disabled {
    background-color: var(--color-fog);   /* #7c7c7c */
    color: var(--color-page-ink);
}
Проверить: /login, /resources, /findings, /users, /roles, /settings.

Скриншоты: до/после (1920px).

🟡 BACKLOG-119 — Убрать hybrid badge из /login
Проблема: badge «Гибридный режим» на /login — избыточно.

Файл: webui/templates/login.html.

Фикс: убрать badge, если auth_mode == 'hybrid'.
Badge оставить только для windows_integrated (если нужно).

Не трогать: сам режим hybrid в коде — остаётся до v3.1.0 (B.1).
Поле «Домен» — v3.1.0.

📋 Синхронизация ARCHITECTURE.md
Задача: пройти по ARCHITECTURE.md v3.13.40, сверить каждый раздел с реальным кодом.

Чек-лист (10 пунктов)
#	Раздел	Что проверить
1	Структура проекта	Все файлы существуют? audit_helper.py, schemas_audit.py, tests/unit/*_v31339.py?
2	API ЭНДПОИНТЫ	PUT/DELETE /api/auth/roles/{id} — есть? GET /api/audit/{id} — есть? POST /api/audit/permissions — есть?
3	Роли	require_* актуальны? Системные роли иммутабельны?
4	mTLS	relaxed/strict, machine_prefixes — актуальны?
5	Findings	Модель Finding — все колонки? MASK_RULES — 19/11? _CONTEXT_PATTERNS — 22?
6	S3-коннектор	S3LineConnector, factory.py, _text_scanner.py — актуальны? Bucket/prefix/endpoint? BUG-149?
7	WebUI-редизайн	CSS-файлы? Шрифты 352/113 KB? theme.js удалён? .btn-primary white?
8	Мониторинг	Метрики, порты — актуальны?
9	Retention	Политики, archive_enabled — актуально?
10	Ключевые решения	Все решения актуальны? .btn-primary white filled?
Что добавить/исправить
#	Что	Где	Действие
1	BUG-150	API «Ресурсы» + «Известные ограничения»	Убрать «каскадно»; добавить ⚠️ BUG-150 → ✅
2	BUG-149	«S3-КОННЕКТОР» + «Известные ограничения»	Добавить ⚠️ BUG-149 → ✅
3	BUG-148	«Секреты S3»	Добавить: load_dotenv() + .bat парсит .env (v3.13.39)
4	BACKLOG-121	«Отличия от DESIGN.md» + «Ключевые решения»	White filled вместо dark-carbon
5	BACKLOG-119	«Режимы аутентификации»	Примечание: badge убран в 53.4a-доп5, режим остаётся до v3.1.0
6	JWT ключ	«Аутентификация»	Новый подраздел «WebUI: хранение токена» — dcap_access_token
7	BUG-176	—	Уже исправлено (PUT/DELETE /roles есть) ✅
8	tests/unit	Структура	455 passed (v3.13.39) + новые
9	docs/DESIGN.md	Структура docs/	План git mv в 53.4e — оставить
10	--shadow-*	«Отличия от DESIGN.md»	Ок, отражено
Новый подраздел «WebUI: хранение токена»
markdown
### WebUI: хранение токена

JWT хранится в `localStorage['dcap_access_token']` (префикс `dcap_`).
Дополнительно `localStorage['dcap-sidebar']` — состояние sidebar.

`webui/static/js/auth.js`:
- `setToken(null)` → `removeItem` (не пишет `null`).
- `getToken()` → `null` (если нет ключа).
- `authHeaders()` → `'Bearer ${token}'`.
- `login` → `setToken(data.access_token)`.
- `logout` → POST `/api/auth/logout` + `setToken(null)` + redirect.
- `me()` → при 401 → `setToken(null)` (авто-logout).
- `check()` → при 401 → redirect `/login`.
📋 Обновление STATE.md / ROADMAP.md / STATE_TEST_SESSION.md / CHANGELOG.md
STATE.md: версия → v3.13.41; BUG-150, BUG-149, BACKLOG-121, BACKLOG-119 → ✅;
unit-счётчик; следующий шаг → 53.4b.

ROADMAP.md: версия → v3.13.41; день 53.4a-доп5 (hotfix + sync) → ✅;
BUG-150, BUG-149, BACKLOG-121, BACKLOG-119 → ✅.

STATE_TEST_SESSION.md: BUG-150, BUG-149 → ✅; BUG-176 → ✅;
TEST-NOTE-NEW-6 (JWT ключ) → ✅.

CHANGELOG.md: запись о v3.13.41.

✅ Definition of Done
DELETE /api/resources/{id} → 204; связанные findings/tasks/catalog_entries удалены.

S3-скан MinIO → > 0 files, ≥ 9 находок.

.btn-primary — white filled на всех страницах.

/login без badge «Гибридный режим».

ARCHITECTURE.md синхронизирован с кодом (чек-лист 10 пунктов).

STATE.md / ROADMAP.md / STATE_TEST_SESSION.md обновлены.

Unit-регресс без падений; E2E — 53 passed / 7 skipped (эталон).

Скриншоты .btn-primary до/после (1920px).

VERSION=3.13.41 во всех compose.

💾 Коммит
bash
git add manager/src/db/migrations/007_add_cascade_deletes.py \
        scanner/connectors/s3_line_connector.py \
        webui/static/css/components.css \
        webui/templates/login.html \
        tests/unit/test_delete_resource_v31341.py \
        tests/e2e/test_s3_scan_v31341.py \
        ARCHITECTURE.md \
        .env .env.example \
        docker-compose.yml docker-compose.test.yml docker-compose.s3.yml \
        STATE.md ROADMAP.md STATE_TEST_SESSION.md CHANGELOG.md \
        prompts/tz/day_53_4a_add5_hotfix_and_sync.md \
        prompts/reports/day_53_4a_add5_hotfix_and_sync_report.md

git commit -m "fix: 53.4a-доп5 — hotfix BUG-150/149 + BACKLOG-121/119 + sync ARCHITECTURE.md (v3.13.41)

- BUG-150: DELETE /api/resources/{id} → 500 (9 FK с NO ACTION).
  Alembic-миграция 007_add_cascade_deletes.py: ON DELETE CASCADE для
  findings/scan_tasks/catalog_entries/access_entries/access_alerts/
  permission_changes/failed_files/schedules. audit_logs и findings_old не трогаются.
- BUG-149: S3LineConnector возвращал 0 files после BUG-148. Диагностика на живом MinIO.
- BACKLOG-121: .btn-primary → white filled, возврат к DESIGN.md.
- BACKLOG-119: badge «Гибридный режим» убран из /login (режим hybrid остаётся до v3.1.0).
- ARCHITECTURE.md: синхронизирован с кодом (10 пунктов): BUG-150/149/148, .btn-primary,
  hybrid badge, WebUI: хранение токена (dcap_access_token), BUG-176.
- STATE.md, ROADMAP.md, STATE_TEST_SESSION.md, CHANGELOG.md обновлены.
- VERSION 3.13.41.

Backlog: BUG-150, BUG-149, BACKLOG-121, BACKLOG-119 закрыты"
Конец ТЗ 53.4a-доп5
Файл: prompts/tz/day_53_4a_add5_hotfix_and_sync.md