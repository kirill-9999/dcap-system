"""Тесты BUG-102 (TASK-073, v3.13.27): Mapper[Finding] падал в Celery-контексте.

Первопричина: в `manager/src/db/models.py` связь объявлена строкой —
    reviewer = relationship("User", foreign_keys=[reviewed_by])
а сам `User` определён в другом модуле, `manager/src/auth/models.py`.

Celery worker импортировал только `db.session`, поэтому `User` не попадал в
registry, и первое же обращение к `Finding` роняло инициализацию mapper'ов
**всего** registry одним проходом:

    When initializing mapper Mapper[Finding(findings)],
    expression 'User' failed to locate a name ('User').

Из-за каскадности падало всё подряд: `run_retention` формально возвращал
`succeeded`, но все 5 шагов (archived_audit, archived_findings,
cleaned_archive, cleaned_tasks, exported) содержали этот error, и
`sweep_scheduled_scans` возвращал `{"error": "When initializing mapper ..."}`.
То есть retention не работал вообще.

Почему регрессионный тест запускается в подпроцессе
-----------------------------------------------------
`User` нужен в registry глобально и появляется там при первом же импорте любого
API-модуля. Если pytest уже импортировал `manager.src.auth.models` в ходе
предыдущего теста, registry «вылечен» и баг в том же процессе не
воспроизводится — тест прошёл бы и на сломанном коде. Поэтому ключевой тест
поднимает **чистый интерпретатор**, где импортируется ровно то, что импортирует
Celery worker, и зовёт `configure_mappers()`. Такой тест падает на коде до
фикса и проходит после — независимо от порядка тестов.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Сообщение, ради которого написан весь фикс.
MAPPER_ERROR_MARKERS = (
    "failed to locate a name",
    "mappers failed to initialize",
    "InvalidRequestError",
)

# Скрипт, имитирующий импорт Celery-воркера: только celery_app/tasks, без auth.
_WORKER_CTX_SNIPPET = """
import sys
sys.path.insert(0, {root!r})
from sqlalchemy.orm import configure_mappers
configure_mappers()
from manager.src.db.models import Finding
assert Finding.reviewer.property.mapper.class_.__name__ == "User"
print("MAPPER_OK")
"""


def _run_worker_context(imports: str) -> subprocess.CompletedProcess:
    """Запустить свежий интерпретатор с указанными импортами."""
    script = f"""
