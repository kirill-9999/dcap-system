#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Catalog Manager
Управление каталогом папок с находками в JSONL формате
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import threading


@dataclass
class FolderRecord:
    """Запись о папке с находками"""
    folder_path: str
    folder_path_unc: str
    source_type: str
    first_detected: str
    last_scanned: str
    scan_count: int
    findings_summary: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "folder_path": self.folder_path,
            "folder_path_unc": self.folder_path_unc,
            "source_type": self.source_type,
            "first_detected": self.first_detected,
            "last_scanned": self.last_scanned,
            "scan_count": self.scan_count,
            "findings_summary": self.findings_summary
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FolderRecord':
        return cls(
            folder_path=data.get("folder_path", ""),
            folder_path_unc=data.get("folder_path_unc", ""),
            source_type=data.get("source_type", "filesystem"),
            first_detected=data.get("first_detected", datetime.now().isoformat()),
            last_scanned=data.get("last_scanned", datetime.now().isoformat()),
            scan_count=data.get("scan_count", 0),
            findings_summary=data.get("findings_summary", {})
        )


class CatalogManager:
    """
    Менеджер каталога папок с находками.
    Формат: JSONL (каждая папка на отдельной строке)
    """
    
    def __init__(self, catalog_dir: str):
        self.catalog_dir = Path(catalog_dir)
        self.catalog_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_file = self.catalog_dir / "folders_catalog.jsonl"  # ← JSONL формат
        self.catalog: Dict[str, FolderRecord] = {}
        self._dirty = False
        self._lock = threading.Lock()
        self._load()
    
    def _load(self):
        """Загрузка каталога из JSONL файла"""
        if not self.catalog_file.exists():
            print(f"[CATALOG] Новый каталог: {self.catalog_file}")
            return
        
        try:
            with open(self.catalog_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        # Используем folder_path как ключ (уникальный идентификатор)
                        key = f"{data.get('source_type', 'filesystem')}:{data.get('folder_path', '')}"
                        self.catalog[key] = FolderRecord.from_dict(data)
                    except json.JSONDecodeError as e:
                        print(f"[CATALOG] Ошибка в строке {line_num}: {e}")
            
            print(f"[CATALOG] Загружено {len(self.catalog)} папок из {self.catalog_file}")
        except Exception as e:
            print(f"[CATALOG] Ошибка загрузки: {e}")
    
    def _save(self):
        """Сохранение каталога в JSONL формат (каждая папка на отдельной строке)"""
        if not self._dirty:
            return
        
        with self._lock:
            try:
                temp_file = self.catalog_dir / "folders_catalog.tmp"
                
                with open(temp_file, 'w', encoding='utf-8') as f:
                    for key, record in self.catalog.items():
                        # Каждая папка - отдельная JSON строка
                        line = json.dumps(record.to_dict(), ensure_ascii=False)
                        f.write(line + '\n')
                
                temp_file.replace(self.catalog_file)
                self._dirty = False
                
            except Exception as e:
                print(f"[CATALOG] Ошибка сохранения: {e}")
    
    def save(self, force: bool = False):
        """Сохранить каталог"""
        if force:
            self._dirty = True
        self._save()
    
    def update_folder(self, folder_path: str, source_type: str, 
                      classifier_name: str, findings: List) -> None:
        """
        Обновление информации о папке с находками
        """
        from core.base import ClassificationFinding
        
        # Нормализуем путь
        normalized_path = str(Path(folder_path).resolve())
        path_unc = f"\\\\?\\{normalized_path}" if len(normalized_path) > 200 else normalized_path
        
        # Ключ для каталога
        key = f"{source_type}:{normalized_path}"
        
        with self._lock:
            if key not in self.catalog:
                self.catalog[key] = FolderRecord(
                    folder_path=normalized_path,
                    folder_path_unc=path_unc,
                    source_type=source_type,
                    first_detected=datetime.now().isoformat(),
                    last_scanned=datetime.now().isoformat(),
                    scan_count=0,
                    findings_summary={}
                )
            
            record = self.catalog[key]
            record.last_scanned = datetime.now().isoformat()
            record.scan_count += 1
            
            # Обновляем сводку находок для этого классификатора
            if classifier_name not in record.findings_summary:
                record.findings_summary[classifier_name] = {
                    "subcategories": [],
                    "last_findings_count": 0
                }
            
            # Собираем уникальные подкатегории
            subcategories = set()
            for finding in findings:
                subcategories.add(finding.subcategory)
            
            record.findings_summary[classifier_name]["subcategories"] = list(subcategories)
            record.findings_summary[classifier_name]["last_findings_count"] = len(findings)
            
            self._dirty = True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики каталога"""
        total_folders = len(self.catalog)
        total_scans = sum(r.scan_count for r in self.catalog.values())
        
        classifier_stats = {}
        subcategory_stats = {}
        
        for record in self.catalog.values():
            for classifier_name, summary in record.findings_summary.items():
                classifier_stats[classifier_name] = classifier_stats.get(classifier_name, 0) + 1
                for subcat in summary.get("subcategories", []):
                    subcategory_stats[subcat] = subcategory_stats.get(subcat, 0) + 1
        
        return {
            "total_folders": total_folders,
            "total_scans": total_scans,
            "classifier_stats": classifier_stats,
            "subcategory_stats": subcategory_stats
        }
    
    def get_folder_info(self, folder_path: str, source_type: str = "filesystem") -> Optional[FolderRecord]:
        """Получение информации о папке"""
        normalized_path = str(Path(folder_path).resolve())
        key = f"{source_type}:{normalized_path}"
        return self.catalog.get(key)
    
    def export_to_json(self) -> Path:
        """
        Экспорт в читаемый JSON формат (для просмотра)
        """
        export_file = self.catalog_dir / "folders_catalog_export.json"
        
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "total_folders": len(self.catalog),
            "folders": {}
        }
        
        for key, record in self.catalog.items():
            # Используем folder_path как ключ (без source_type:)
            data["folders"][record.folder_path] = record.to_dict()
        
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[CATALOG] Экспорт в читаемый JSON: {export_file}")
        return export_file


__all__ = ['CatalogManager', 'FolderRecord']