# manager/tests/test_metrics_v3142.py
"""
Тесты метрик (v3.14.2, 53.4e-grafana hotfix).

- BUG-245: dcap_scanner_heartbeat_age_seconds / dcap_scanner_active должны
  иметь scanner_id равный id сканера ("1"), а не пустую строку "".
- BUG-246: dcap_findings_total — Gauge с реальным количеством findings в БД
  по типам (pii/credentials/...); dcap_findings_created_total — Counter за
  сессию (растёт при создании findings).
- BUG-247: dcap_findings_total больше не Counter, поэтому авто-метрика
  dcap_findings_created (timestamp) не генерируется.

Запуск: python -m pytest manager/tests/test_metrics_v3142.py -v
"""

import math
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from manager.src.db import models
from manager.src.db import session as session_module
from manager.src import metrics
from manager.src.auth import models as _auth_models  # noqa: F401  (регистрирует users/roles)


# ============================================================
# HELPERS
# ============================================================

def _label_keys(metric) -> list:
    """Ключи (наборы значений меток) серий метрики."""
    return list(metric._metrics.keys())


def _value(metric, **labels) -> float:
    return metric.labels(**labels)._value.get()


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(autouse=True)
def _reset_gauges():
    """Сброс gauge'ов до и после каждого теста (глобальный REGISTRY)."""
    metrics.scanner_active.clear()
    metrics.scanner_heartbeat_age.clear()
    metrics.findings_total.clear()
    yield
    metrics.scanner_active.clear()
    metrics.scanner_heartbeat_age.clear()
    metrics.findings_total.clear()


@pytest.fixture
def db_factory(monkeypatch):
    """In-memory SQLite + подмена session.SessionLocal на тестовую фабрику."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(session_module, "SessionLocal", testing_session)
    return testing_session


def _add_scanner(factory, scanner_id=1, status="active", last_heartbeat=None):
    db = factory()
    try:
        db.add(
            models.Scanner(
                id=scanner_id,
                name=f"scanner-{scanner_id}",
                status=status,
                last_heartbeat=last_heartbeat,
            )
        )
        db.commit()
    finally:
        db.close()


def _add_finding(factory, finding_type="pii", index=0):
    db = factory()
    try:
        db.add(
            models.Finding(
                resource_id=1,
                finding_type=finding_type,
                category="email",
                fragment_type="text_line",
                fingerprint=f"fp-{finding_type}-{index}",
                encryption_key_id="key-1",
            )
        )
        db.commit()
    finally:
        db.close()


# ============================================================
# BUG-245: scanner_id в метриках сканера
# ============================================================

def test_scanner_heartbeat_uses_scanner_id(db_factory):
    _add_scanner(db_factory, scanner_id=1, last_heartbeat=datetime.utcnow())

    metrics._refresh_scanner_gauges()

    keys = _label_keys(metrics.scanner_heartbeat_age)
    assert ("1",) in keys, keys
    assert ("",) not in keys, "BUG-245: серия scanner_id='' не должна появляться"
    assert _value(metrics.scanner_heartbeat_age, scanner_id="1") >= 0.0

    active_keys = _label_keys(metrics.scanner_active)
    assert ("1",) in active_keys, active_keys
    assert ("",) not in active_keys
    assert _value(metrics.scanner_active, scanner_id="1") == 1.0


def test_scanner_heartbeat_age_inf_without_heartbeat(db_factory):
    _add_scanner(db_factory, scanner_id=1, last_heartbeat=None)

    metrics._refresh_scanner_gauges()

    age = _value(metrics.scanner_heartbeat_age, scanner_id="1")
    assert math.isinf(age), age


def test_empty_db_produces_no_empty_scanner_label(db_factory):
    metrics._refresh_scanner_gauges()

    assert _label_keys(metrics.scanner_heartbeat_age) == []
    assert _label_keys(metrics.scanner_active) == []


# ============================================================
# BUG-246/247: findings из БД и счётчик за сессию
# ============================================================

def test_findings_total_reflects_db(db_factory):
    for i in range(2):
        _add_finding(db_factory, finding_type="pii", index=i)
    _add_finding(db_factory, finding_type="credentials", index=0)

    metrics._refresh_findings_gauges()

    assert _value(metrics.findings_total, type="pii") == 2
    assert _value(metrics.findings_total, type="credentials") == 1


def test_findings_total_is_gauge_not_counter():
    # BUG-247: имя dcap_findings_total больше не Counter (нет авто-_created).
    assert type(metrics.findings_total).__name__ == "Gauge"
    assert type(metrics.findings_created_total).__name__ == "Counter"


def test_track_findings_increments_session_counter():
    if hasattr(metrics.findings_created_total, "_metrics"):
        metrics.findings_created_total._metrics.clear()

    metrics.track_findings({"pii": 3})
    metrics.track_findings({"pii": 2})

    assert _value(metrics.findings_created_total, type="pii") == 5