import sys
sys.path.insert(0, {str(REPO_ROOT)!r})
{imports}
from sqlalchemy.orm import configure_mappers
configure_mappers()
print("MAPPER_OK")
"""
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        encoding="utf-8",
        timeout=180,
    )


def _assert_no_mapper_error(payload, where: str) -> None:
    """Ни один вложенный dict/str в результате не содержит mapper-ошибку."""
    blob = repr(payload)
    for marker in MAPPER_ERROR_MARKERS:
        assert marker not in blob, f"{where}: найдено {marker!r} в результате:\n{blob}"


# ============================================================
# Регрессия: чистый Celery-контекст
# ============================================================


class TestCeleryMapperInit:
    def test_worker_context_mapper_init(self):
        """Импорт tasks.py + configure_mappers() не падает (главный тест BUG-102).

        До фикса — `expression 'User' failed to locate a name ('User')`.
        """
        proc = _run_worker_context("import manager.src.workers.tasks")

        assert proc.returncode == 0, (
            "Celery-контекст не инициализирует mapper'ы — BUG-102 вернулся.\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
        assert "MAPPER_OK" in proc.stdout, f"Не долетел маркер OK:\n{proc.stdout}"
        _assert_no_mapper_error(proc.stderr, "worker ctx")

    def test_finding_mapper_initialized(self):
        """Finding.reviewer резолвится именно в User после импорта tasks."""
        proc = _run_worker_context("import manager.src.workers.tasks")

        assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
        assert "MAPPER_OK" in proc.stdout

    @pytest.mark.parametrize(
        "module",
        [
            "manager.src.workers.tasks",
            "manager.src.workers.celery_app",
            "manager.src.retention.archiver",
            "manager.src.retention.cleaner",
            "manager.src.retention.exporter",
            "manager.src.services.access_service",
        ],
    )
    def test_modules_importable_standalone(self, module):
        """Каждый модуль, работающий с Finding, вызывает mapper init без ошибок.

        Раньше `retention/*` и `access_service` работали только потому, что
        в API-процессе раньше них импортировался `auth.models`. В Celery
        worker и при standalone-запуске такой гарантии не было.
        """
        proc = _run_worker_context(f"import {module}")

        assert proc.returncode == 0, (
            f"{module} не инициализирует mapper'ы самостоятельно:\n{proc.stderr}"
        )

    def test_user_model_imported_before_finding(self):
        """Статическая проверка: User импортируется в точках входа (BUG-102 не вернётся)."""
        import inspect

        from manager.src.workers import tasks

        # workers/__init__.py экспортирует объект Celery под именем `celery_app`,
        # поэтому модуль достаём из sys.modules.
        celery_app_module = sys.modules["manager.src.workers.celery_app"]

        for module in (tasks, celery_app_module):
            source = inspect.getsource(module)
            assert "from manager.src.auth.models import User" in source, (
                f"{module.__name__} не импортирует User — BUG-102 вернётся"
            )


# ============================================================
# Функциональные сценарии в контексте Celery-воркера
# ============================================================
#
# `Base.metadata.create_all` требует, чтобы таблица `users` была в MetaData, а она
# появляется там только при импорте `manager.src.auth.models` — то есть
# импортировать его нельзя, иначе registry заранее «вылечен» и баг не воспроизведётся.
#
# Поэтому схема готовится в родительском процессе (где auth.models и так импортирован)
# и сохраняется в файл SQLite, а сценарий в свежем интерпретаторе открывает этот файл
# и работает ровно так, как Celery worker: auth.models не импортирован, `users`
# в registry отсутствует. На коде до фикса сценарий падает с настоящей ошибкой
# "When initializing mapper Mapper[Finding(findings)] ... failed to locate a
# name ('User')", а не с NoReferencedTableError.

_RETENTION_SCENARIO = """
import json, sys
sys.path.insert(0, {root!r})

# Точка входа Celery-воркера.
import manager.src.workers.tasks  # noqa: F401

from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from manager.src.db.models import Resource, Schedule
from manager.src.retention import runtime
from manager.src.workers import tasks as celery_tasks

# ВАЖНО: manager.src.auth.models здесь намеренно НЕ импортируется. Схема уже
# готова в файле, который передан из родительского процесса; таблица users
# физически существует, но в registry её нет — ровно как в Celery worker до фикса.
engine = create_engine("sqlite:///" + {db_path!r})
factory = sessionmaker(bind=engine)

# run_retention берёт SessionLocal из retention.runtime, задачи Celery — из
# manager.src.workers.tasks (импорт верхнего уровня). Подменяем оба, иначе
# сценарий дёргал бы боевую БД.
runtime.SessionLocal = factory
celery_tasks.SessionLocal = factory

runtime.get_config = lambda: {{
    "retention": {{
        "enabled": True,
        "audit_events": {{"ttl_days": 90, "archive_ttl_days": 365,
                         "archive_enabled": True}},
        "findings": {{"ttl_days": 180}},
        "tasks": {{"ttl_days": 30}},
        "logs": {{"rotate_days": 30, "max_size_mb": 100}},
        "export": {{"enabled": True, "format": "json", "path": {export_dir!r}}},
    }}
}}
runtime.clean_log_rotation = lambda *a, **kw: {{"removed": []}}

# --- часть 1: run_retention -------------------------------------------------
result = runtime.run_retention(dry_run=True)
print("RETENTION=" + json.dumps(result, default=str))

# --- часть 2: sweep_scheduled_scans ----------------------------------------
db = factory()
try:
    sched = db.query(Schedule).filter(Schedule.resource_id == 1).one()
    sched.next_run_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
finally:
    db.close()

dispatched = []
celery_tasks.scan_resource.apply_async = lambda args, queue: dispatched.append(
    [list(args), queue])
