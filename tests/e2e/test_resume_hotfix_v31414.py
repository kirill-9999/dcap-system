"""53.4p (v3.14.14): E2E — resume без потери задачи."""
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for _p in (ROOT, os.path.join(ROOT, "scanner")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


@pytest.mark.skip(reason="E2E стенд (Manager :18000) и сканер требуются; сценарий описан в отчёте")
def test_resume_does_not_lose_task():
    pass


@pytest.mark.skip(reason="E2E стенд (Manager :18000) и сканер требуются; сценарий описан в отчёте")
def test_progress_monotonic():
    pass
