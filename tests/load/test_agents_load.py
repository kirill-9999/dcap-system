# tests/load/test_agents_load.py
import concurrent.futures
import os
import time
import uuid

import pytest

AGENT_NAME = f"load-agent-{uuid.uuid4().hex[:8]}"
_TIMEOUT = (5, 300)


def _make_event(i):
    return {
        "event_source": "linux_agent",
        "event_type": "file_access",
        "user": f"user_{i % 100}",
        "file_path": f"/tmp/file_{i}.txt",
        "source_host": "load-test-host",
    }


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.requires_manager
def test_10000_events(api_client, manager_url):
    """Отправка 10 000 событий от имени агента. Порог: <60 сек, без 5xx."""
    # 1. Регистрируем агента
    r = api_client.post(
        f"{manager_url}/api/audit/agents/register",
        json={"name": AGENT_NAME, "hostname": "load-test-host", "version": "3.7.0"},
        timeout=_TIMEOUT,
    )
    assert r.status_code in (200, 201), f"Register failed: {r.text}"
    agent_id = r.json().get("agent_id")
    assert agent_id

    # 2. Отправляем батчами по 100
    N = int(os.getenv("DCAP_LOAD_EVENTS", "10000"))
    BATCH = 100
    errors = []
    saved = []

    def send_batch(start_idx):
        events = [_make_event(start_idx + j) for j in range(BATCH)]
        try:
            r = api_client.post(
                f"{manager_url}/api/audit/events",
                json={"agent_id": agent_id, "events": events},
                timeout=_TIMEOUT,
            )
            if r.status_code >= 500:
                errors.append(r.status_code)
            else:
                saved.append(r.json().get("saved", 0))
        except Exception as e:
            errors.append(str(e))

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(send_batch, range(0, N, BATCH)))
    duration = time.time() - start

    assert len(errors) == 0, f"Errors: {errors[:5]}"
    assert duration < 60, f"Too slow: {duration:.1f}s for {N} events"

    total_saved = sum(saved)
    assert total_saved > 0, "No events saved"
    print(f"\n[X] {N} events in {duration:.1f}s ({N / duration:.0f} events/s) | "
          f"saved={total_saved}")