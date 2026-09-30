📄 ТЗ: BUG-102 — Retention и sweep_scheduled_scans падают на Mapper[Finding] ... 'User'
Файл: TZ_FIX_BUG102_CELERY_MAPPER.md
Версия: v3.13.26 → v3.13.27
Оценка: ~1 ч
Дата: 30.09.2026
Приоритет: 🔴 critical (блокер v3.0.0) — retention не работает вообще
Контекст: найдено в Блоке 7 (Retention) при live-прогоне v3.13.26

🎯 Проблема
В Celery-контексте (celery_worker) падают все задачи, работающие с моделью Finding:

run_retention — retention (архивация audit, очистка tasks, экспорт) — все 5 шагов падают.

sweep_scheduled_scans — запуск запланированных сканов — падает.

Retention формально succeeded, но фактически ничего не делает — все шаги возвращают ошибку.

📌 Доказательная база
Celery Worker logs (30.09.2026, 19:01:34)
text
Task manager.src.workers.tasks.run_retention[63383034-7cc3-49ba-87b8-c1da32bd6cc7] received
Loaded retention policies: ['audit_events', 'findings', 'tasks', 'logs']

[ERROR/ForkPoolWorker-4] Error archiving audit events:
One or more mappers failed to initialize - can't proceed with initialization
of other mappers. Triggering mapper: 'Mapper[Finding(findings)]'.
Original exception was: When initializing mapper Mapper[Finding(findings)],
expression 'User' failed to locate a name ('User'). If this is a class name,
consider adding this relationship() to the <class 'manager.src.db.models.Finding'>
class after both dependent classes have been defined.

[ERROR/ForkPoolWorker-4] Error archiving findings: ... (та же ошибка)
[ERROR/ForkPoolWorker-4] Error cleaning tasks: ... (та же ошибка)
[ERROR/ForkPoolWorker-4] Error exporting audit events: ... (та же ошибка)

[INFO/ForkPoolWorker-4] Retention run completed (dry_run=False)
Retention вернул:

json
{
  "archived_audit": {"archived": 0, "error": "One or more mappers failed ..."},
  "archived_findings": {"archived": 0, "error": "..."},
  "cleaned_archive": {
    "audit_logs_archive": {"deleted": 0, "error": "..."},
    "findings_archive": {"deleted": 0, "error": "..."}
  },
  "cleaned_tasks": {"deleted": 0, "error": "..."},
  "exported": {"exported": 0, "error": "..."},
  "rotated_logs": {"removed": []}
}
sweep_scheduled_scans (30.09.2026, 18:00:01)
text
[ERROR/ForkPoolWorker-4] sweep_scheduled_scans failed:
When initializing mapper Mapper[Finding(findings)],
expression 'User' failed to locate a name ('User'). ...

Task manager.src.workers.tasks.sweep_scheduled_scans[f0af13e1-...] succeeded in 0.3s:
{'error': "When initializing mapper Mapper[Finding(findings)], expression 'User' ..."}
🔍 Корень
Та же проблема, что в BUG-096 (v3.13.25), но в другом модуле:

Модель Finding (manager/src/db/models.py) содержит reviewed_by = Column(Integer, ForeignKey("users.id")).

SQLAlchemy при инициализации mapper ищет User в том же модуле (manager.src.db.models), но User определён в manager.src.auth.models.

В manager/src/api/findings.py — фикс BUG-096 (импорт AuthUser из auth.models). Но в manager/src/workers/tasks.py — импорта нет.

При первом обращении к Finding в Celery worker'е — mapper init падает.

