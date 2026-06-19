#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - OCR Engine для Windows с нативным Tesseract
"""

import subprocess
import tempfile
import time
import threading
import hashlib
import uuid
import platform
import os
from pathlib import Path
from typing import Optional
from collections import deque


class OCREngine:
    """OCR Engine с нативным Tesseract для Windows"""
    
    def __init__(self, temp_dir: Path, max_workers: int = 1, max_cache_size: int = 100):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self.max_workers = max_workers
        self.max_cache_size = max_cache_size
        self._cache = {}
        self._cache_order = deque()
        self._cache_lock = threading.Lock()
        self._semaphore = threading.Semaphore(max_workers)
        self.stats = {"processed": 0, "errors": 0, "cache_hits": 0, "time": 0.0}
        
        # Находим Tesseract
        self._tesseract_cmd = self._find_tesseract()
        self._languages = self._detect_languages()
        
        print(f"[OCR] Tesseract path: {self._tesseract_cmd}")
        print(f"[OCR] Languages: {self._languages}")
        
        self._cleanup_temp_files()
    
    def _find_tesseract(self) -> str:
        """Поиск Tesseract в системе Windows"""
        # Проверка через where
        try:
            result = subprocess.run(
                ['where', 'tesseract'],
                capture_output=True,
                text=True,
                timeout=5,
                shell=True
            )
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip().split('\n')[0]
                print(f"[OCR] Found via 'where': {path}")
                return path
        except:
            pass
        
        # Стандартные пути установки
        possible_paths = [
            r'E:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.environ.get('USERNAME', '')),
        ]
        
        # Проверка стандартных путей
        for path in possible_paths:
            if os.path.exists(path):
                print(f"[OCR] Found at: {path}")
                return path
        
        # Fallback
        print(f"[OCR] WARNING: Tesseract not found, using 'tesseract' from PATH")
        return 'tesseract'
    
    def _detect_languages(self) -> str:
        """Определение доступных языков"""
        try:
            result = subprocess.run(
                [self._tesseract_cmd, '--list-langs'],
                capture_output=True,
                text=True,
                timeout=10,
                shell=False
            )
            if result.returncode == 0:
                langs = result.stdout
                print(f"[OCR] Available languages: {langs[:200]}")
                if 'rus' in langs:
                    return 'rus+eng'
                return 'eng'
        except Exception as e:
            print(f"[OCR] Language detection failed: {e}")
        
        return 'rus+eng'
    
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
    
    def _get_cache_key(self, image_data: bytes) -> str:
        """Получение ключа кэша"""
        return hashlib.md5(image_data).hexdigest()
    
    def _add_to_cache(self, key: str, value: str):
        """Добавление в кэш с LRU"""
        with self._cache_lock:
            if key in self._cache:
                return
            
            while len(self._cache) >= self.max_cache_size:
                oldest_key = self._cache_order.popleft()
                if oldest_key in self._cache:
                    del self._cache[oldest_key]
            
            self._cache[key] = value
            self._cache_order.append(key)
    
    def ocr_image(self, image_data: bytes, timeout: int = 60) -> Optional[str]:
        """OCR одного изображения через нативный Tesseract"""
        # Проверка кэша
        cache_key = self._get_cache_key(image_data)
        with self._cache_lock:
            if cache_key in self._cache:
                self.stats["cache_hits"] += 1
                self.stats["processed"] += 1
                return self._cache[cache_key]
        
        # Получаем семафор
        acquired = self._semaphore.acquire(timeout=30)
        if not acquired:
            self.stats["errors"] += 1
            return None
        
        temp_img = None
        temp_txt = None
        
        start_time = time.time()
        
        try:
            # Сохраняем изображение во временный файл
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(image_data)
                temp_img = f.name
            
            # Создаём временный файл для вывода
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
                temp_txt = f.name
            
            output_base = temp_txt[:-4]  # удаляем .txt
            
            # Запускаем Tesseract
            cmd = [
                self._tesseract_cmd,
                temp_img,
                output_base,
                '-l', self._languages,
                '--psm', '6'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False
            )
            
            # Читаем результат
            text = ""
            if os.path.exists(temp_txt):
                with open(temp_txt, 'r', encoding='utf-8') as f:
                    text = f.read()
            
            elapsed = time.time() - start_time
            self.stats["time"] += elapsed
            
            if text and len(text.strip()) > 10:
                result_text = text[:5000]
                self._add_to_cache(cache_key, result_text)
                self.stats["processed"] += 1
                return result_text
            
            self.stats["errors"] += 1
            return None
            
        except subprocess.TimeoutExpired:
            self.stats["errors"] += 1
            print(f"[OCR] Timeout after {timeout}s")
            return None
        except Exception as e:
            self.stats["errors"] += 1
            print(f"[OCR] Error: {e}")
            return None
        finally:
            # Очистка временных файлов
            for path in [temp_img, temp_txt]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
            self._semaphore.release()
    
    def get_stats(self) -> dict:
        """Получение статистики"""
        avg_time = self.stats["time"] / self.stats["processed"] if self.stats["processed"] > 0 else 0
        return {
            "processed": self.stats["processed"],
            "errors": self.stats["errors"],
            "cache_hits": self.stats["cache_hits"],
            "avg_time_ms": avg_time * 1000,
            "cache_size": len(self._cache)
        }
    
    def reset(self):
        """Сброс OCR движка"""
        with self._cache_lock:
            self._cache.clear()
            self._cache_order.clear()
        self._cleanup_temp_files()
        print(f"[OCR] Reset completed")


__all__ = ['OCREngine']