# tests/e2e/test_retention_e2e.py — BUG-102 (TASK-073, v3.13.27)
"""Live-проверка retention: Mapper[Finding] больше не роняет цикл.

Контекст. В v3.13.26 (День 49) при live-прогоне выяснилось: Celery-воркер падал
на `Finding.reviewer = relationship("User")`, потому что `User` определён в
`manager.src.auth.models`, а воркер этот модуль не импортировал. `run_retention`
формально отчитывался об успехе, но все 5 шагов возвращали
`"When initializing mapper Mapper[Finding(findings)], expression 'User' failed to
locate a name ('User')"`, то есть retention не делал ровно ничего.

Важная деталь про покрытие
--------------------------
`POST /api/retention/run` выполняет retention **синхронно в процессе Manager**
(`manager/src/api/retention.py:39`), а не через Celery. В процессе Manager
`auth.models` импортируется (там смонтирован auth-router), поэтому этот путь
работал даже при сломанном воркере — он не способен поймать BUG-102.

Через Celery задача уходит только через `POST /api/retention/start`
(`run_retention_task.delay`), и вот там баг проявлялся. Поэтому тест проверяет
оба пути:

  * `/api/retention/run?dry_run=true` — контракт ответа и отсутствие ошибок
    в 5 шагах (ожидание ТЗ);
  * `/api/retention/start` — задача реально ставится в очередь Celery, то есть
    путь, который падал в BUG-102, достижим.

Результат выполнения воркером проверить через API нельзя: `retention.state`
хранится в файле `data/retention_state.json` **внутри контейнера воркера**, а
том `manager/data` с воркером не смонтирован — Manager его не видит. Поэтому
worker-сторона подтверждается live-проверкой логов
(`docker compose logs celery_worker | Select-String "retention|mapper"`),
см. отчёт дня.
"""

import time

import pytest

MAPPER_ERROR_MARKERS = (
    "failed to locate a name",
    "mappers failed to initialize",
    "InvalidRequestError",
)

# Шаги полного цикла retention, которые обязаны присутствовать в результате.
EXPECTED_STEPS = (
    "archived_audit",
    "archived_findings",
    "cleaned_archive",
    "cleaned_tasks",
    "exported",
)


def _has_mapper_error(payload) -> bool:
    blob = repr(payload)
    return any(marker in blob for marker in MAPPER_ERROR_MARKERS)


def _findings_count(api_client, manager_url) -> int:
    r = api_client.get(f"{manager_url}/api/findings/count")
    assert r.status_code == 200, f"findings/count: {r.status_code} {r.text}"
    return r.json().get("total", 0)


@pytest.mark.e2e
@pytest.mark.requires_manager
def test_run_retention_live(api_client, manager_url):
    """Live: retention отрабатывает все 5 шагов без mapper-ошибки (BUG-102)."""
    findings_before = _findings_count(api_client, manager_url)

    # --- часть 1: API-путь, dry_run (ожидание ТЗ) --------------------------
    r = api_client.post(f"{manager_url}/api/retention/run", params={"dry_run": "true"})
    assert r.status_code == 200, f"retention/run: {r.status_code} {r.text}"

    body = r.json()
    assert body["status"] == "completed", f"Не completed: {body}"
    assert body["dry_run"] is True, f"dry_run не применён: {body}"

    result = body["result"]
    assert not _has_mapper_error(result), f"Mapper-ошибка в результате retention:\n{result}"

    for step in EXPECTED_STEPS:
        assert step in result, f"Шаг {step} отсутствует в результате: {sorted(result)}"
        assert "error" not in result[step], f"Шаг {step} вернул error: {result[step]}"

    # dry_run ничего не должен удалять — acceptance criterion ТЗ.
    assert _findings_count(api_client, manager_url) == findings_before, (
        "dry_run изменил количество findings — retention не в режиме dry_run"
    )

    # --- часть 2: путь Celery (тот самый, что падал в BUG-102) --------------
    r_start = api_client.post(f"{manager_url}/api/retention/start")
    if r_start.status_code == 503:
        pytest.skip("Celery broker недоступен — worker-путь проверить нельзя")
    assert r_start.status_code in (200, 202), f"retention/start: {r_start.status_code} {r_start.text}"

    started = r_start.json()
    assert started.get("status") == "queued", f"Задача не поставлена в очередь: {started}"
    assert started.get("task_id"), f"Celery не вернул task_id: {started}"

    # Даём воркеру подхватить задачу: при BUG-102 он падал на mapper init, и
    # «queued» без task_id/succeeded означал бы, что путь недоступен.
    time.sleep(2)