sweep = celery_tasks.sweep_scheduled_scans()
print("SWEEP=" + json.dumps(sweep, default=str))
print("DISPATCHED=" + json.dumps(dispatched))
"""


@pytest.fixture(scope="module")
def worker_db_file(tmp_path_factory):
    """SQLite-файл с полной схемой, подготовленный в родительском процессе.

    Родитель импортирует `manager.src.auth.models` (это нужно, чтобы в MetaData
    появилась таблица `users` для `findings.reviewed_by`), создаёт схему и одну
    активную запись Schedule. Воркер-сценарий затем открывает этот файл, не
    импортируя auth.models, — и получает контекст, идентичный реальному.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from manager.src.auth.models import Role, User  # noqa: F401
    from manager.src.db.models import Base, Resource, Schedule

    path = tmp_path_factory.mktemp("bug102") / "worker.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)

    db = sessionmaker(bind=engine)()
    try:
        res = Resource(path="C:/data/sweep", type="FILESYSTEM", status="ACTIVE")
        db.add(res)
        db.commit()
        db.add(
            Schedule(
                resource_id=res.id,
                cron_expression="*/5 * * * *",
                enabled=True,
            )
        )
        db.commit()
    finally:
        db.close()
        engine.dispose()

    return path


@pytest.fixture(scope="module")
def scenario_result(worker_db_file, tmp_path_factory):
    """Один запуск сценария на модуль: возвращает распарсенные результаты задач."""
    export_dir = tmp_path_factory.mktemp("bug102_export")
    script = _RETENTION_SCENARIO.format(
        root=str(REPO_ROOT),
        db_path=str(worker_db_file),
        export_dir=str(export_dir),
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        encoding="utf-8",
        timeout=300,
    )
    if proc.returncode != 0:
        pytest.fail(
            "Сценарий упал — баг, вероятно, вернулся:\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )

    parsed = {"stdout": proc.stdout, "stderr": proc.stderr}
    for line in proc.stdout.splitlines():
        for key in ("RETENTION", "SWEEP", "DISPATCHED"):
            prefix = key + "="
            if line.startswith(prefix):
                parsed[key.lower()] = json.loads(line[len(prefix) :])
    return parsed


class TestRetentionScenarios:
    def test_run_retention_no_mapper_error(self, scenario_result):
        """run_retention отрабатывает все 5 шагов без error (BUG-102).

        До фикса возвращал `succeeded`, но каждый шаг содержал
        "When initializing mapper Mapper[Finding(findings)] ... failed to locate
        a name ('User')" — то есть retention не делал ровно ничего.
        """
        result = scenario_result["retention"]

        assert "error" not in result, f"run_retention вернул верхний error: {result}"
        for step in (
            "archived_audit",
            "archived_findings",
            "cleaned_archive",
            "cleaned_tasks",
            "exported",
        ):
            assert step in result, f"Шаг {step} отсутствует: {sorted(result)}"
            assert "error" not in result[step], f"Шаг {step} вернул error: {result[step]}"

    def test_sweep_scheduled_scans_no_mapper_error(self, scenario_result):
        """sweep_scheduled_scans не возвращает {'error': 'When initializing mapper ...'}.

        `scheduled_scans` в ТЗ: та же каскадная ошибка, задача молча возвращала
        пустой результат, и расписания переставали запускать сканирования.
        """
        sweep = scenario_result["sweep"]

        assert "error" not in sweep, f"sweep вернул error: {sweep}"
        assert len(sweep["dispatched"]) == 1, f"Ожидалась 1 задача, получено: {sweep}"

    def test_scanned_task_dispatched_to_queue(self, scenario_result):
        """Из-за расписания задача уходит именно в очередь scanner_tasks."""
        dispatched = scenario_result["dispatched"]

        assert dispatched, f"Задача не поставлена в очередь: {dispatched}"
        assert dispatched[0][1] == "scanner_tasks", f"Неверная очередь: {dispatched}"

    def test_no_mapper_errors_in_worker_stderr(self, scenario_result):
        """Ни в stdout, ни в stderr сценария нет следов mapper-ошибки."""
        _assert_no_mapper_error(scenario_result["stdout"], "scenario stdout")
        _assert_no_mapper_error(scenario_result["stderr"], "scenario stderr")
