from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional
from datetime import datetime

from ..db import models, session

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

@router.get("")
def get_catalog(
    search: Optional[str] = Query(None, description="Поиск по пути папки"),
    category: Optional[str] = Query(None, description="Фильтр по категории (pii, credentials, code)"),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(session.get_db)
):
    """Получить каталог папок с находками"""
    query = db.query(models.CatalogEntry)
    
    if search:
        query = query.filter(
            or_(
                models.CatalogEntry.path.ilike(f"%{search}%"),
                models.CatalogEntry.path.ilike(f"%{search.replace(' ', '%')}%")
            )
        )
    
    if category:
        query = query.filter(
            models.CatalogEntry.entry_metadata.has_key("classifiers")
        ).filter(
            models.CatalogEntry.entry_metadata["classifiers"].has_key(category)
        )
    
    total = query.count()
    entries = query.order_by(models.CatalogEntry.updated_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "entries": [
            {
                "id": e.id,
                "path": e.path,
                "classifiers": e.entry_metadata.get("classifiers", {}),
                "total_findings": e.entry_metadata.get("total_findings", 0),
                "file_count": e.entry_metadata.get("file_count", 0),
                "last_scanned": e.entry_metadata.get("last_scanned"),
                "created_at": e.created_at.isoformat(),
                "updated_at": e.updated_at.isoformat() if e.updated_at else None
            }
            for e in entries
        ]
    }

@router.get("/tree")
def get_catalog_tree(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(session.get_db)
):
    """Получить дерево папок с находками"""
    query = db.query(models.CatalogEntry)
    
    if search:
        query = query.filter(
            or_(
                models.CatalogEntry.path.ilike(f"%{search}%"),
                models.CatalogEntry.path.ilike(f"%{search.replace(' ', '%')}%")
            )
        )
    
    if category:
        query = query.filter(
            models.CatalogEntry.entry_metadata.has_key("classifiers")
        ).filter(
            models.CatalogEntry.entry_metadata["classifiers"].has_key(category)
        )
    
    entries = query.order_by(models.CatalogEntry.path).all()

    # Строим дерево узлами-папками (W-60): корень/промежуточные считаются
    # папками, метаданные агрегируются рекурсивно по детям.
    tree = {}

    def _node(part_name, part_path, children=None):
        return {
            "name": part_name,
            "is_folder": True,
            "path": part_path,
            "children": children if children is not None else {},
            "classifiers": None,
            "total_findings": 0,
            "file_count": 0,
            "last_scanned": None,
            "updated_at": None,
            "has_findings": False,
        }

    leaf_meta = {}
    for entry in entries:
        meta = entry.entry_metadata or {}
        leaf_meta[entry.path.replace('\\', '/')] = {
            "classifiers": meta.get("classifiers", {}),
            "total_findings": meta.get("total_findings", 0),
            "file_count": meta.get("file_count", 0),
            "last_scanned": meta.get("last_scanned"),
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        }

    for full in sorted(leaf_meta, key=lambda x: (len(x.split('/')), x)):
        parts = full.split('/')
        current = tree
        acc = ""
        for i, part in enumerate(parts):
            acc = acc + "/" + part if acc else part
            if part not in current:
                current[part] = _node(part, acc)
            if i == len(parts) - 1:
                m = leaf_meta[full]
                n = current[part]
                n["classifiers"] = m["classifiers"]
                n["total_findings"] = m["total_findings"]
                n["file_count"] = m["file_count"]
                n["last_scanned"] = m["last_scanned"]
                n["updated_at"] = m["updated_at"]
                n["has_findings"] = True if (m["total_findings"] or m["file_count"]) else False
            else:
                current = current[part]["children"]

    def _aggregate(node):
        children = node["children"]
        if children:
            for child in children.values():
                _aggregate(child)
                node["total_findings"] += child["total_findings"] or 0
                node["file_count"] += child["file_count"] or 0
                if child["has_findings"]:
                    node["has_findings"] = True
                if child["last_scanned"] and (node["last_scanned"] is None
                                              or child["last_scanned"] > node["last_scanned"]):
                    node["last_scanned"] = child["last_scanned"]
                if child["updated_at"] and (node["updated_at"] is None
                                            or child["updated_at"] > node["updated_at"]):
                    node["updated_at"] = child["updated_at"]
        # BUG-043: единый тип children — list (листья были {} и ломали WebUI).
        node["children"] = list(children.values())
        return node

    result = {}
    for name, node in tree.items():
        result[name] = _aggregate(node)
    return result

@router.get("/stats")
def get_catalog_stats(
    db: Session = Depends(session.get_db)
):
    """Получить статистику по каталогу"""
    total_entries = db.query(models.CatalogEntry).count()
    
    # Статистика по классификаторам
    classifier_stats = {}
    entries = db.query(models.CatalogEntry).all()
    
    for entry in entries:
        classifiers = entry.entry_metadata.get("classifiers", {})
        for cat, info in classifiers.items():
            if cat not in classifier_stats:
                classifier_stats[cat] = {"folders": 0, "total_findings": 0}
            classifier_stats[cat]["folders"] += 1
            classifier_stats[cat]["total_findings"] += info.get("count", 0)
    
    # Последние обновленные
    latest = db.query(models.CatalogEntry).order_by(
        models.CatalogEntry.updated_at.desc()
    ).limit(10).all()
    
    return {
        "total_folders": total_entries,
        "classifier_stats": classifier_stats,
        "latest": [
            {
                "id": e.id,
                "path": e.path,
                "total_findings": e.entry_metadata.get("total_findings", 0),
                "updated_at": e.updated_at.isoformat() if e.updated_at else None
            }
            for e in latest
        ]
    }

@router.get("/search")
def search_catalog(
    q: str = Query(..., min_length=1),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(session.get_db)
):
    """Быстрый поиск по каталогу"""
    query = db.query(models.CatalogEntry).filter(
        models.CatalogEntry.path.ilike(f"%{q}%")
    ).order_by(models.CatalogEntry.path).limit(limit)
    
    entries = query.all()
    
    return [
        {
            "id": e.id,
            "path": e.path,
            "classifiers": e.entry_metadata.get("classifiers", {}),
            "total_findings": e.entry_metadata.get("total_findings", 0),
            "updated_at": e.updated_at.isoformat() if e.updated_at else None
        }
        for e in entries
    ]