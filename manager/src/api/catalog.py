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
    
    # Строим дерево
    tree = {}
    
    for entry in entries:
        parts = entry.path.replace('\\', '/').split('/')
        current = tree
        
        for i, part in enumerate(parts):
            is_folder = i == len(parts) - 1
            
            if not current.get(part):
                current[part] = {
                    "name": part,
                    "is_folder": is_folder,
                    "path": '/'.join(parts[:i+1]),
                    "children": {},
                    "classifiers": entry.entry_metadata.get("classifiers", {}) if is_folder else None,
                    "total_findings": entry.entry_metadata.get("total_findings", 0) if is_folder else None,
                    "file_count": entry.entry_metadata.get("file_count", 0) if is_folder else None,
                    "last_scanned": entry.entry_metadata.get("last_scanned") if is_folder else None,
                    "updated_at": entry.updated_at.isoformat() if is_folder and entry.updated_at else None
                }
            
            if is_folder:
                current[part]["has_findings"] = True
                current[part]["classifiers"] = entry.entry_metadata.get("classifiers", {})
                current[part]["total_findings"] = entry.entry_metadata.get("total_findings", 0)
            else:
                current = current[part]["children"]
    
    return tree

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