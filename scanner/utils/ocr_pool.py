#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - OCR Pool with process isolation and automatic restart
"""

import subprocess
import tempfile
import uuid
import time
import threading
import hashlib
import os
from pathlib import Path
from typing import Optional
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing


def _ocr_worker(image_data: bytes, timeout: int = 30) -> str:
    """
    Рабочая функция для отдельного процесса OCR.
    Выполняется в изолированном процессе, вся память освобождается после завершения.
    """
    temp_file = None
    out_path = None
    
    try:
        # Сохраняем изображение во временный файл
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(image_data)
            temp_file = f.name
        
        # Создаём временный файл для вывода
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            out_path = f.name
        
        # Запускаем Tesseract
        cmd = [
            'tesseract',
            temp_file,
            out_path[:-4],  # удаляем .txt
            '-l', 'rus+eng',
            '--psm', '6'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        # Читаем результат
        text = ""
        txt_path = out_path
        if os.path.exists(txt_path):
            with open(txt_path, 'r', encoding='utf-8') as f:
                text = f.read()
        
        return text[:3000] if text else ""
        
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        return ""
    finally:
        # Очистка временных файлов
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except:
                pass
        if out_path and os.path.exists(out_path):
            try:
                os.unlink(out_path)
            except:
                pass


class OCRPool:
    """
    Пул процессов для OCR с автоматическим перезапуском.
    Преимущества:
    - Каждое изображение обрабатывается в изолированном процессе
    - Память полностью освобождается после каждой операции
    - Периодический перезапуск пула для предотвращения утечек
    """
    
    def __init__(self, temp_dir: Path, max_workers: int = 2, restart_after: int = 500):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self.max_workers = max_workers
        self.restart_after = restart_after
        self._executor = None
        self._processed_count = 0
        self._restart_count = 0
        self._lock = threading.Lock()
        
        # Кэш для одинаковых изображений
        self._cache = {}
        self._cache_order = deque()
        self._cache_lock = threading.Lock()
        self._max_cache_size = 500
        
        self.stats = {
            "processed": 0,
            "errors": 0,
            "cache_hits": 0,
            "restarts": 0,
            "avg_time": 0.0,
            "total_time": 0.0
        }
        
        self._init_pool()
        self._cleanup_temp_files()
    
    def _init_pool(self):
        """Инициализация или перезапуск пула процессов"""
        with self._lock:
            if self._executor:
                try:
                    self._executor.shutdown(wait=True, cancel_futures=True)
                except:
                    pass
            
            # Используем spawn контекст для Windows (более стабильно)
            try:
                mp_context = multiprocessing.get_context('spawn')
                self._executor = ProcessPoolExecutor(
                    max_workers=self.max_workers,
                    mp_context=mp_context
                )
            except:
                self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
            
            self._processed_count = 0
            self._restart_count += 1
            self.stats["restarts"] = self._restart_count
            
            print(f"[OCR] Пул процессов инициализирован (воркеров: {self.max_workers}, рестарт #{self._restart_count})")
    
    def _should_restart(self) -> bool:
        """Проверка необходимости перезапуска пула"""
        return self._processed_count >= self.restart_after
    
    def _add_to_cache(self, key: str, value: str):
        """Добавление результата в кэш (LRU)"""
        with self._cache_lock:
            if key in self._cache:
                return
            
            while len(self._cache) >= self._max_cache_size:
                oldest_key = self._cache_order.popleft()
                if oldest_key in self._cache:
                    del self._cache[oldest_key]
            
            self._cache[key] = value
            self._cache_order.append(key)
    
    def _get_cache_key(self, image_data: bytes) -> str:
        """Получение ключа кэша (MD5)"""
        return hashlib.md5(image_data).hexdigest()
    
    def _cleanup_temp_files(self):
        """Очистка старых временных файлов"""
        try:
            for f in self.temp_dir.glob("ocr_*"):
                try:
                    if f.exists():
                        f.unlink()
                except:
                    pass
            for f in self.temp_dir.glob("tmp*"):
                try:
                    if f.exists():
                        f.unlink()
                except:
                    pass
        except:
            pass
    
    def ocr_image(self, image_data: bytes, timeout: int = 60) -> Optional[str]:
        """
        OCR одного изображения через пул процессов.
        Возвращает распознанный текст или None при ошибке.
        """
        # Проверка кэша
        cache_key = self._get_cache_key(image_data)
        with self._cache_lock:
            if cache_key in self._cache:
                self.stats["cache_hits"] += 1
                self.stats["processed"] += 1
                return self._cache[cache_key]
        
        # Проверка необходимости перезапуска пула
        if self._should_restart():
            print(f"[OCR] Перезапуск пула после {self._processed_count} операций")
            self._init_pool()
        
        start_time = time.time()
        
        try:
            # Отправляем задачу в пул процессов
            future = self._executor.submit(_ocr_worker, image_data, timeout)
            text = future.result(timeout=timeout + 10)
            
            elapsed = time.time() - start_time
            self.stats["total_time"] += elapsed
            
            if text and len(text.strip()) > 10:
                self._add_to_cache(cache_key, text)
                self.stats["processed"] += 1
                with self._lock:
                    self._processed_count += 1
                return text
            
            self.stats["errors"] += 1
            return None
            
        except Exception as e:
            self.stats["errors"] += 1
            print(f"[OCR] Ошибка в пуле: {e}")
            
            # При ошибке перезапускаем пул
            self._init_pool()
            return None
    
    def get_stats(self) -> dict:
        """Получение статистики OCR"""
        avg_time = self.stats["total_time"] / self.stats["processed"] if self.stats["processed"] > 0 else 0
        return {
            "processed": self.stats["processed"],
            "errors": self.stats["errors"],
            "cache_hits": self.stats["cache_hits"],
            "restarts": self.stats["restarts"],
            "avg_time_ms": avg_time * 1000,
            "cache_size": len(self._cache),
            "workers": self.max_workers
        }
    
    def reset(self):
        """Полный сброс OCR движка"""
        print(f"[OCR] Полный сброс...")
        self._init_pool()
        with self._cache_lock:
            self._cache.clear()
            self._cache_order.clear()
        self._cleanup_temp_files()
        self.stats = {
            "processed": 0,
            "errors": 0,
            "cache_hits": 0,
            "restarts": 0,
            "avg_time": 0.0,
            "total_time": 0.0
        }
        self._processed_count = 0
        self._restart_count = 0
        print(f"[OCR] Сброс завершён")
    
    def shutdown(self):
        """Корректное завершение работы пула"""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None


# Глобальный экземпляр для использования во всём приложении
_ocr_pool_instance = None


def get_ocr_pool(temp_dir: Path, max_workers: int = 2, restart_after: int = 500) -> OCRPool:
    """Получение глобального экземпляра OCR пула (Singleton)"""
    global _ocr_pool_instance
    if _ocr_pool_instance is None:
        _ocr_pool_instance = OCRPool(temp_dir, max_workers, restart_after)
    return _ocr_pool_instance


def shutdown_ocr_pool():
    """Завершение работы OCR пула"""
    global _ocr_pool_instance
    if _ocr_pool_instance:
        _ocr_pool_instance.shutdown()
        _ocr_pool_instance = None