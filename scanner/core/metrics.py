#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Метрики
Сбор и агрегация метрик производительности
"""

from typing import Dict, Any, List
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime

from core.base import ClassificationResult, DataCategory


@dataclass
class ProcessingStats:
    """Статистика обработки"""
    files_processed: int = 0
    total_findings: int = 0
    total_time: float = 0.0
    avg_time_per_file: float = 0.0
    findings_by_category: Dict[str, int] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0


class MetricsCollector:
    """Сборщик метрик"""
    
    def __init__(self):
        self.stats = ProcessingStats()
        self.file_times: List[float] = []
        self.start_time = None
    
    def start_processing(self) -> None:
        """Начало обработки"""
        import time
        self.start_time = time.time()
        self.stats.start_time = self.start_time
    
    def update(self, result: ClassificationResult) -> None:
        """Обновление метрик на основе результата"""
        self.stats.files_processed += 1
        self.stats.total_findings += len(result.findings)
        
        for finding in result.findings:
            category = finding.category.value
            self.stats.findings_by_category[category] = self.stats.findings_by_category.get(category, 0) + 1
    
    def add_processing_time(self, elapsed: float) -> None:
        """Добавление времени обработки файла"""
        self.file_times.append(elapsed)
        self.stats.total_time += elapsed
    
    def finish_processing(self) -> None:
        """Завершение обработки"""
        import time
        self.stats.end_time = time.time()
        if self.stats.files_processed > 0:
            self.stats.avg_time_per_file = self.stats.total_time / self.stats.files_processed
    
    def get_summary(self) -> Dict[str, Any]:
        """Получение сводки метрик"""
        return {
            "files_processed": self.stats.files_processed,
            "total_findings": self.stats.total_findings,
            "total_time": self.stats.total_time,
            "avg_time_per_file": self.stats.avg_time_per_file,
            "findings_by_category": self.stats.findings_by_category,
            "total_duration": (self.stats.end_time - self.stats.start_time) if self.stats.start_time else 0
        }
    
    def get_slowest_files(self, top_n: int = 5) -> List[float]:
        """Получение самых медленных файлов"""
        sorted_times = sorted(self.file_times, reverse=True)
        return sorted_times[:top_n]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Получение статистики производительности"""
        if not self.file_times:
            return {}
        
        return {
            "min_time": min(self.file_times),
            "max_time": max(self.file_times),
            "avg_time": sum(self.file_times) / len(self.file_times),
            "total_time": sum(self.file_times),
            "files_count": len(self.file_times)
        }
    
    def reset(self) -> None:
        """Сброс метрик"""
        self.stats = ProcessingStats()
        self.file_times = []
        self.start_time = None