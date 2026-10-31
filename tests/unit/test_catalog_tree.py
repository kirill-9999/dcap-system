# tests/unit/test_catalog_tree.py — BUG-043 (Fix-спринт)
# _aggregate в /api/catalog/tree рекурсивно агрегировал детей, но «портил»
# дерево лишним преобразованием children в list на каждом уровне.
# Проверяем: дерево валидное, агрегаты корректные, без 500.
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from manager.src.db import models
from manager.src.db.session import get_db
from manager.src.api import catalog as catalog_api

pytestmark = [pytest.mark.unit]


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    app = FastAPI()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.include_router(catalog_api.router)
    return TestClient(app)


def _entry(db, path, total_findings=0, file_count=0):
    e = models.CatalogEntry(
        path=path,
        entry_metadata={
            "classifiers": {},
            "total_findings": total_findings,
            "file_count": file_count,
        },
        updated_at=datetime.utcnow(),
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _find_node_in(nodes, name):
    """Ищет узел по имени в списке дочерних узлов."""
    if not isinstance(nodes, list):
        return None
    for n in nodes:
        if n["name"] == name:
            return n
    return None


def test_tree_single_level(client, db_session):
    _entry(db_session, "E:/proj", total_findings=5, file_count=2)
    r = client.get("/api/catalog/tree")
    assert r.status_code == 200, r.text
    tree = r.json()
    # корень дерева: {"E:": node}; node.children — список
    e_node = tree.get("E:")
    assert e_node is not None
    proj = _find_node_in(e_node.get("children"), "proj")
    assert proj is not None
    assert proj["total_findings"] == 5
    assert proj["file_count"] == 2
    assert proj["has_findings"] is True
    # children — список (был dict/сломанное дерево в BUG-043)
    assert isinstance(proj.get("children"), list)


def test_tree_nested_aggregation(client, db_session):
    _entry(db_session, "E:/proj", total_findings=5, file_count=1)
    _entry(db_session, "E:/proj/src", total_findings=3, file_count=7)
    r = client.get("/api/catalog/tree")
    assert r.status_code == 200, r.text
    tree = r.json()
    e_node = tree.get("E:")
    assert e_node is not None
    proj = _find_node_in(e_node.get("children"), "proj")
    assert proj is not None
    # агрегат узла = свой + все дети (рекурсивно)
    assert proj["total_findings"] == 5 + 3
    assert proj["file_count"] == 1 + 7
    assert proj["has_findings"] is True
    # дочерние списки — валидные списки, а не dict
    assert isinstance(proj["children"], list)
    src = _find_node_in(proj["children"], "src")
    assert src is not None
    assert src["total_findings"] == 3
    assert src["children"] == []


def test_tree_zero_findings_no_flag(client, db_session):
    _entry(db_session, "E:/empty", total_findings=0, file_count=0)
    r = client.get("/api/catalog/tree")
    assert r.status_code == 200, r.text
    tree = r.json()
    e_node = tree.get("E:")
    assert e_node is not None
    empty = _find_node_in(e_node.get("children"), "empty")
    assert empty is not None
    assert empty["has_findings"] is False
    assert empty["total_findings"] == 0


def test_tree_empty_db(client, db_session):
    r = client.get("/api/catalog/tree")
    assert r.status_code == 200, r.text
    assert r.json() == {}