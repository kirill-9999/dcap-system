# tests/fixtures/db.py — управление тестовыми данными (cleanup).


def cleanup_tasks(api_client, manager_url: str, created) -> None:
    """Удаляет созданные задания после теста (fail-open)."""
    for task_id in created:
        try:
            if task_id is not None:
                api_client.delete(f"{manager_url}/api/tasks/{task_id}")
        except Exception:
            pass


def find_task_ids(api_client, manager_url: str, path: str):
    """Поиск task_id по ресурсному пути (вспомогательный)."""
    r = api_client.get(f"{manager_url}/api/tasks", params={"limit": 1000})
    if r.status_code != 200:
        return []
    ids = []
    for t in r.json():
        # resource_id → path сверяется дополнительно в управляющем коде;
        # здесь возвращаем все id для выборочной чистки.
        ids.append(t["id"])
    return ids