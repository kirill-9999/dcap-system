#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Performance Monitor
Сбор метрик производительности в реальном времени
"""

import time
import threading
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import deque


class PerformanceMonitor:
    """
    Мониторинг производительности:
    - Скорость обработки файлов
    - Использование CPU/RAM/диска
    - Статистика по OCR
    - Финальный отчёт
    """
    
    def __init__(self, log_dir: Path, interval: float = 5.0, enabled: bool = True):
        self.log_dir = Path(log_dir)
        self.interval = interval  # секунды между замерами
        self.enabled = enabled
        self.session_active = False
        
        # Статистика файлов
        self.total_files = 0
        self.total_size_bytes = 0
        self.total_processing_time = 0.0
        self.processing_times: List[float] = []
        self.files_with_findings = 0
        self.total_findings = 0
        
        # OCR статистика
        self.ocr_count = 0
        self.ocr_errors = 0
        self.ocr_total_time = 0.0
        
        # Системные метрики
        self.cpu_samples: List[float] = []
        self.ram_samples: List[float] = []
        self.disk_read_samples: List[float] = []
        self.disk_write_samples: List[float] = []
        
        # Для скорости
        self.last_time = None
        self.last_files = 0
        self.speed_samples: deque = deque(maxlen=10)
        
        # Фоновый поток
        self._thread = None
        self._stop_event = threading.Event()
        
        # Процесс для замера памяти
        self._process = psutil.Process()
        
        # Диск I/O (накопительно)
        self._last_disk_io = psutil.disk_io_counters()
        
        print(f"[MONITOR] Инициализирован, интервал {interval}с, лог: {log_dir}")
    
    def start_session(self):
        """Начать сессию мониторинга"""
        if not self.enabled:
            return
        
        if self.session_active:
            return
        
        self.session_active = True
        self._reset_stats()
        self.last_time = time.time()
        self.last_files = 0
        
        # Запускаем фоновый сбор метрик
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._background_collector, daemon=True)
        self._thread.start()
        
        print("[MONITOR] Мониторинг запущен")
    
    def stop_session(self):
        """Остановить сессию и вывести финальный отчёт"""
        if not self.enabled or not self.session_active:
            return
        
        self.session_active = False
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        self._print_final_report()
        print("[MONITOR] Мониторинг остановлен")
    
    def update_file(self, file_size: int, processing_time: float, has_findings: bool = False, findings_count: int = 0):
        """
        Обновить статистику по обработанному файлу
        
        Args:
            file_size: размер файла в байтах
            processing_time: время обработки в секундах
            has_findings: есть ли находки
            findings_count: количество находок (если >0, переопределяет has_findings)
        """
        if not self.enabled:
            return
        
        self.total_files += 1
        self.total_size_bytes += file_size
        self.total_processing_time += processing_time
        self.processing_times.append(processing_time)
        
        if findings_count > 0:
            self.files_with_findings += 1
            self.total_findings += findings_count
        elif has_findings:
            self.files_with_findings += 1
            self.total_findings += 1
        
        # Обновляем скорость
        now = time.time()
        elapsed = now - self.last_time
        if elapsed >= 1.0 and self.last_files > 0:
            files_diff = self.total_files - self.last_files
            speed = files_diff / elapsed
            self.speed_samples.append(speed)
            self.last_time = now
            self.last_files = self.total_files
    
    def update_ocr(self, processing_time: float, success: bool = True):
        """Обновить статистику OCR"""
        if not self.enabled:
            return
        
        self.ocr_count += 1
        self.ocr_total_time += processing_time
        if not success:
            self.ocr_errors += 1
    
    def record_ocr(self, processing_time: float, success: bool = True):
        """Алиас для update_ocr"""
        self.update_ocr(processing_time, success)
    
    def _reset_stats(self):
        """Сбросить всю статистику"""
        self.total_files = 0
        self.total_size_bytes = 0
        self.total_processing_time = 0.0
        self.processing_times = []
        self.files_with_findings = 0
        self.total_findings = 0
        
        self.ocr_count = 0
        self.ocr_errors = 0
        self.ocr_total_time = 0.0
        
        self.cpu_samples = []
        self.ram_samples = []
        self.disk_read_samples = []
        self.disk_write_samples = []
        
        self.speed_samples.clear()
        
        self.last_time = time.time()
        self.last_files = 0
        
        self._last_disk_io = psutil.disk_io_counters()
    
    def _background_collector(self):
        """Фоновый сбор системных метрик"""
        while not self._stop_event.is_set():
            try:
                # CPU
                cpu_percent = psutil.cpu_percent(interval=0.5)
                self.cpu_samples.append(cpu_percent)
                
                # RAM
                ram = psutil.virtual_memory()
                self.ram_samples.append(ram.percent)
                
                # Disk I/O (дельта с прошлого замера)
                current_io = psutil.disk_io_counters()
                if self._last_disk_io:
                    read_delta = current_io.read_bytes - self._last_disk_io.read_bytes
                    write_delta = current_io.write_bytes - self._last_disk_io.write_bytes
                    # Переводим в MB за интервал
                    self.disk_read_samples.append(read_delta / 1024 / 1024)
                    self.disk_write_samples.append(write_delta / 1024 / 1024)
                self._last_disk_io = current_io
                
                # Ограничим размер истории
                max_samples = 3600  # 5 часов при интервале 5с
                if len(self.cpu_samples) > max_samples:
                    self.cpu_samples = self.cpu_samples[-max_samples:]
                    self.ram_samples = self.ram_samples[-max_samples:]
                    self.disk_read_samples = self.disk_read_samples[-max_samples:]
                    self.disk_write_samples = self.disk_write_samples[-max_samples:]
                
            except Exception as e:
                # Молча пропускаем ошибки сбора метрик
                pass
            
            # Ждём следующий замер
            for _ in range(int(self.interval * 2)):
                if self._stop_event.is_set():
                    break
                time.sleep(0.5)
    
    def _get_average_speed(self) -> float:
        """Средняя скорость обработки (файлов/сек)"""
        if not self.speed_samples:
            if self.total_processing_time > 0:
                return self.total_files / self.total_processing_time
            return 0.0
        return sum(self.speed_samples) / len(self.speed_samples)
    
    def _print_final_report(self):
        """Вывести финальный отчёт"""
        if self.total_files == 0:
            print("\n" + "=" * 70)
            print("ФИНАЛЬНЫЙ ОТЧЁТ ПРОИЗВОДИТЕЛЬНОСТИ")
            print("=" * 70)
            print("\n⚠️ Нет данных для отображения (обработано 0 файлов)")
            print("=" * 70)
            return
        
        avg_time_ms = (self.total_processing_time / self.total_files) * 1000 if self.total_files > 0 else 0
        min_time_ms = min(self.processing_times) * 1000 if self.processing_times else 0
        max_time_ms = max(self.processing_times) * 1000 if self.processing_times else 0
        
        avg_cpu = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
        avg_ram = sum(self.ram_samples) / len(self.ram_samples) if self.ram_samples else 0
        total_disk_read = sum(self.disk_read_samples) if self.disk_read_samples else 0
        total_disk_write = sum(self.disk_write_samples) if self.disk_write_samples else 0
        
        avg_ocr_time_ms = (self.ocr_total_time / self.ocr_count) * 1000 if self.ocr_count > 0 else 0
        ocr_success_rate = ((self.ocr_count - self.ocr_errors) / self.ocr_count * 100) if self.ocr_count > 0 else 0
        
        print("\n" + "=" * 70)
        print("ФИНАЛЬНЫЙ ОТЧЁТ ПРОИЗВОДИТЕЛЬНОСТИ")
        print("=" * 70)
        
        print("\n📊 СТАТИСТИКА ОБРАБОТКИ:")
        print(f"   Обработано файлов: {self.total_files:,}")
        print(f"   Файлов с находками: {self.files_with_findings:,}")
        print(f"   Всего находок: {self.total_findings:,}")
        print(f"   Общий объём: {self.total_size_bytes / 1024 / 1024:.1f} MB")
        print(f"   Средняя скорость: {self._get_average_speed():.2f} файлов/сек")
        print(f"   Среднее время: {avg_time_ms:.1f} мс")
        print(f"   Мин/Макс время: {min_time_ms:.1f}/{max_time_ms:.1f} мс")
        
        if self.ocr_count > 0:
            print("\n🔍 OCR СТАТИСТИКА:")
            print(f"   Вызовов OCR: {self.ocr_count}")
            print(f"   Ошибок OCR: {self.ocr_errors} ({100 - ocr_success_rate:.1f}%)")
            print(f"   Среднее время OCR: {avg_ocr_time_ms:.1f} мс")
        
        print("\n💻 СИСТЕМНЫЕ МЕТРИКИ:")
        print(f"   CPU (средний): {avg_cpu:.1f}%")
        print(f"   RAM (средний): {avg_ram:.1f}%")
        
        # Текущий RAM процесса
        try:
            process_mem = self._process.memory_info().rss / 1024 / 1024
            print(f"   Память процесса: {process_mem:.0f} MB")
        except:
            pass
        
        print(f"\n💾 ДИСКОВЫЙ I/O (за сессию):")
        print(f"   Прочитано: {total_disk_read:.1f} MB")
        print(f"   Записано: {total_disk_write:.1f} MB")
        
        # Скорость в конце
        if self.speed_samples:
            last_speeds = list(self.speed_samples)[-5:]
            avg_last_speed = sum(last_speeds) / len(last_speeds) if last_speeds else 0
            print(f"\n⚡ Финальная скорость: {avg_last_speed:.2f} файлов/сек")
        
        print("\n" + "=" * 70)
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Получить текущую статистику (для API)"""
        return {
            "total_files": self.total_files,
            "files_with_findings": self.files_with_findings,
            "total_findings": self.total_findings,
            "avg_speed": self._get_average_speed(),
            "current_speed": self.speed_samples[-1] if self.speed_samples else 0,
            "avg_processing_time_ms": (self.total_processing_time / self.total_files * 1000) if self.total_files > 0 else 0,
            "ocr": {
                "count": self.ocr_count,
                "errors": self.ocr_errors,
                "avg_time_ms": (self.ocr_total_time / self.ocr_count * 1000) if self.ocr_count > 0 else 0
            },
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "ram_percent": psutil.virtual_memory().percent,
                "process_ram_mb": self._process.memory_info().rss / 1024 / 1024
            }
        }


__all__ = ['PerformanceMonitor']