Дополнительно: ошибка каскадная — после первого сбоя Mapper[Finding] все последующие попытки падают с тем же сообщением («One or more mappers failed to initialize - can't proceed with initialization of other mappers»).

🔧 Задача
TASK-072 (BUG-102) — фикс mapper в Celery
Файл: manager/src/workers/tasks.py (основной) + manager/src/workers/celery_app.py (альтернативный подход).

Вариант A (рекомендуемый) — явный импорт User в tasks.py
До первого использования моделей Finding / AuditLog — добавить:

python
# manager/src/workers/tasks.py

# BUG-102: импорт User ДО первого обращения к Finding/AuditLog —
# иначе SQLAlchemy mapper init падает ("expression 'User' failed to locate a name")
from manager.src.auth.models import User  # noqa: F401
from manager.src.db.models import (
    Finding, AuditLog, ScanTask, Resource, AuditLogArchive, ...
)
Ключевое: User должен быть импортирован до Finding / AuditLog. Если это невозможно (циклический импорт), использовать локальный импорт:

python
def run_retention(...):
    # BUG-102: локальный импорт ДО первого обращения к Finding
    from manager.src.auth.models import User  # noqa: F401
    from manager.src.db.models import Finding, AuditLog, ...
    ...
Вариант B — configure_mappers() в celery_app.py
Файл: manager/src/workers/celery_app.py

python
from celery import Celery
from sqlalchemy.orm import configure_mappers

# BUG-102: явная инициализация SQLAlchemy mappers после загрузки всех моделей
from manager.src.auth.models import User  # noqa: F401
from manager.src.db import models  # noqa: F401
configure_mappers()

celery_app = Celery("dcap", broker=..., backend=...)
Минус: нужен порядок импортов — все модели должны быть загружены до configure_mappers().

Вариант C — __init__.py в manager/src/db/
Файл: manager/src/db/__init__.py (если существует — дополнить):

python
"""DB-модуль DCAP. BUG-102: гарантирует загрузку User ДО mapper init."""
from manager.src.auth.models import User  # noqa: F401
from manager.src.db.models import *  # noqa: F401,F403
Риск: циклический импорт (auth.models → db.models?), нужно проверить.

Рекомендация: A (или B, если A сложен).

TASK-073 (BUG-102) — тесты
Unit tests/unit/test_celery_mapper_v31327.py:

python
"""BUG-102 (TASK-072, v3.13.27): mapper Finding не падает в Celery-контексте."""

import pytest


class TestCeleryMapperInit:
    def test_run_retention_no_mapper_error(self):
        """run_retention не возвращает error про mapper 'User'."""
        # Запустить run_retention (с моками БД)
        # Проверить: результат НЕ содержит "failed to locate a name ('User')"
        pass

    def test_sweep_scheduled_scans_no_mapper_error(self):
        """sweep_scheduled_scans не возвращает error про mapper 'User'."""
        pass

    def test_finding_mapper_initialized(self):
        """mapper Finding инициализируется без ошибок при импорте tasks."""
        from manager.src.workers import tasks  # noqa: F401
        from sqlalchemy.orm import configure_mappers
        configure_mappers()  # не должно падать
        pass

    def test_user_model_imported_before_finding(self):
        """В tasks.py User импортируется ДО Finding (статистический тест)."""
        import inspect
        from manager.src.workers import tasks
        source = inspect.getsource(tasks)
        idx_user = source.find("from manager.src.auth.models import User")
        idx_finding = source.find("from manager.src.db.models import")
        # Если User отсутствует вообще — fail
        assert idx_user > 0, "User не импортируется в tasks.py — BUG-102 вернётся"
E2E tests/e2e/test_retention_e2e.py:

python
def test_run_retention_live(admin_token, manager_url):
    """Live: POST /api/retention/run?dry_run=true → все шаги без error."""
    # Вызвать /api/retention/run?dry_run=true
    # Проверить: response.result НЕ содержит "error" с "mapper" / "User"
    # И содержит все 5 шагов: archived_audit, archived_findings,
    # cleaned_archive, cleaned_tasks, exported
    pass
Ожидание: +4 unit, +1 E2E.

🧪 Live-проверка (после фикса)
1. Пересборка
powershell
$env:VERSION="3.13.27"
docker compose build manager celery_worker celery_beat
docker compose up -d manager celery_worker celery_beat
Start-Sleep 20
Invoke-RestMethod http://127.0.0.1:8000/api/health
# → 3.13.27
2. Запустить retention dry_run через API
powershell
$base = "http://127.0.0.1:8000/api"
$adminToken = (Invoke-RestMethod -Method POST http://127.0.0.1:8000/api/auth/login `
  -ContentType "application/json" -Body '{"username":"admin","password":"admin123"}').access_token

$r = Invoke-RestMethod -Method POST "${base}/retention/run?dry_run=true" `
  -Headers @{ Authorization = "Bearer $adminToken" }
$r | ConvertTo-Json -Depth 6
Ожидание: все 5 шагов без error:

json
{
  "status": "completed",
  "dry_run": true,
  "result": {
    "archived_audit": {"archived": 0},         ← БЕЗ error
    "archived_findings": {"archived": 0},      ← БЕЗ error
    "cleaned_archive": {...},                   ← БЕЗ error
    "cleaned_tasks": {"deleted": 0, "dry_run": true},  ← БЕЗ error
    "exported": {"exported": 0},                ← БЕЗ error
    "rotated_logs": {"removed": []},
    "dry_run": true,
    "timestamp": "..."
  }
}
3. Проверить Celery Worker logs
powershell
docker compose logs celery_worker --tail 50 | Select-String -Pattern "retention|mapper|User|succeeded|failed"
Ожидание:

Task ... run_retention[...] succeeded in Xs: {...} — без error.

Нет Mapper[Finding] ... 'User' failed to locate.

4. Запустить реальный retention (dry_run=false)
⚠️ Осторожно: реально архивирует/удаляет данные. Проверить, что в БД есть данные под TTL:

sql
-- Есть ли tasks старше 30 дней?
SELECT COUNT(*) FROM scan_tasks WHERE created_at < NOW() - INTERVAL '30 days';

-- Есть ли audit_logs старше 90 дней?
SELECT COUNT(*) FROM audit_logs WHERE created_at < NOW() - INTERVAL '90 days';

-- Есть ли findings старше 180 дней?
SELECT COUNT(*) FROM findings WHERE first_seen_at < NOW() - INTERVAL '180 days';
Если все 0 — retention нечего делать (все данные свежие). Тогда реальный запуск безопасен (ничего не удалит).

Если > 0 — retention удалит/архивирует эти записи. Только если уверен, что это ожидаемо.

powershell
# Запуск реального retention
$r = Invoke-RestMethod -Method POST "${base}/retention/run?dry_run=false" `
  -Headers @{ Authorization = "Bearer $adminToken" }
$r | ConvertTo-Json -Depth 6
5. sweep_scheduled_scans — проверить
powershell
docker compose logs celery_worker --tail 100 | Select-String -Pattern "sweep_scheduled_scans"
Ожидание: после фикса — задача либо не запускается (нет расписания), либо запускается без mapper-ошибки.

✅ Критерии приёмки
□ python -m py_compile manager/src/workers/tasks.py — OK
□ pytest tests/unit/test_celery_mapper_v31327.py -v — 4 passed
□ pytest tests/e2e/test_retention_e2e.py -v — 1 passed
□ Полный unit: 305+ passed (301 + 4)
□ Manager /api/health → 3.13.27
□ Live: POST /api/retention/run?dry_run=true → все 5 шагов без error
□ Live: Celery Worker logs — нет Mapper[Finding] ... 'User' failed to locate
□ Live: sweep_scheduled_scans — без mapper-ошибки
□ findings, audit_logs, scan_tasks — не изменились (после dry_run)
□ Обновлены STATE.md, ROADMAP.md, CHANGELOG.md
📝 Сводка правок
#	Файл	Действие	Задача
1	manager/src/workers/tasks.py	Явный импорт User из auth.models до Finding	TASK-072
2	(опционально) manager/src/workers/celery_app.py	configure_mappers() после импортов	TASK-072 alt
3	(опционально) manager/src/db/__init__.py	Гарантия загрузки User	TASK-072 alt
4	tests/unit/test_celery_mapper_v31327.py	Создать (4 теста)	TASK-073
5	tests/e2e/test_retention_e2e.py	Создать (1 тест)	TASK-073
6	docker-compose.yml	VERSION → 3.13.27	релиз
7	STATE.md, ROADMAP.md, CHANGELOG.md	BUG-102 → ✅	док
📌 Проверить заодно — есть ли другие Celery-задачи с той же проблемой
powershell
Get-ChildItem -Path "manager\src\workers" -Recurse -Filter *.py |
  Select-String -Pattern "from manager.src.db.models import" -Context 0,3
Если есть ещё файлы, работающие с Finding без импорта User — исправить тем же способом.

Также — проверить sweep_scheduled_scans:

powershell
Select-String -Path "manager\src\workers\tasks.py" -Pattern "def sweep_scheduled_scans" -Context 0,15
Смотрим, что он делает и какие модели использует.

🚀 После закрытия
BUG-102 → ✅ v3.13.27

Retention заработает — архивация, очистка, экспорт.

sweep_scheduled_scans заработает — запланированные сканы.

Блок 7 (Retention) полностью закрыт.

📌 Дополнительные заметки
TEST-NOTE-7.1…7.5 (из тестирования Retention):

ID	Название	Приоритет
TEST-NOTE-7.1	findings_archive — legacy-таблица (старая модель findings), не в ARCHITECTURE.md	📋 док
TEST-NOTE-7.2	last_run / last_result retention не сохраняются в БД (только в памяти)	📋 v3.1.0
TEST-NOTE-7.3	findings.ttl_days=180 — без архивации (в отличие от audit)	📋 v3.1.0
TEST-NOTE-7.4	dry_run через API работает (даже без Celery)	✅
TEST-NOTE-7.5	Flower не видит worker'ов (Inspect failed) — не критично	🟢 v3.1.0
Эти — в ROADMAP/STATE (не в этом ТЗ).

Автор ТЗ: архитектор
Дата: 30.09.2026
Статус: готово к передаче разработчику
Ожидаемый результат: v3.13.27, BUG-102 → ✅