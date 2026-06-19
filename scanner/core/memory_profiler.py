# memory_profiler.py
import sys
import gc
import tracemalloc
import psutil
import time
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, 'E:/projects/dcap-agent')

class DetailedMemoryProfiler:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.snapshots = []
        self.file_stats = defaultdict(lambda: {"before": 0, "after": 0, "delta": 0})
        self.current_file = None
        
        if enabled:
            tracemalloc.start(25)
    
    def start_file(self, filename):
        """Начать отслеживание для файла"""
        if not self.enabled:
            return
        self.current_file = filename
        gc.collect()
        self.file_stats[filename]["before"] = tracemalloc.get_traced_memory()[0] / 1024 / 1024
        self._log("START", filename)
    
    def end_file(self, filename):
        """Закончить отслеживание для файла"""
        if not self.enabled or self.current_file != filename:
            return
        gc.collect()
        after = tracemalloc.get_traced_memory()[0] / 1024 / 1024
        before = self.file_stats[filename]["before"]
        delta = after - before
        self.file_stats[filename]["after"] = after
        self.file_stats[filename]["delta"] = delta
        self._log("END", filename, f"Δ: {delta:+.2f} MB")
        
        # Если рост большой, показываем детали
        if delta > 5:
            self.show_top_allocations(filename)
    
    def show_top_allocations(self, filename, top_n=10):
        """Показать top N мест выделения памяти"""
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')[:top_n]
        
        print(f"\n  [ALLOCATIONS] {filename}:")
        for stat in top_stats:
            print(f"    {stat}")
    
    def _log(self, event, filename, extra=""):
        mem = psutil.Process().memory_info().rss / 1024 / 1024
        print(f"[MEMORY] {event}: {filename} | Process: {mem:.0f} MB | {extra}")
    
    def get_summary(self):
        """Получить сводку"""
        total_delta = sum(s["delta"] for s in self.file_stats.values())
        large_leaks = {k: v for k, v in self.file_stats.items() if v["delta"] > 5}
        
        print("\n" + "="*70)
        print("MEMORY PROFILER SUMMARY")
        print("="*70)
        print(f"Files tracked: {len(self.file_stats)}")
        print(f"Total memory delta: {total_delta:+.2f} MB")
        print(f"Files with >5MB leak: {len(large_leaks)}")
        
        if large_leaks:
            print("\nLargest leaks:")
            sorted_leaks = sorted(large_leaks.items(), key=lambda x: x[1]["delta"], reverse=True)[:10]
            for f, stats in sorted_leaks:
                print(f"  {f}: +{stats['delta']:.2f} MB")
        
        print("="*70)
        return self.file_stats
    
    def reset(self):
        """Сброс профилировщика"""
        tracemalloc.stop()
        tracemalloc.start(25)
        self.file_stats.clear()


# Глобальный экземпляр
profiler = DetailedMemoryProfiler(enabled=False)  # Включить только для отладки

def enable_profiling():
    global profiler
    profiler = DetailedMemoryProfiler(enabled=True)
    return profiler