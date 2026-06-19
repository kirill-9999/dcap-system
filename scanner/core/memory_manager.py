#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Memory Manager
С поддержкой мониторинга виртуальной памяти (Commit Charge)
"""

import psutil
import gc
import threading
import sys
import ctypes
from datetime import datetime
from typing import Dict, Any, Optional


class MemoryManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.process = psutil.Process()
        self.last_gc_time = datetime.now()
        self.gc_interval_seconds = config.get("gc_interval_seconds", 30)
        self.memory_limit_rss_mb = config.get("memory_limit_rss_mb", 8192)
        self.memory_limit_vms_mb = config.get("memory_limit_vms_mb", 12000)
        self.warning_threshold = config.get("warning_threshold", 0.8)
        self.emergency_restart_threshold = config.get("emergency_restart_threshold", 85)  # % от лимита системы
        self.monitor_virtual_memory = config.get("monitor_virtual_memory", True)
        self.memory_history = []
        self.max_history = 100
        
        # Получаем системную информацию
        self.system_memory = psutil.virtual_memory()
        self.system_swap = psutil.swap_memory()
        
        print(f"[MEMORY] Менеджер памяти инициализирован:")
        print(f"   Физическая память: {self.system_memory.total / 1024 / 1024 / 1024:.1f} GB")
        print(f"   Файл подкачки: {self.system_swap.total / 1024 / 1024 / 1024:.1f} GB")
        print(f"   Порог RSS: {self.memory_limit_rss_mb} MB")
        print(f"   Порог VMS: {self.memory_limit_vms_mb} MB")
    
    def get_system_commit_charge_percent(self) -> float:
        """Получение процента использования системной виртуальной памяти (Commit Charge)"""
        try:
            # Получаем системную информацию
            system_mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Общий лимит = физическая память + файл подкачки
            total_commit_limit = system_mem.total + swap.total
            # Текущий Commit Charge = использовано физической памяти + использовано swap
            current_commit = system_mem.used + swap.used
            
            if total_commit_limit > 0:
                return (current_commit / total_commit_limit) * 100
            return 0
        except Exception as e:
            print(f"[MEMORY] Ошибка получения Commit Charge: {e}")
            return 0
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Получение детального использования памяти"""
        try:
            mem_info = self.process.memory_info()
            
            # RSS - физическая память (рабочий набор)
            rss_mb = mem_info.rss / 1024 / 1024
            
            # VMS - виртуальная память (Commit Charge)
            vms_mb = mem_info.vms / 1024 / 1024
            
            # Private Bytes (более точное измерение)
            private_mb = rss_mb
            if hasattr(mem_info, 'private'):
                private_mb = mem_info.private / 1024 / 1024
            
            # USS - уникальная память
            uss_mb = 0
            if hasattr(mem_info, 'uss'):
                uss_mb = mem_info.uss / 1024 / 1024
            
            # Системная информация
            system_commit_percent = self.get_system_commit_charge_percent()
            
            result = {
                "process_rss_mb": rss_mb,
                "process_vms_mb": vms_mb,
                "process_private_mb": private_mb,
                "process_uss_mb": uss_mb,
                "process_memory_percent": self.process.memory_percent(),
                "system_commit_percent": system_commit_percent,
                "limit_rss_mb": self.memory_limit_rss_mb,
                "limit_vms_mb": self.memory_limit_vms_mb,
                "exceeded_rss": rss_mb > self.memory_limit_rss_mb,
                "exceeded_vms": vms_mb > self.memory_limit_vms_mb,
                "emergency_required": system_commit_percent > self.emergency_restart_threshold,
                "timestamp": datetime.now().isoformat()
            }
            
            # Сохраняем историю
            self.memory_history.append(result)
            if len(self.memory_history) > self.max_history:
                self.memory_history.pop(0)
            
            return result
            
        except Exception as e:
            print(f"[MEMORY] Ошибка получения памяти: {e}")
            return {
                "process_rss_mb": 0,
                "process_vms_mb": 0,
                "system_commit_percent": 0,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_memory_trend(self) -> Dict[str, Any]:
        """Анализ тренда памяти"""
        if len(self.memory_history) < 2:
            return {"trend": "unknown", "delta_rss_mb": 0, "delta_vms_mb": 0, "avg_growth_rss": 0, "avg_growth_vms": 0}
        
        # Берем последние 20 измерений
        recent = self.memory_history[-20:]
        
        rss_values = [m.get("process_rss_mb", 0) for m in recent if m.get("process_rss_mb", 0) > 0]
        vms_values = [m.get("process_vms_mb", 0) for m in recent if m.get("process_vms_mb", 0) > 0]
        
        if len(rss_values) < 2:
            return {"trend": "stable", "delta_rss_mb": 0, "delta_vms_mb": 0, "avg_growth_rss": 0, "avg_growth_vms": 0}
        
        first_rss = rss_values[0]
        last_rss = rss_values[-1]
        delta_rss = last_rss - first_rss
        
        first_vms = vms_values[0] if vms_values else 0
        last_vms = vms_values[-1] if vms_values else 0
        delta_vms = last_vms - first_vms
        
        avg_growth_rss = delta_rss / len(rss_values) if len(rss_values) > 0 else 0
        avg_growth_vms = delta_vms / len(vms_values) if len(vms_values) > 0 else 0
        
        if delta_rss > 100:
            trend = "growing"
        elif delta_rss < -100:
            trend = "shrinking"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "delta_rss_mb": delta_rss,
            "delta_vms_mb": delta_vms,
            "avg_growth_rss": avg_growth_rss,
            "avg_growth_vms": avg_growth_vms,
            "first_rss_mb": first_rss,
            "last_rss_mb": last_rss,
            "samples": len(rss_values)
        }
    
    def check_and_collect(self, force: bool = False) -> Dict[str, Any]:
        """Проверка памяти и запуск GC при необходимости"""
        mem = self.get_memory_usage()
        current_rss = mem.get("process_rss_mb", 0)
        current_vms = mem.get("process_vms_mb", 0)
        system_commit = mem.get("system_commit_percent", 0)
        now = datetime.now()
        
        result = {
            "gc_triggered": False,
            "before_rss_mb": current_rss,
            "before_vms_mb": current_vms,
            "after_rss_mb": current_rss,
            "after_vms_mb": current_vms,
            "freed_rss_mb": 0,
            "freed_vms_mb": 0,
            "reason": ""
        }
        
        # Проверяем необходимость GC
        time_since_last_gc = (now - self.last_gc_time).total_seconds()
        
        if force:
            result["reason"] = "forced"
            result["gc_triggered"] = True
        elif current_rss > self.memory_limit_rss_mb * self.warning_threshold:
            result["reason"] = f"RSS threshold: {current_rss:.0f} > {self.memory_limit_rss_mb * self.warning_threshold:.0f}"
            result["gc_triggered"] = True
        elif current_vms > self.memory_limit_vms_mb * self.warning_threshold:
            result["reason"] = f"VMS threshold: {current_vms:.0f} > {self.memory_limit_vms_mb * self.warning_threshold:.0f}"
            result["gc_triggered"] = True
        elif time_since_last_gc > self.gc_interval_seconds:
            result["reason"] = f"time_interval: {time_since_last_gc:.0f}s > {self.gc_interval_seconds}s"
            result["gc_triggered"] = True
        
        if result["gc_triggered"]:
            before_rss = current_rss
            before_vms = current_vms
            
            # Запускаем GC несколько раз
            for _ in range(3):
                gc.collect()
            
            # Для Windows - попытка сброса рабочего набора
            if sys.platform == 'win32':
                try:
                    kernel32 = ctypes.windll.kernel32
                    process = kernel32.GetCurrentProcess()
                    kernel32.SetProcessWorkingSetSize(process, -1, -1)
                except:
                    pass
            
            after_mem = self.get_memory_usage()
            after_rss = after_mem.get("process_rss_mb", 0)
            after_vms = after_mem.get("process_vms_mb", 0)
            
            freed_rss = before_rss - after_rss
            freed_vms = before_vms - after_vms
            
            result["after_rss_mb"] = after_rss
            result["after_vms_mb"] = after_vms
            result["freed_rss_mb"] = freed_rss
            result["freed_vms_mb"] = freed_vms
            
            self.last_gc_time = now
            
            print(f"[MEMORY] GC: освобождено RSS {freed_rss:.0f} MB, VMS {freed_vms:.0f} MB")
            print(f"[MEMORY] Причина: {result['reason']}")
        
        return result
    
    def check_emergency(self) -> bool:
        """Проверка необходимости аварийного перезапуска"""
        mem = self.get_memory_usage()
        system_commit = mem.get("system_commit_percent", 0)
        
        if system_commit > self.emergency_restart_threshold:
            print(f"[MEMORY] ⚠️ АВАРИЙНЫЙ ПОРОГ! System Commit: {system_commit:.1f}% > {self.emergency_restart_threshold}%")
            return True
        return False
    
    def should_cleanup_caches(self, current_rss_mb: float, current_vms_mb: float, files_since_cleanup: int, cleanup_interval: int) -> tuple:
        """Проверка необходимости очистки кэшей"""
        need_cleanup = False
        reason = ""
        
        # По RSS
        if current_rss_mb > self.config.get("cache_memory_threshold_rss", 3500):
            need_cleanup = True
            reason = f"RSS {current_rss_mb:.0f} MB > {self.config.get('cache_memory_threshold_rss', 3500)} MB"
        # По VMS
        elif self.monitor_virtual_memory and current_vms_mb > self.config.get("cache_memory_threshold_vms", 7000):
            need_cleanup = True
            reason = f"VMS {current_vms_mb:.0f} MB > {self.config.get('cache_memory_threshold_vms', 7000)} MB"
        # По интервалу
        elif files_since_cleanup >= cleanup_interval and files_since_cleanup > 0:
            need_cleanup = True
            reason = f"интервал {files_since_cleanup} >= {cleanup_interval} файлов"
        
        return need_cleanup, reason
    
    def should_reload_models(self, current_rss_mb: float, current_vms_mb: float, files_since_reload: int, reload_interval: int) -> tuple:
        """Проверка необходимости перезагрузки моделей"""
        need_reload = False
        reason = ""
        
        # По RSS
        if current_rss_mb > self.config.get("models_memory_threshold_rss", 4500):
            need_reload = True
            reason = f"RSS {current_rss_mb:.0f} MB > {self.config.get('models_memory_threshold_rss', 4500)} MB"
        # По VMS
        elif self.monitor_virtual_memory and current_vms_mb > self.config.get("models_memory_threshold_vms", 9000):
            need_reload = True
            reason = f"VMS {current_vms_mb:.0f} MB > {self.config.get('models_memory_threshold_vms', 9000)} MB"
        # По интервалу
        elif files_since_reload >= reload_interval and files_since_reload > 0:
            need_reload = True
            reason = f"интервал {files_since_reload} >= {reload_interval} файлов"
        
        # Аварийная проверка
        if self.check_emergency():
            need_reload = True
            reason = f"АВАРИЙНЫЙ ПОРОГ: system commit {self.get_system_commit_charge_percent():.1f}%"
        
        return need_reload, reason
    
    def get_process_info(self) -> Dict[str, Any]:
        """Детальная информация о процессе"""
        try:
            mem = self.get_memory_usage()
            return {
                "pid": self.process.pid,
                "name": self.process.name(),
                "status": self.process.status(),
                "cpu_percent": self.process.cpu_percent(interval=0.1),
                "memory_rss_mb": mem.get("process_rss_mb", 0),
                "memory_vms_mb": mem.get("process_vms_mb", 0),
                "num_threads": self.process.num_threads(),
                "create_time": datetime.fromtimestamp(self.process.create_time()).isoformat(),
                "system_commit_percent": mem.get("system_commit_percent", 0)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_all_dcap_processes_memory(self) -> Dict[str, Any]:
        """Получение суммарной памяти всех процессов DCAP"""
        total_rss = 0
        total_vms = 0
        processes = []
        current_pid = self.process.pid
        
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
            try:
                name = proc.info['name']
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                
                if (name.lower() in ['python.exe', 'python'] and 
                    ('dcap' in cmdline.lower() or 'agent' in cmdline.lower() or 
                     proc.info['pid'] == current_pid or
                     'model_worker' in cmdline.lower() or
                     'ocr_worker' in cmdline.lower())):
                    
                    mem_info = proc.info['memory_info']
                    rss_mb = mem_info.rss / 1024 / 1024
                    vms_mb = mem_info.vms / 1024 / 1024
                    
                    total_rss += rss_mb
                    total_vms += vms_mb
                    
                    processes.append({
                        "pid": proc.info['pid'],
                        "name": name,
                        "rss_mb": rss_mb,
                        "vms_mb": vms_mb
                    })
            except:
                continue
        
        return {
            "total_rss_mb": total_rss,
            "total_vms_mb": total_vms,
            "processes": processes,
            "count": len(processes)
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Получение статуса системы в целом"""
        try:
            system_mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            return {
                "physical_total_gb": system_mem.total / 1024 / 1024 / 1024,
                "physical_available_gb": system_mem.available / 1024 / 1024 / 1024,
                "physical_used_gb": system_mem.used / 1024 / 1024 / 1024,
                "physical_percent": system_mem.percent,
                "swap_total_gb": swap.total / 1024 / 1024 / 1024,
                "swap_used_gb": swap.used / 1024 / 1024 / 1024,
                "swap_percent": swap.percent,
                "commit_limit_gb": (system_mem.total + swap.total) / 1024 / 1024 / 1024,
                "commit_used_gb": (system_mem.used + swap.used) / 1024 / 1024 / 1024,
                "commit_percent": self.get_system_commit_charge_percent()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def reset_stats(self):
        """Сброс статистики"""
        self.memory_history.clear()
        self.last_gc_time = datetime.now()
        for _ in range(3):
            gc.collect()
        print("[MEMORY] Статистика сброшена")


__all__ = ['MemoryManager']