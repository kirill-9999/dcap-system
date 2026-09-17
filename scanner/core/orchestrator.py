#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Оркестратор с адаптивным управлением памятью
"""

import time
import gc
import psutil
import sys
import ctypes
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict
from datetime import datetime

from core.base import ISourceConnector, IClassifier, IOutputHandler, FileContext, ProcessingContext, SourceType
from core.state_manager import StateManager
from core.metrics import MetricsCollector
from core.logger import AgentLogger
from core.memory_manager import MemoryManager
from core.catalog_manager import CatalogManager
from core.adaptive_cache_manager import AdaptiveCacheManager
from utils.performance_monitor import PerformanceMonitor
from utils.file_hasher import FileHasher

# Настройка логгера
logger = logging.getLogger(__name__)


class ProgressDisplay:
    def __init__(self, total_new: int, already_processed: int = 0, total_all: int = None):
        self.total_new = total_new
        self.already_processed = already_processed
        self.total_all = total_all if total_all else already_processed + total_new
        
        self.processed_in_this_run = 0
        self.processed_total = already_processed
        self.files_with_findings = 0
        
        self.start_time = time.time()
        self.last_log_time = 0
        self.start_mem = psutil.Process().memory_info().rss / 1024 / 1024
        self.first_update_done = False
        self.peak_memory = self.start_mem
        
        if total_new < 10:
            self.log_interval = 1
        elif total_new < 100:
            self.log_interval = 10
        else:
            self.log_interval = 100
        
        self.next_log_at = self.log_interval
    
    def first_message(self, files_with_findings: int = 0, memory_mb: float = None):
        self.first_update_done = True
        if memory_mb is None:
            memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
        
        print()
        print("=" * 70)
        print(f"[X] НАЧАЛО ОБРАБОТКИ ФАЙЛОВ")
        print("=" * 70)
        print(f"   Всего файлов в источнике: {self.total_all:,}")
        print(f"   Уже обработано ранее: {self.already_processed:,}")
        print(f"   Осталось обработать: {self.total_new:,}")
        print(f"   Начальная память: {memory_mb:.0f} MB")
        print(f"   Файлов с находками: {files_with_findings:,}")
        print(f"   Интервал вывода: каждые {self.log_interval} файлов")
        print("=" * 70)
        print()
    
    def update(self, processed_in_this_run: int, processed_total: int, 
               files_with_findings: int = 0, memory_mb: float = None, 
               vms_mb: float = None, commit_percent: float = None, force: bool = False):
        self.processed_in_this_run = processed_in_this_run
        self.processed_total = processed_total
        self.files_with_findings = files_with_findings
        now = time.time()
        
        if memory_mb:
            if memory_mb > self.peak_memory:
                self.peak_memory = memory_mb
        
        if not self.first_update_done and processed_in_this_run > 0:
            self.first_message(files_with_findings, memory_mb)
        
        should_log = force or processed_in_this_run >= self.next_log_at or processed_in_this_run >= self.total_new
        
        if not should_log:
            return
        
        self.next_log_at = ((processed_in_this_run // self.log_interval) + 1) * self.log_interval
        self.last_log_time = now
        
        percent_total = processed_total / self.total_all * 100 if self.total_all > 0 else 0
        percent_new = processed_in_this_run / self.total_new * 100 if self.total_new > 0 else 0
        
        elapsed = now - self.start_time
        speed = processed_in_this_run / elapsed if elapsed > 0 else 0
        
        if speed > 0:
            eta = (self.total_new - processed_in_this_run) / speed
            eta_hours = int(eta // 3600)
            eta_minutes = int((eta % 3600) // 60)
            if eta_hours > 0:
                eta_str = f"{eta_hours}ч {eta_minutes}м"
            elif eta_minutes > 0:
                eta_str = f"{eta_minutes}м"
            else:
                eta_str = f"{int(eta)}с"
        else:
            eta_str = "---"
        
        if memory_mb is None:
            memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
        mem_delta = memory_mb - self.start_mem
        
        total_python_mem = 0
        try:
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if proc.info['name'].lower() in ['python.exe', 'python']:
                        total_python_mem += proc.info['memory_info'].rss / 1024 / 1024
                except:
                    pass
        except:
            pass
        
        mem_info = f"RAM: {memory_mb:.0f} MB ({mem_delta:+.0f})"
        if vms_mb:
            mem_info += f" | VMS: {vms_mb:.0f} MB"
        if commit_percent:
            mem_info += f" | Commit: {commit_percent:.0f}%"
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
              f"Запуск: {processed_in_this_run:,}/{self.total_new:,} ({percent_new:.1f}%) | "
              f"Всего: {processed_total:,}/{self.total_all:,} ({percent_total:.1f}%) | "
              f"{speed:.2f} ф/с | ETA: {eta_str} | "
              f"{mem_info} | "
              f"Всего Python: {total_python_mem:.0f} MB | "
              f"Пик: {self.peak_memory:.0f} MB | "
              f"Файлов с находками: {files_with_findings:,}")
    
    def finish(self):
        elapsed = time.time() - self.start_time
        elapsed_min = int(elapsed // 60)
        elapsed_sec = int(elapsed % 60)
        final_mem = psutil.Process().memory_info().rss / 1024 / 1024
        mem_delta = final_mem - self.start_mem
        
        total_python_mem = 0
        try:
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if proc.info['name'].lower() in ['python.exe', 'python']:
                        total_python_mem += proc.info['memory_info'].rss / 1024 / 1024
                except:
                    pass
        except:
            pass
        
        print()
        print("=" * 70)
        print("[OK] СКАНИРОВАНИЕ ЗАВЕРШЕНО")
        print("=" * 70)
        print(f"   Обработано в этом запуске: {self.processed_in_this_run:,}")
        print(f"   Всего обработано: {self.processed_total:,} из {self.total_all:,}")
        print(f"   Файлов с находками: {self.files_with_findings:,}")
        print(f"   Время работы: {elapsed_min}м {elapsed_sec}с")
        print(f"   Средняя скорость: {self.processed_in_this_run / elapsed:.2f} файлов/сек")
        print(f"   Память процесса: {self.start_mem:.0f} MB -> {final_mem:.0f} MB ({mem_delta:+.0f} MB)")
        print(f"   Общая память Python: {total_python_mem:.0f} MB")
        print(f"   Пиковая память: {self.peak_memory:.0f} MB")
        print("=" * 70)


class Orchestrator:
    def __init__(self, config: Dict[str, Any], 
                 shared_classifiers: List[IClassifier] = None,
                 shared_handlers: List[IOutputHandler] = None):
        self.config = config
        self.connector: Optional[ISourceConnector] = None
        self.classifiers: List[IClassifier] = shared_classifiers if shared_classifiers else []
        self.handlers: List[IOutputHandler] = shared_handlers if shared_handlers else []
        self.connector_name: str = "unknown"
        
        state_file = config.get("state_file", "state.json")
        logs_folder = config.get("logs_folder", "logs")
        
        self.state_manager = StateManager(state_file)
        self.metrics = MetricsCollector()
        self.logger = AgentLogger(logs_folder)
        
        perf_config = config.get("performance", {})
        self.memory_manager = MemoryManager(perf_config)
        
        catalog_dir = config.get("catalog_dir", "catalog")
        self.catalog_manager = CatalogManager(catalog_dir)
        
        self.processed_count = self.state_manager.get_processed_count()
        self.files_with_findings = 0
        self.total_findings = 0
        self.stop_requested = False
        self.ocr_stats = {"count": 0, "errors": 0, "time": 0.0}
        
        # Список неудачных файлов
        self.failed_files = []
        self.max_failed_log = config.get("max_failed_log", 1000)
        
        self.models_reload_base_interval = perf_config.get("models_reload_after_files", 5000)
        self.models_reload_after_files = self.models_reload_base_interval
        self.models_memory_threshold_rss = perf_config.get("models_memory_threshold_rss", 6000)
        self.models_memory_threshold_vms = perf_config.get("models_memory_threshold_vms", 12000)
        
        self.cache_cleanup_interval = perf_config.get("cache_cleanup_interval", 500)
        self.cache_memory_threshold_rss = perf_config.get("cache_memory_threshold_rss", 4000)
        self.cache_memory_threshold_vms = perf_config.get("cache_memory_threshold_vms", 8000)
        
        self.save_interval = perf_config.get("save_interval", 500)
        self.catalog_save_interval = perf_config.get("catalog_save_interval", 500)
        self.emergency_restart_threshold = perf_config.get("emergency_restart_threshold", 85)
        
        self.last_save = 0
        self.last_catalog_save = 0
        self.last_cache_cleanup = self.processed_count
        self.last_models_reload = self.processed_count
        self.models_reload_count = 0
        self.models_reload_failures = 0
        
        self.hasher = FileHasher()
        
        monitoring_enabled = config.get("monitoring_enabled", True)
        monitor_interval = config.get("monitor_interval", 5.0)
        self.monitor = PerformanceMonitor(
            log_dir=Path(logs_folder),
            interval=monitor_interval,
            enabled=monitoring_enabled
        )
        
        self.memory_samples = []
        self.file_memory_stats = defaultdict(lambda: {"before": 0, "after": 0, "delta": 0})
        
        actual_processed = self.state_manager.get_processed_count()
        if self.processed_count != actual_processed:
            print(f"[SYNC] Рассинхронизация: агент={self.processed_count}, state={actual_processed}")
            self.processed_count = actual_processed
        
        # Адаптивный менеджер кэшей
        self.adaptive_manager = AdaptiveCacheManager(perf_config)
        
        print(f"[ORCHESTRATOR] Восстановлено состояние: обработано {self.processed_count} файлов")
        print(f"[ORCHESTRATOR] Параметры памяти:")
        print(f"   Очистка кэшей: интервал {self.cache_cleanup_interval} файлов, RSS > {self.cache_memory_threshold_rss} MB, VMS > {self.cache_memory_threshold_vms} MB")
        print(f"   Перезагрузка моделей: интервал {self.models_reload_after_files} файлов, RSS > {self.models_memory_threshold_rss} MB, VMS > {self.models_memory_threshold_vms} MB")
        print(f"   Сохранение состояния: каждые {self.save_interval} новых файлов")
        print(f"   Аварийный порог Commit Charge: {self.emergency_restart_threshold}%")
    
    def reset_for_new_source(self):
        """Сброс состояния для нового источника"""
        import gc
        
        actual_processed = self.state_manager.get_processed_count()
        if self.processed_count != actual_processed:
            print(f"[SYNC] Синхронизация: агент={self.processed_count}, state={actual_processed}")
            self.processed_count = actual_processed
        
        self.files_with_findings = 0
        self.total_findings = 0
        self.failed_files = []
        
        self.last_save = self.processed_count
        self.last_catalog_save = self.processed_count
        self.last_cache_cleanup = self.processed_count
        self.last_models_reload = self.processed_count
        
        for classifier in self.classifiers:
            if hasattr(classifier, 'cache') and classifier.cache:
                cache_size = len(classifier.cache)
                if cache_size > 0:
                    classifier.cache.clear()
                    print(f"[RESET] Очищен кэш {classifier.classifier_name}: {cache_size} -> 0")
            
            if hasattr(classifier, 'extractor') and classifier.extractor:
                if hasattr(classifier.extractor, '_ocr_engine') and classifier.extractor._ocr_engine:
                    if hasattr(classifier.extractor._ocr_engine, '_cache'):
                        cache_size = len(classifier.extractor._ocr_engine._cache)
                        if cache_size > 0:
                            classifier.extractor._ocr_engine._cache.clear()
                            print(f"[RESET] Очищен кэш OCR: {cache_size} -> 0")
        
        gc.collect()
        
        print(f"[RESET] Оркестратор сброшен для нового источника. Всего обработано: {self.processed_count} файлов")
    
    def _log_failed_file(self, file_path: str, error: str, error_type: str = "unknown"):
        self.failed_files.append({
            "path": file_path,
            "error": str(error)[:500],
            "error_type": error_type,
            "timestamp": datetime.now().isoformat()
        })
        if len(self.failed_files) > self.max_failed_log:
            self.failed_files = self.failed_files[-self.max_failed_log:]
    
    def _print_failed_files_report(self):
        if not self.failed_files:
            return
        
        print("\n" + "=" * 70)
        print("[WARN] ФАЙЛЫ, НЕ ОБРАБОТАННЫЕ ИЗ-ЗА ОШИБОК")
        print("=" * 70)
        print(f"   Всего неудачных файлов: {len(self.failed_files)}")
        print("=" * 70)
        
        error_types = {}
        for f in self.failed_files:
            error_type = f.get("error_type", "unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        print("\n[X] Статистика по типам ошибок:")
        for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
            print(f"   - {error_type}: {count}")
        
        print("\n[X] Детали (первые 10 ошибок):")
        for i, f in enumerate(self.failed_files[:10], 1):
            path = f.get("path", "unknown")
            error = f.get("error", "unknown")[:200]
            error_type = f.get("error_type", "unknown")
            timestamp = f.get("timestamp", "unknown")
            
            print(f"\n   {i}. {path}")
            print(f"      Тип: {error_type}")
            print(f"      Время: {timestamp}")
            print(f"      Ошибка: {error}")
        
        if len(self.failed_files) > 10:
            print(f"\n   ... и ещё {len(self.failed_files) - 10} ошибок")
        
        print("\n" + "=" * 70)
    
    def _save_failed_files_report(self):
        if not self.failed_files:
            return
        
        logs_folder = self.config.get("logs_folder", "logs")
        logs_dir = Path(logs_folder)
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        today = datetime.now().strftime("%Y%m%d_%H%M%S")
        failed_file = logs_dir / f"failed_files_{today}.jsonl"
        
        try:
            with open(failed_file, 'w', encoding='utf-8') as f:
                for record in self.failed_files:
                    f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
            print(f"\n[X] Детали ошибок сохранены в: {failed_file}")
        except Exception as e:
            print(f"\n[WARN] Не удалось сохранить отчёт об ошибках: {e}")
    
    def configure(self, connector: ISourceConnector, configure_connector: bool = False) -> None:
        self.connector = connector
        self.connector_name = connector.connector_type.value
        if configure_connector:
            connector_config = self.config.get("connectors", {}).get(connector.connector_type.value, {})
            connector.configure(connector_config)
        self.metrics.start_processing()
        print(f"[ORCHESTRATOR] Настроен для {self.connector_name} (классификаторов: {len(self.classifiers)})")
    
    def _stop_all_workers(self):
        for classifier in self.classifiers:
            if hasattr(classifier, '_stop_worker'):
                classifier._stop_worker()
            if hasattr(classifier, 'shutdown'):
                classifier.shutdown()
    
    def _save_state(self, force: bool = False):
        files_since_save = self.processed_count - self.last_save
        
        if force or files_since_save >= self.save_interval:
            self.state_manager.save()
            self.last_save = self.processed_count
            if force and self.processed_count > 0:
                print(f"[STATE] Состояние сохранено ({self.processed_count} файлов)")
        
        files_since_catalog_save = self.processed_count - self.last_catalog_save
        if force or files_since_catalog_save >= self.catalog_save_interval:
            self.catalog_manager.save()
            self.last_catalog_save = self.processed_count
    
    def _adaptive_cleanup_caches(self, reason: str):
        """Адаптивная очистка кэшей с записью эффективности"""
        mem = self.memory_manager.get_memory_usage()
        before_rss = mem.get("process_rss_mb", 0)
        before_vms = mem.get("process_vms_mb", 0)
        
        # Если память не превышает порог значительно - пропускаем очистку
        if before_rss < self.cache_memory_threshold_rss + 200:
            print(f"\n[CACHE] Пропуск очистки: RSS={before_rss:.0f} MB (порог {self.cache_memory_threshold_rss} MB)")
            self.last_cache_cleanup = self.processed_count
            return
        
        print(f"\n[CACHE] [X] ОЧИСТКА КЭШЕЙ ОСНОВНОГО ПРОЦЕССА")
        print(f"[CACHE] Память до: RSS={before_rss:.0f} MB, VMS={before_vms:.0f} MB")
        
        # Очистка кэшей классификаторов
        for classifier in self.classifiers:
            if hasattr(classifier, 'cache'):
                cache_size = len(classifier.cache)
                if cache_size > 0:
                    classifier.cache.clear()
                    print(f"[CACHE] Очищен кэш {classifier.classifier_name}: {cache_size} -> 0")
            
            if hasattr(classifier, 'extractor') and classifier.extractor:
                if hasattr(classifier.extractor, '_ocr_engine') and classifier.extractor._ocr_engine:
                    if hasattr(classifier.extractor._ocr_engine, '_cache'):
                        cache_size = len(classifier.extractor._ocr_engine._cache)
                        if cache_size > 0:
                            classifier.extractor._ocr_engine._cache.clear()
                            print(f"[CACHE] Очищен кэш OCR: {cache_size} -> 0")
        
        # Принудительный GC
        start_time = time.time()
        self.memory_manager.check_and_collect(force=True)
        
        after_mem = self.memory_manager.get_memory_usage()
        after_rss = after_mem.get("process_rss_mb", 0)
        after_vms = after_mem.get("process_vms_mb", 0)
        freed_rss = before_rss - after_rss
        freed_vms = before_vms - after_vms
        duration = time.time() - start_time
        
        print(f"[CACHE] Очистка завершена: RSS {before_rss:.0f} -> {after_rss:.0f} MB ( freed {freed_rss:.0f} MB)")
        print(f"[CACHE] VMS {before_vms:.0f} -> {after_vms:.0f} MB ( freed {freed_vms:.0f} MB)")
        print(f"[CACHE] Длительность: {duration:.2f}с")
        print(f"[CACHE] {'='*50}\n")
        
        # Обновляем счетчик ТОЛЬКО если память действительно освободилась
        if freed_rss > 50 or freed_vms > 100:
            self.last_cache_cleanup = self.processed_count
        else:
            # Если очистка не помогла, увеличиваем счетчик, чтобы не проверять слишком часто
            self.last_cache_cleanup = self.processed_count
            print(f"[CACHE] [WARN] Очистка не освободила память, следующий раз проверим через 50 файлов")
    
    def _adaptive_reload_models(self, reason: str):
        """Адаптивная перезагрузка моделей с записью эффективности"""
        mem = self.memory_manager.get_memory_usage()
        before_rss = mem.get("process_rss_mb", 0)
        before_vms = mem.get("process_vms_mb", 0)
        before_commit = mem.get("system_commit_percent", 0)
        
        start_time = time.time()
        self.models_reload_count += 1
        
        print(f"\n{'='*70}")
        print(f"[RELOAD_MODELS] [X] АДАПТИВНАЯ ПЕРЕЗАГРУЗКА МОДЕЛЕЙ (#{self.models_reload_count})")
        print(f"[RELOAD_MODELS] Причина: {reason}")
        print(f"[RELOAD_MODELS] Память до: RSS={before_rss:.0f} MB, VMS={before_vms:.0f} MB")
        print(f"[RELOAD_MODELS] System Commit: {before_commit:.1f}%")
        print(f"{'='*70}\n")
        
        self._save_state(force=True)
        
        for classifier in self.classifiers:
            if hasattr(classifier, 'reload_models'):
                try:
                    classifier.reload_models()
                    print(f"[RELOAD_MODELS] [OK] {classifier.classifier_name} перезагружен")
                except Exception as e:
                    print(f"[RELOAD_MODELS] [ERROR] Ошибка перезагрузки {classifier.classifier_name}: {e}")
        
        for _ in range(5):
            gc.collect()
        
        if sys.platform == 'win32':
            try:
                kernel32 = ctypes.windll.kernel32
                process = kernel32.GetCurrentProcess()
                kernel32.SetProcessWorkingSetSize(process, -1, -1)
            except:
                pass
        
        after_mem = self.memory_manager.get_memory_usage()
        after_rss = after_mem.get("process_rss_mb", 0)
        after_vms = after_mem.get("process_vms_mb", 0)
        after_commit = after_mem.get("system_commit_percent", 0)
        freed_rss = before_rss - after_rss
        freed_vms = before_vms - after_vms
        duration = time.time() - start_time
        
        print(f"\n[RELOAD_MODELS] Память после: RSS={after_rss:.0f} MB, VMS={after_vms:.0f} MB")
        print(f"[RELOAD_MODELS] System Commit: {after_commit:.1f}%")
        print(f"[RELOAD_MODELS] Освобождено: RSS={freed_rss:.0f} MB, VMS={freed_vms:.0f} MB")
        print(f"[RELOAD_MODELS] Длительность: {duration:.2f}с")
        print(f"{'='*70}\n")
        
        self.adaptive_manager.record_reload(before_rss, after_rss, freed_rss, reason, duration)
        self.last_models_reload = self.processed_count
    
    def _emergency_restart(self):
        """Аварийный перезапуск процесса при риске OOM"""
        print("\n" + "!" * 70)
        print("[WARN] АВАРИЙНЫЙ ПЕРЕЗАПУСК ПРОЦЕССА")
        print("!" * 70)
        
        self._save_state(force=True)
        self.catalog_manager.save(force=True)
        self.state_manager.save()
        self._stop_all_workers()
        
        print("\n[X] Состояние сохранено. Выход для перезапуска...")
        sys.exit(99)
    
    def _check_and_cleanup(self):
        """Проверка необходимости очистки кэша и перезагрузки моделей"""
        current_files = self.processed_count
        
        # Проверка очистки кэша
        if current_files - self.last_cache_cleanup >= self.cache_cleanup_interval:
            logger.info(f"[CACHE] Требуется очистка: интервал {self.cache_cleanup_interval} >= {current_files - self.last_cache_cleanup} файлов")
            self._cleanup_cache()
            self.last_cache_cleanup = current_files
        
        # Проверка перезагрузки моделей
        if current_files - self.last_models_reload >= self.models_reload_after_files:
            logger.info(f"[RELOAD] Требуется перезагрузка моделей: интервал {self.models_reload_after_files} >= {current_files - self.last_models_reload} файлов")
            self._reload_models()
            self.last_models_reload = current_files

    def _cleanup_cache(self):
        """Очистка кэша классификаторов"""
        try:
            logger.info("[CACHE] Очистка кэша...")
            
            for classifier in self.classifiers:
                if hasattr(classifier, 'cleanup_cache'):
                    classifier.cleanup_cache()
                elif hasattr(classifier, 'clear_cache'):
                    classifier.clear_cache()
            
            import gc
            gc.collect()
            
            logger.info("[CACHE] Очистка кэша завершена")
            
        except Exception as e:
            logger.error(f"[CACHE] Ошибка очистки кэша: {e}")

    def _reload_models(self):
        """Перезагрузка моделей классификаторов"""
        try:
            logger.info("[RELOAD] Перезагрузка моделей классификаторов...")
            
            for classifier in self.classifiers:
                if hasattr(classifier, 'reload_models'):
                    classifier.reload_models()
                elif hasattr(classifier, 'reload'):
                    classifier.reload()
                elif hasattr(classifier, 'load_models'):
                    classifier.load_models()
            
            import gc
            gc.collect()
            
            logger.info("[RELOAD] Модели перезагружены")
            
        except Exception as e:
            logger.error(f"[RELOAD] Ошибка перезагрузки моделей: {e}")
    
    def _collect_findings_types(self, context: ProcessingContext) -> Dict[str, List[str]]:
        findings_types = {}
        for classifier_name, result in context.classifier_results.items():
            if result.findings:
                types = list(set(f.subcategory for f in result.findings))
                findings_types[classifier_name] = types
        return findings_types
    
    def process_source(self, source_path: str) -> None:
        if not self.connector:
            raise ValueError("Коннектор не настроен")
        
        source_display = source_path
        if hasattr(self.connector, 'connector_type') and self.connector.connector_type in [SourceType.S3, SourceType.MINIO]:
            source_display = f"s3://{source_path}"
        
        self.logger.info(f"Обработка: {source_display}")
        
        all_files = list(self.connector.list_files(source_path))
        if not all_files:
            self.logger.info("Нет файлов для обработки")
            return
        
        files_to_process = []
        for fc in all_files:
            normalized_path = str(Path(fc.path).resolve())
            fc.id = normalized_path
            
            if not self.state_manager.is_processed_and_unchanged(fc.id, None):
                files_to_process.append(fc)
        
        total_new_files = len(files_to_process)
        total_all_files = len(all_files)
        
        actual_processed = self.state_manager.get_processed_count()
        if self.processed_count != actual_processed:
            print(f"[SYNC] Рассинхронизация: агент={self.processed_count}, state={actual_processed}")
            self.processed_count = actual_processed
        
        self.logger.info(f"Найдено файлов: {total_all_files:,}, из них новых: {total_new_files:,}")
        
        if total_new_files == 0:
            self.logger.info("Нет новых файлов для обработки")
            return
        
        self.monitor.start_session()
        
        progress = ProgressDisplay(
            total_new=total_new_files,
            already_processed=self.processed_count,
            total_all=total_all_files
        )
        
        processed_in_this_run = 0
        files_with_findings = self.files_with_findings
        
        start_mem = self.memory_manager.get_memory_usage()
        
        print()
        print("=" * 70)
        print(f"[X] НАЧАЛО СКАНИРОВАНИЯ: {source_display}")
        print(f"[X] Всего файлов в источнике: {total_all_files:,}")
        print(f"[X] Новых файлов для обработки: {total_new_files:,}")
        print(f"[X] Уже обработано ранее: {self.processed_count:,}")
        print(f"[X] Начальная память: RSS={start_mem.get('process_rss_mb', 0):.0f} MB, VMS={start_mem.get('process_vms_mb', 0):.0f} MB")
        print(f"[X] System Commit: {start_mem.get('system_commit_percent', 0):.1f}%")
        print("=" * 70)
        print()
        
        try:
            for i, fc in enumerate(files_to_process):
                if self.stop_requested:
                    print("\n[STOP] Прерывание обработки по запросу...")
                    break
                
                try:
                    fc_with_content = self.connector.get_content(fc)
                    if not fc_with_content or not fc_with_content.content:
                        self._log_failed_file(
                            fc.path, 
                            "Не удалось загрузить содержимое файла (возможно, повреждён или нет доступа)",
                            "content_load_error"
                        )
                        continue
                except Exception as e:
                    self._log_failed_file(fc.path, str(e), "content_load_exception")
                    continue
                
                try:
                    file_hash = self.hasher.hash_bytes(fc_with_content.content)
                    if not file_hash and hasattr(fc_with_content, 'path'):
                        file_hash = self.hasher.hash_file(Path(fc_with_content.path))
                    if not file_hash:
                        self._log_failed_file(fc.path, "Не удалось вычислить хэш файла", "hash_error")
                        continue
                except Exception as e:
                    self._log_failed_file(fc.path, str(e), "hash_exception")
                    continue
                
                context = ProcessingContext(file_context=fc_with_content)
                
                try:
                    findings_count = self._process_file(context, total_new_files)
                except Exception as e:
                    self._log_failed_file(fc.path, str(e), "processing_exception")
                    findings_count = 0
                
                findings_types = self._collect_findings_types(context)
                
                if findings_count > 0:
                    files_with_findings += 1
                    self.files_with_findings += 1
                    self.total_findings += findings_count
                
                self.state_manager.mark_processed(fc_with_content, file_hash, len(findings_types) if findings_types else 0)
                self.processed_count += 1
                processed_in_this_run += 1
                
                current_mem = self.memory_manager.get_memory_usage()
                current_rss = current_mem.get("process_rss_mb", 0)
                current_vms = current_mem.get("process_vms_mb", 0)
                current_commit = current_mem.get("system_commit_percent", 0)
                
                progress.update(
                    processed_in_this_run=processed_in_this_run,
                    processed_total=self.processed_count,
                    files_with_findings=files_with_findings,
                    memory_mb=current_rss,
                    vms_mb=current_vms,
                    commit_percent=current_commit
                )
                
                self._check_and_cleanup()
                self._save_state()
        
        except Exception as e:
            print(f"\n[ERROR] Ошибка при сканировании: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self._save_state(force=True)
            self.catalog_manager.save(force=True)
        
        self._stop_all_workers()
        
        progress.finish()
        
        self._print_failed_files_report()
        self._save_failed_files_report()
        
        for handler in self.handlers:
            handler.flush()
        
        self.monitor.stop_session()
        self.state_manager.save()
        self.metrics.finish_processing()
        
        self.logger.info(f"Завершено: обработано {processed_in_this_run} новых файлов, всего {self.processed_count} | Файлов с находками: {self.files_with_findings}")
    
    def _process_file(self, context: ProcessingContext, total_files_in_source: int = None) -> int:
        total_findings = 0
        file_context = context.file_context
        
        folder_path = str(Path(file_context.path).parent)
        
        for classifier in self.classifiers:
            if context.stop_processing:
                break
            
            if not classifier.can_classify(file_context):
                continue
            
            try:
                result = classifier.classify(context)
                context.classifier_results[classifier.classifier_name] = result
                
                for handler in self.handlers:
                    handler.write(result, file_context)
                
                self.metrics.update(result)
                
                if result.findings:
                    total_findings += len(result.findings)
                    
                    self.catalog_manager.update_folder(
                        folder_path=folder_path,
                        source_type=file_context.source_type.value,
                        classifier_name=classifier.classifier_name,
                        findings=result.findings
                    )
                
                if hasattr(classifier, 'ocr_count'):
                    self.ocr_stats["count"] += classifier.ocr_count
                    self.ocr_stats["errors"] += classifier.ocr_errors
                    self.ocr_stats["time"] += classifier.ocr_time
                    
                    if classifier.ocr_count > 0:
                        avg_time = classifier.ocr_time / classifier.ocr_count if classifier.ocr_count > 0 else 0
                        self.monitor.record_ocr(avg_time, classifier.ocr_errors == 0)
                    
                    classifier.ocr_count = 0
                    classifier.ocr_errors = 0
                    classifier.ocr_time = 0.0
                
            except Exception as e:
                self.logger.error(f"Ошибка в {classifier.classifier_name}: {e}")
        
        context.shared_cache.clear()
        
        # Обновление монитора производительности
        if self.monitor and self.monitor.enabled:
            processing_time = sum(r.processing_time for r in context.classifier_results.values())
            has_findings = total_findings > 0
            self.monitor.update_file(
                file_size=file_context.size_bytes,
                processing_time=processing_time,
                has_findings=has_findings,
                findings_count=total_findings
            )
        
        return total_findings
    
    def stop(self) -> None:
        if self.stop_requested:
            return
        self.stop_requested = True
        
        print("[STOP] Финальное сохранение состояния...")
        self._save_state(force=True)
        self.catalog_manager.save(force=True)
        self.state_manager.save()
        
        print("[STOP] Финальная очистка памяти...")
        for _ in range(3):
            gc.collect()
        
        if sys.platform == 'win32':
            try:
                kernel32 = ctypes.windll.kernel32
                process = kernel32.GetCurrentProcess()
                kernel32.SetProcessWorkingSetSize(process, -1, -1)
            except:
                pass
        
        print("[STOP] Остановка рабочих процессов...")
        self._stop_all_workers()
        print("[STOP] Завершено")
    
    def get_statistics(self) -> Dict[str, Any]:
        metrics = self.metrics.get_summary()
        
        mem_stats = {}
        if self.memory_samples:
            mem_deltas = [s["mem_delta_mb"] for s in self.memory_samples]
            mem_stats = {
                "total_samples": len(self.memory_samples),
                "total_memory_delta_mb": sum(mem_deltas),
                "avg_memory_delta_mb": sum(mem_deltas) / len(mem_deltas),
                "max_memory_delta_mb": max(mem_deltas),
                "min_memory_delta_mb": min(mem_deltas)
            }
        
        return {
            "processed_files": self.processed_count,
            "files_with_findings": self.files_with_findings,
            "total_findings": self.total_findings,
            "failed_files_count": len(self.failed_files),
            "failed_files": self.failed_files[:100],
            "metrics": metrics,
            "ocr": self.ocr_stats,
            "state": self.state_manager.get_stats(),
            "catalog": self.catalog_manager.get_statistics(),
            "models_reload_count": self.models_reload_count,
            "models_reload_failures": self.models_reload_failures,
            "memory": mem_stats,
            "system_memory": self.memory_manager.get_system_status(),
            "adaptive": self.adaptive_manager.get_efficiency_stats()
        }


__all__ = ['Orchestrator']