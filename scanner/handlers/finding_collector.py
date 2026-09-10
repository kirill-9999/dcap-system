#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Finding Collector - Обработчик для сбора находок во время сканирования
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

from core.base import IOutputHandler, ClassificationResult, FileContext, ClassificationFinding, DataCategory


class FindingCollector(IOutputHandler):
    """
    Обработчик для сбора всех находок в единую структуру данных.
    Используется внутри Orchestrator для накопления результатов.
    """
    
    def __init__(self):
        self.findings: List[Dict[str, Any]] = []
        self.failed_files: List[Dict[str, Any]] = []
        self.files_scanned: int = 0
        self.files_with_findings: int = 0
        self.total_findings: int = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
        # Статистика по категориям
        self.category_stats: Dict[str, int] = defaultdict(int)
        self.subcategory_stats: Dict[str, int] = defaultdict(int)
        
        # Для дедупликации
        self._seen_findings: set = set()
        
        # Ограничения
        self.max_findings = 10000  # Максимальное количество находок
        self.max_failed_files = 1000  # Максимальное количество failed файлов
        
    @property
    def handler_name(self) -> str:
        return "finding_collector"
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Настройка обработчика"""
        self.max_findings = config.get("max_findings", 10000)
        self.max_failed_files = config.get("max_failed_files", 1000)
        
    def write(self, result: ClassificationResult, file_context: FileContext) -> None:
        """
        Запись результата классификации
        
        Args:
            result: Результат классификации
            file_context: Контекст файла
        """
        # Обновляем счетчики
        self.files_scanned += 1
        
        if not result.success:
            # Если классификация не удалась
            self.failed_files.append({
                "path": file_context.path,
                "error": result.error or "Unknown error",
                "error_type": "classification_error"
            })
            return
        
        findings = result.findings
        if not findings:
            return
        
        # Обновляем статистику
        self.files_with_findings += 1
        self.total_findings += len(findings)
        
        # Добавляем находки
        for finding in findings:
            if len(self.findings) >= self.max_findings:
                break
                
            # Преобразуем в словарь для API
            finding_dict = self._convert_finding_to_dict(finding, file_context)
            
            # Дедупликация
            dedup_key = f"{finding_dict['file_path']}:{finding_dict['subcategory']}:{finding_dict['value']}"
            if dedup_key in self._seen_findings:
                continue
            self._seen_findings.add(dedup_key)
            
            self.findings.append(finding_dict)
            
            # Обновляем статистику по категориям
            category = finding_dict.get("category", "unknown")
            subcategory = finding_dict.get("subcategory", "unknown")
            self.category_stats[category] += 1
            self.subcategory_stats[subcategory] += 1
    
    def _convert_finding_to_dict(self, finding: ClassificationFinding, file_context: FileContext) -> Dict[str, Any]:
        """
        Преобразование ClassificationFinding в словарь для API
        
        Args:
            finding: Объект ClassificationFinding
            file_context: Контекст файла
            
        Returns:
            Dict: Словарь с данными находки
        """
        # Получаем категорию как строку
        category = finding.category
        if hasattr(category, 'value'):
            category = category.value
        else:
            category = str(category)
        
        return {
            "file_path": file_context.path,
            "line_number": finding.position if hasattr(finding, 'position') else 0,
            "category": category,
            "subcategory": finding.subcategory if hasattr(finding, 'subcategory') else "",
            "value": finding.value[:500] if hasattr(finding, 'value') else "",
            "confidence": finding.confidence if hasattr(finding, 'confidence') else 0.0,
            "context": finding.context[:500] if hasattr(finding, 'context') else "",
            "detection_method": finding.detection_method if hasattr(finding, 'detection_method') else "unknown"
        }
    
    def add_failed_file(self, file_path: str, error: str, error_type: str = "unknown") -> None:
        """
        Добавить файл с ошибкой
        
        Args:
            file_path: Путь к файлу
            error: Текст ошибки
            error_type: Тип ошибки
        """
        if len(self.failed_files) >= self.max_failed_files:
            return
        
        self.failed_files.append({
            "path": file_path,
            "error": error[:500],
            "error_type": error_type
        })
    
    def flush(self) -> None:
        """Сброс (ничего не делаем, данные уже собраны)"""
        pass
    
    def get_results(self) -> Dict[str, Any]:
        """
        Получить собранные результаты
        
        Returns:
            Dict: Словарь с результатами
        """
        # Сортируем находки по confidence (убывание)
        sorted_findings = sorted(
            self.findings,
            key=lambda x: x.get('confidence', 0),
            reverse=True
        )
        
        return {
            "findings": sorted_findings,
            "failed_files": self.failed_files,
            "stats": {
                "files_scanned": self.files_scanned,
                "files_with_findings": self.files_with_findings,
                "files_failed": len(self.failed_files),
                "total_findings": self.total_findings,
                "unique_findings": len(self.findings),
                "category_stats": dict(self.category_stats),
                "subcategory_stats": dict(self.subcategory_stats),
                "started_at": datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
                "completed_at": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
                "duration_seconds": (self.end_time - self.start_time) if self.start_time and self.end_time else 0
            }
        }
    
    def start_collection(self) -> None:
        """Начать сбор"""
        self.start_time = time.time()
        self.findings = []
        self.failed_files = []
        self.files_scanned = 0
        self.files_with_findings = 0
        self.total_findings = 0
        self._seen_findings = set()
        self.category_stats = defaultdict(int)
        self.subcategory_stats = defaultdict(int)
    
    def finish_collection(self) -> None:
        """Завершить сбор"""
        self.end_time = time.time()
    
    def reset(self) -> None:
        """Сброс всех данных"""
        self.findings = []
        self.failed_files = []
        self.files_scanned = 0
        self.files_with_findings = 0
        self.total_findings = 0
        self.start_time = None
        self.end_time = None
        self._seen_findings = set()
        self.category_stats = defaultdict(int)
        self.subcategory_stats = defaultdict(int)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику"""
        return {
            "files_scanned": self.files_scanned,
            "files_with_findings": self.files_with_findings,
            "files_failed": len(self.failed_files),
            "total_findings": self.total_findings,
            "unique_findings": len(self.findings),
            "category_stats": dict(self.category_stats),
            "subcategory_stats": dict(self.subcategory_stats)
        }
    
    @staticmethod
    def mask_value(value: str, keep: int = 4) -> str:
        """Маскирование значения секрета для лог-отчёта.
        
        Значение не выводится полностью — только первые `keep` символов
        и длина, чтобы избежать утечки секретов в текстовых отчётах/логах.
        """
        if not value:
            return ""
        value = str(value)
        if len(value) <= keep:
            return "*" * len(value)
        if value.startswith("<file: "):
            return value
        return value[:keep] + "*" * min(len(value) - keep, 20)
    
    def generate_report(self, file_path: Optional[str] = None) -> str:
        """Сгенерировать текстовый лог-отчёт о результатах сканирования.
        
        Отчёт не содержит значений секретов — только типы, количество,
        пути файлов и степень уверенности (confidence).
        
        Args:
            file_path: Если задан — отчёт только по этому файлу.
        
        Returns:
            str: Текст отчёта
        """
        lines = []
        lines.append("=" * 68)
        lines.append(f"DCAP SCAN REPORT — {datetime.now().isoformat(timespec='seconds')}")
        lines.append("=" * 68)
        lines.append(f"Files scanned      : {self.files_scanned}")
        lines.append(f"Files with findings: {self.files_with_findings}")
        lines.append(f"Files failed       : {len(self.failed_files)}")
        lines.append(f"Findings total     : {self.total_findings} (unique: {len(self.findings)})")
        if self.start_time and self.end_time:
            lines.append(f"Duration           : {self.end_time - self.start_time:.1f}s")
        
        if self.category_stats:
            lines.append("-" * 68)
            lines.append("BY CATEGORY")
            for cat, cnt in sorted(self.category_stats.items(), key=lambda x: -x[1]):
                lines.append(f"  {cat:<20} {cnt}")
        
        target_findings = self.findings
        if file_path:
            target_findings = [f for f in self.findings if f.get("file_path") == file_path]
            lines.append(f"\nFILE: {file_path}")
        
        if target_findings:
            lines.append("-" * 68)
            lines.append("FINDINGS (values masked)")
            
            # Группировка по категориям
            by_category = defaultdict(list)
            for f in target_findings:
                by_category[f.get("category", "unknown")].append(f)
            
            i = 0
            for cat in sorted(by_category.keys()):
                lines.append(f"\n  == {cat.upper()} ==")
                for f in by_category[cat]:
                    i += 1
                    value = self.mask_value(f.get("value", ""))
                    lines.append(
                        f"  {i:>4}. [{f.get('subcategory', 'unknown'):<24}] "
                        f"conf={f.get('confidence', 0):.2f} "
                        f"file={f.get('file_path', '?')}"
                    )
                    lines.append(f"        value={value} method={f.get('detection_method', '?')}")
        else:
            lines.append("\nNo findings.")
        
        if self.failed_files:
            lines.append("-" * 68)
            lines.append("[FAILED TO PROCESS]")
            for fail in self.failed_files[:50]:
                lines.append(f"  {fail.get('path', '?')}: {fail.get('error', '?')}")
            if len(self.failed_files) > 50:
                lines.append(f"  ... ещё {len(self.failed_files) - 50} файлов")
        
        lines.append("=" * 68)
        return "\n".join(lines)


__all__ = ['FindingCollector']