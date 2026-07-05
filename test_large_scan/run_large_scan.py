#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Load test for DCAP Scanner on E:\much_of_test_files
"""

import sys
import os
from pathlib import Path

# ========================================
# FIX: Добавляем корень проекта в PYTHONPATH
# ========================================
PROJECT_ROOT = Path(__file__).parent.parent  # поднимаемся на уровень выше из test_large_scan
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)  # Меняем рабочую директорию на корень проекта

print(f"[PATH] Project root: {PROJECT_ROOT}")
print(f"[PATH] Current dir: {os.getcwd()}")
print(f"[PATH] PYTHONPATH: {sys.path[:3]}")

# Теперь импорты будут работать
import time
import json
import psutil
import asyncio
from datetime import datetime
import tracemalloc

from scanner.src.managed_scanner import ManagedScanner


class LoadTester:
    """Load testing with monitoring"""
    
    def __init__(self, source_path: str):
        self.source_path = source_path
        self.start_time = None
        self.end_time = None
        self.metrics = {
            "files_processed": 0,
            "findings": 0,
            "errors": 0,
            "memory_peak_mb": 0,
            "cpu_peak_percent": 0,
            "duration_seconds": 0,
            "speed_files_per_sec": 0
        }
        self.memory_samples = []
        self.cpu_samples = []
        
    def get_file_count(self) -> int:
        """Count files in directory"""
        path = Path(self.source_path)
        if not path.exists():
            print(f"[ERROR] Path does not exist: {self.source_path}")
            return 0
        
        count = 0
        for _ in path.rglob('*'):
            if _.is_file():
                count += 1
        return count
    
    def get_file_types(self) -> dict:
        """Statistics by file type"""
        path = Path(self.source_path)
        types = {}
        for f in path.rglob('*'):
            if f.is_file():
                ext = f.suffix.lower() or 'no_ext'
                types[ext] = types.get(ext, 0) + 1
        return types
    
    def print_stats(self):
        """Print source statistics"""
        path = Path(self.source_path)
        
        if not path.exists():
            print(f"\n[ERROR] Path {self.source_path} does not exist!")
            print("   Please check the path or create the test data folder.")
            return 0
        
        total = self.get_file_count()
        types = self.get_file_types()
        
        print("\n" + "=" * 70)
        print("SOURCE STATISTICS")
        print("=" * 70)
        print(f"   Path: {self.source_path}")
        print(f"   Total files: {total:,}")
        
        if total > 0:
            print(f"\n   TOP 15 FILE TYPES:")
            sorted_types = sorted(types.items(), key=lambda x: x[1], reverse=True)[:15]
            for ext, count in sorted_types:
                ext_name = ext if ext != 'no_ext' else 'no extension'
                print(f"      .{ext_name}: {count:,} ({count/total*100:.1f}%)")
        
        print("=" * 70)
        return total
    
    async def run(self):
        """Run the load test"""
        total_files = self.print_stats()
        
        if total_files == 0:
            print("\n[ERROR] No files to process!")
            print("   Check: E:\\much_of_test_files")
            return
        
        print("\n" + "=" * 70)
        print("LOAD TEST STARTED")
        print("=" * 70)
        print(f"   Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Files: {total_files:,}")
        
        # Time estimate
        if total_files < 1000:
            est_min = total_files / 5 / 60
        elif total_files < 5000:
            est_min = total_files / 4 / 60
        else:
            est_min = total_files / 3 / 60
        
        print(f"   Estimated time: ~{est_min:.1f} minutes")
        print("=" * 70)
        
        tracemalloc.start()
        
        scanner = ManagedScanner(
            name=f"load-test-{datetime.now().strftime('%H%M%S')}",
            manager_endpoint="localhost:50051"
        )
        
        self.start_time = time.time()
        
        try:
            monitor_task = asyncio.create_task(self._monitor())
            await scanner.run_and_exit()
            monitor_task.cancel()
            
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
        finally:
            await scanner.stop()
        
        self.end_time = time.time()
        self.metrics["duration_seconds"] = self.end_time - self.start_time
        if self.metrics["duration_seconds"] > 0 and self.metrics["files_processed"] > 0:
            self.metrics["speed_files_per_sec"] = self.metrics["files_processed"] / self.metrics["duration_seconds"]
        
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')[:10]
        
        self._print_results(top_stats)
        
    async def _monitor(self):
        """Background resource monitoring"""
        process = psutil.Process()
        cpu_count = psutil.cpu_count()
        
        while True:
            try:
                cpu_percent = process.cpu_percent(interval=0.5) / cpu_count
                self.cpu_samples.append(cpu_percent)
                if cpu_percent > self.metrics["cpu_peak_percent"]:
                    self.metrics["cpu_peak_percent"] = cpu_percent
                
                mem_info = process.memory_info()
                mem_mb = mem_info.rss / 1024 / 1024
                self.memory_samples.append(mem_mb)
                if mem_mb > self.metrics["memory_peak_mb"]:
                    self.metrics["memory_peak_mb"] = mem_mb
                
                if len(self.memory_samples) % 2 == 0:
                    elapsed = time.time() - self.start_time if self.start_time else 0
                    print(f"   [MONITOR] {int(elapsed)}s | CPU: {cpu_percent:.1f}% | "
                          f"RAM: {mem_mb:.0f} MB | "
                          f"Peak: {self.metrics['memory_peak_mb']:.0f} MB")
                
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"   [MONITOR] Error: {e}")
                await asyncio.sleep(5)
    
    def _print_results(self, top_stats):
        """Print test results"""
        print("\n" + "=" * 70)
        print("LOAD TEST RESULTS")
        print("=" * 70)
        
        duration = self.metrics["duration_seconds"]
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        
        print(f"\n[TIME]")
        print(f"   {minutes}m {seconds}s ({duration:.1f} sec)")
        
        print(f"\n[PROCESSING]")
        print(f"   Files: {self.metrics['files_processed']:,}")
        print(f"   Findings: {self.metrics['findings']:,}")
        if self.metrics["speed_files_per_sec"] > 0:
            print(f"   Speed: {self.metrics['speed_files_per_sec']:.2f} files/sec")
        else:
            print(f"   Speed: N/A (no files processed)")
        
        print(f"\n[RESOURCES]")
        print(f"   Peak CPU: {self.metrics['cpu_peak_percent']:.1f}%")
        print(f"   Peak RAM: {self.metrics['memory_peak_mb']:.0f} MB")
        if self.memory_samples:
            avg_mem = sum(self.memory_samples) / len(self.memory_samples)
            print(f"   Avg RAM: {avg_mem:.0f} MB")
        
        print(f"\n[TOP MEMORY ALLOCATIONS]")
        for stat in top_stats:
            print(f"   {stat}")
        
        print("\n" + "=" * 70)
        
        # Performance assessment
        if self.metrics["speed_files_per_sec"] > 0:
            files_per_min = self.metrics["speed_files_per_sec"] * 60
            print(f"\n[PERFORMANCE ASSESSMENT]")
            print(f"   Speed: {files_per_min:.0f} files/min")
            
            if self.metrics["speed_files_per_sec"] > 5:
                print("   🏆 Excellent performance!")
            elif self.metrics["speed_files_per_sec"] > 3:
                print("   ✅ Good performance")
            elif self.metrics["speed_files_per_sec"] > 2:
                print("   ✅ Acceptable performance")
            elif self.metrics["speed_files_per_sec"] > 1:
                print("   ⚠️ Average performance, could be optimized")
            else:
                print("   ❌ Poor performance, needs optimization")
            
            # Projection for 22,500 files
            if self.metrics["speed_files_per_sec"] > 0:
                total_time_sec = 22500 / self.metrics["speed_files_per_sec"]
                total_min = total_time_sec / 60
                print(f"\n[PROJECTION FOR 22,500 FILES]")
                print(f"   ~{total_min:.1f} minutes ({total_time_sec/3600:.2f} hours)")
        else:
            print("\n[PERFORMANCE ASSESSMENT]")
            print("   No data to assess performance")
        
        print("=" * 70)


async def main():
    # ========================================
    # TEST DATA PATH
    # ========================================
    SOURCE_PATH = r"E:\much_of_test_files"
    
    if not Path(SOURCE_PATH).exists():
        print(f"\n[ERROR] Path {SOURCE_PATH} does not exist!")
        print("   Please check the path or create the test data folder.")
        print("   Expected: E:\\much_of_test_files")
        return
    
    tester = LoadTester(SOURCE_PATH)
    
    try:
        await tester.run()
    except KeyboardInterrupt:
        print("\n[STOP] Test interrupted by user")
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())