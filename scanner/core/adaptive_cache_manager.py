#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Adaptive Cache Manager v2.0
Улучшенное адаптивное управление памятью с прогнозированием и самообучением
"""

import time
import gc
import threading
import psutil
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime


@dataclass
class CleanupRecord:
    timestamp: float
    before_rss_mb: float
    after_rss_mb: float
    freed_mb: float
    reason: str
    duration_sec: float
    was_effective: bool = False


@dataclass
class ReloadRecord:
    timestamp: float
    before_rss_mb: float
    after_rss_mb: float
    freed_mb: float
    reason: str
    duration_sec: float
    was_effective: bool = False


class AdaptiveCacheManager:
    """
    Улучшенный адаптивный менеджер кэшей с прогнозированием и самообучением.
    
    Новые возможности:
    - Отслеживание реального потребления памяти
    - Прогнозирование на основе скользящего среднего
    - Адаптивные пороги с учётом системной нагрузки
    - Приоритезация перезагрузки моделей перед очисткой кэшей
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Лимиты памяти
        self.max_rss_mb = config.get("memory_limit_rss_mb", 8192)
        self.max_vms_mb = config.get("memory_limit_vms_mb", 16000)
        self.emergency_threshold = config.get("emergency_restart_threshold", 85)
        
        # Базовые интервалы
        self.base_cleanup_interval = config.get("cache_cleanup_interval", 2000)
        self.base_reload_interval = config.get("models_reload_after_files", 3000)
        self.min_cleanup_interval = config.get("adaptive_min_cleanup_interval", 500)
        self.max_cleanup_interval = config.get("adaptive_max_cleanup_interval", 5000)
        self.min_reload_interval = max(1000, self.base_reload_interval // 2)
        self.max_reload_interval = self.base_reload_interval * 2
        
        # Адаптивные пороги
        self.rss_cleanup_threshold = config.get("cache_memory_threshold_rss", 7500)
        self.rss_reload_threshold = config.get("models_memory_threshold_rss", 6800)
        
        # Динамические интервалы
        self.current_cleanup_interval = self.base_cleanup_interval
        self.current_reload_interval = self.base_reload_interval
        
        # История для анализа
        self.memory_history: deque = deque(maxlen=100)
        self.cleanup_history: List[CleanupRecord] = []
        self.reload_history: List[ReloadRecord] = []
        
        # Статистика эффективности
        self.total_cleanups = 0
        self.effective_cleanups = 0
        self.total_reloads = 0
        self.effective_reloads = 0
        self.consecutive_ineffective_cleanups = 0
        self.consecutive_ineffective_reloads = 0
        
        # Прогнозирование
        self.predicted_peak_mb = 0
        self.memory_growth_rate_mb_per_file = 0.0
        self.sliding_window = deque(maxlen=20)  # Для скользящего среднего
        
        # Состояние
        self.emergency_mode = False
        self.last_check_time = time.time()
        
        # Системная информация
        self.system_memory = psutil.virtual_memory()
        
        self._lock = threading.Lock()
        
        print(f"[ADAPTIVE_CACHE] Инициализация v2.0:")
        print(f"   Максимальный RSS: {self.max_rss_mb} MB")
        print(f"   Базовый интервал очистки: {self.base_cleanup_interval} файлов")
        print(f"   Базовый интервал перезагрузки: {self.base_reload_interval} файлов")
        print(f"   Порог очистки RSS: {self.rss_cleanup_threshold} MB")
        print(f"   Порог перезагрузки RSS: {self.rss_reload_threshold} MB")
        print(f"   Аварийный порог Commit: {self.emergency_threshold}%")
    
    def record_memory(self, rss_mb: float, vms_mb: float, files_processed: int, commit_percent: float):
        """Запись замера памяти для анализа трендов"""
        with self._lock:
            self.memory_history.append({
                "timestamp": time.time(),
                "rss_mb": rss_mb,
                "vms_mb": vms_mb,
                "files_processed": files_processed,
                "commit_percent": commit_percent
            })
            self.sliding_window.append(rss_mb)
            self._update_trends()
            self._predict_peak()
    
    def _update_trends(self):
        """Обновление трендов роста памяти"""
        if len(self.memory_history) < 20:
            return
        
        recent = list(self.memory_history)[-20:]
        first = recent[0]
        last = recent[-1]
        
        files_delta = last["files_processed"] - first["files_processed"]
        rss_delta = last["rss_mb"] - first["rss_mb"]
        
        if files_delta > 500 and rss_delta > 0:
            self.memory_growth_rate_mb_per_file = rss_delta / files_delta
        elif rss_delta <= 0:
            self.memory_growth_rate_mb_per_file = 0
    
    def _predict_peak(self) -> float:
        """Прогнозирование пика памяти"""
        if len(self.sliding_window) < 10 or self.memory_growth_rate_mb_per_file <= 0:
            return 0
        
        if not self.memory_history:
            return 0
        
        last = self.memory_history[-1]
        current_rss = last["rss_mb"]
        
        if current_rss < 2000:
            return 0
        
        rss_left = self.max_rss_mb - current_rss
        if rss_left > 0:
            files_to_limit = rss_left / self.memory_growth_rate_mb_per_file
            self.predicted_peak_mb = self.max_rss_mb
            return files_to_limit
        
        return 0
    
    def should_cleanup(self, current_rss_mb: float, current_vms_mb: float,
                       files_since_last_cleanup: int, commit_percent: float) -> Tuple[bool, str]:
        """Адаптивное решение о необходимости очистки кэшей"""
        with self._lock:
            # 1. Аварийный сценарий
            if commit_percent > self.emergency_threshold:
                self.emergency_mode = True
                return True, f"АВАРИЙНЫЙ: Commit Charge {commit_percent:.1f}% > {self.emergency_threshold}%"
            
            # 2. RSS превысил порог (основной критерий)
            if current_rss_mb > self.rss_cleanup_threshold:
                return True, f"RSS {current_rss_mb:.0f} MB > порога {self.rss_cleanup_threshold} MB"
            
            # 3. Прогноз достижения лимита (только при высоком RSS)
            if current_rss_mb > 5000:
                files_to_limit = self._predict_peak()
                if 0 < files_to_limit < 500:
                    return True, f"прогноз: достижение лимита через {files_to_limit:.0f} файлов"
            
            # 4. Интервальная очистка (только если RSS уже значительный)
            if current_rss_mb > 4000 and files_since_last_cleanup >= self.current_cleanup_interval:
                return True, f"интервал {files_since_last_cleanup} >= {self.current_cleanup_interval} файлов"
            
            return False, ""
    
    def record_cleanup(self, before_rss_mb: float, after_rss_mb: float, 
                       freed_mb: float, reason: str, duration_sec: float):
        """Запись результата очистки с улучшенной оценкой эффективности"""
        with self._lock:
            # Очистка эффективна, если освобождено > 20 MB ИЛИ freed > 1% от before
            was_effective = freed_mb > 20 or (before_rss_mb > 0 and freed_mb / before_rss_mb > 0.01)
            
            record = CleanupRecord(
                timestamp=time.time(),
                before_rss_mb=before_rss_mb,
                after_rss_mb=after_rss_mb,
                freed_mb=freed_mb,
                reason=reason,
                duration_sec=duration_sec,
                was_effective=was_effective
            )
            self.cleanup_history.append(record)
            
            self.total_cleanups += 1
            if was_effective:
                self.effective_cleanups += 1
                self.consecutive_ineffective_cleanups = 0
                
                # Увеличиваем интервал, но не слишком агрессивно
                if self.current_cleanup_interval < self.max_cleanup_interval:
                    self.current_cleanup_interval = min(
                        self.max_cleanup_interval,
                        int(self.current_cleanup_interval * 1.2)
                    )
                    print(f"[ADAPTIVE_CACHE] Очистка эффективна (+{freed_mb:.0f} MB), интервал увеличен до {self.current_cleanup_interval}")
            else:
                self.consecutive_ineffective_cleanups += 1
                
                # После 5 неэффективных очисток подряд - увеличиваем порог
                if self.consecutive_ineffective_cleanups >= 5:
                    old_threshold = self.rss_cleanup_threshold
                    self.rss_cleanup_threshold = min(
                        self.max_rss_mb - 500,  # Оставляем 500 MB запаса
                        self.rss_cleanup_threshold + 500
                    )
                    print(f"[ADAPTIVE_CACHE] 5 неэффективных очисток, порог повышен: {old_threshold:.0f} -> {self.rss_cleanup_threshold:.0f} MB")
                    self.consecutive_ineffective_cleanups = 0
                
                # Уменьшаем интервал, но не ниже минимума
                self.current_cleanup_interval = max(
                    self.min_cleanup_interval,
                    int(self.current_cleanup_interval * 0.9)
                )
                if self.total_cleanups % 5 == 0:
                    print(f"[ADAPTIVE_CACHE] Очистка неэффективна, интервал уменьшен до {self.current_cleanup_interval}")
            
            if len(self.cleanup_history) > 50:
                self.cleanup_history = self.cleanup_history[-50:]
    
    def should_reload_models(self, current_rss_mb: float, current_vms_mb: float,
                            files_since_last_reload: int, commit_percent: float) -> Tuple[bool, str]:
        """Улучшенное решение о необходимости перезагрузки моделей"""
        with self._lock:
            # 1. Аварийный сценарий
            if commit_percent > self.emergency_threshold:
                self.emergency_mode = True
                return True, f"АВАРИЙНЫЙ: Commit Charge {commit_percent:.1f}% > {self.emergency_threshold}%"
            
            # 2. RSS превысил порог (основной критерий)
            if current_rss_mb > self.rss_reload_threshold:
                return True, f"RSS {current_rss_mb:.0f} MB > порога {self.rss_reload_threshold:.0f} MB"
            
            # 3. Прогноз достижения лимита
            if current_rss_mb > 5000:
                files_to_limit = self._predict_peak()
                if 0 < files_to_limit < 1000:
                    return True, f"прогноз: достижение лимита через {files_to_limit:.0f} файлов"
            
            # 4. Интервальная перезагрузка
            if files_since_last_reload >= self.current_reload_interval:
                return True, f"интервал {files_since_last_reload} >= {self.current_reload_interval} файлов"
            
            return False, ""
    
    def record_reload(self, before_rss_mb: float, after_rss_mb: float,
                      freed_mb: float, reason: str, duration_sec: float):
        """Запись результата перезагрузки с улучшенной оценкой"""
        with self._lock:
            was_effective = freed_mb > 100
            
            record = ReloadRecord(
                timestamp=time.time(),
                before_rss_mb=before_rss_mb,
                after_rss_mb=after_rss_mb,
                freed_mb=freed_mb,
                reason=reason,
                duration_sec=duration_sec,
                was_effective=was_effective
            )
            self.reload_history.append(record)
            
            self.total_reloads += 1
            if was_effective:
                self.effective_reloads += 1
                self.consecutive_ineffective_reloads = 0
                
                if self.current_reload_interval < self.max_reload_interval:
                    self.current_reload_interval = min(
                        self.max_reload_interval,
                        int(self.current_reload_interval * 1.2)
                    )
                    print(f"[ADAPTIVE_CACHE] Перезагрузка эффективна (+{freed_mb:.0f} MB), интервал увеличен до {self.current_reload_interval}")
            else:
                self.consecutive_ineffective_reloads += 1
                
                if self.consecutive_ineffective_reloads >= 2:
                    old_threshold = self.rss_reload_threshold
                    self.rss_reload_threshold = min(
                        self.max_rss_mb - 300,
                        self.rss_reload_threshold + 500
                    )
                    print(f"[ADAPTIVE_CACHE] Неэффективные перезагрузки, порог повышен: {old_threshold:.0f} -> {self.rss_reload_threshold:.0f} MB")
                    self.consecutive_ineffective_reloads = 0
                
                self.current_reload_interval = max(
                    self.min_reload_interval,
                    int(self.current_reload_interval * 0.8)
                )
            
            if len(self.reload_history) > 30:
                self.reload_history = self.reload_history[-30:]
    
    def should_emergency_restart(self, current_rss_mb: float, commit_percent: float) -> Tuple[bool, str]:
        """Проверка необходимости аварийного перезапуска процесса"""
        if commit_percent > 95:
            return True, f"Commit Charge {commit_percent:.1f}% > 95% - риск OOM!"
        
        if current_rss_mb > self.max_rss_mb * 0.95:
            return True, f"RSS {current_rss_mb:.0f} MB > 95% лимита ({self.max_rss_mb} MB)"
        
        return False, ""
    
    def get_efficiency_stats(self) -> Dict[str, Any]:
        """Получение статистики эффективности"""
        cleanup_effectiveness = (self.effective_cleanups / self.total_cleanups * 100) if self.total_cleanups > 0 else 0
        reload_effectiveness = (self.effective_reloads / self.total_reloads * 100) if self.total_reloads > 0 else 0
        
        return {
            "total_cleanups": self.total_cleanups,
            "effective_cleanups": self.effective_cleanups,
            "cleanup_effectiveness_percent": cleanup_effectiveness,
            "current_cleanup_interval": self.current_cleanup_interval,
            "total_reloads": self.total_reloads,
            "effective_reloads": self.effective_reloads,
            "reload_effectiveness_percent": reload_effectiveness,
            "current_reload_interval": self.current_reload_interval,
            "rss_cleanup_threshold": self.rss_cleanup_threshold,
            "rss_reload_threshold": self.rss_reload_threshold,
            "memory_growth_rate_mb_per_file": self.memory_growth_rate_mb_per_file,
            "predicted_peak_mb": self.predicted_peak_mb,
            "emergency_mode": self.emergency_mode
        }
    
    def reset_emergency_mode(self):
        self.emergency_mode = False

    def get_optimal_save_interval(self) -> int:
        """Определение оптимального интервала сохранения состояния"""
        if self.memory_growth_rate_mb_per_file > 5:
            return 200
        elif self.memory_growth_rate_mb_per_file > 2:
            return 500
        else:
            return 1000

__all__ = ['AdaptiveCacheManager']