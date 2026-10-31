#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - OCR Engine для Windows с нативным Tesseract
"""

from functools import lru_cache
import logging
import os

logger = logging.getLogger(__name__)
import subprocess

# 53.4k (v3.14.9): детекция tesseract/языков кэшируется на процесс (@lru_cache).
# Раньше OCREngine создавался на каждый файл → 'where tesseract' + '--list-langs'
# вызывались многократно (см. отчёт 53.4k Фаза 2: 3 subprocess/файл).


@lru_cache(maxsize=1)
def _get_tesseract_path():
    for env_var in ("TESSERACT_PATH", "TESSERACT_CMD"):
        env_cmd = os.environ.get(env_var, "")
        if env_cmd and os.path.exists(env_cmd):
            return env_cmd
    try:
        r = subprocess.run(["where", "tesseract"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0].strip()
    except Exception:
        pass
    possible_paths = [
        r'D:\dev\Tesseract-OCR\tesseract.exe',
        r'E:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.environ.get('USERNAME', '')),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return "tesseract"


@lru_cache(maxsize=1)
def _get_tesseract_langs(cmd):
    try:
        r = subprocess.run([cmd, "--list-langs"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, shell=False)
        if r.returncode == 0 and r.stdout:
            t = r.stdout
            if "rus" in t and "eng" in t:
                return "rus+eng"
            if "rus" in t:
                return "rus"
            if "eng" in t:
                return "eng"
    except Exception:
        pass
    return "rus+eng"


import tempfile
import time
import threading
import hashlib
import uuid
import platform
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

        # BUG-137 (v3.13.36): каждый OCREngine работает в СВОЕЙ уникальной
        # подпапке, а не в общем системном temp. Раньше linewise-путь
        # (extract_document_text → DocumentExtractor) создавал новый OCREngine
        # на КАЖДЫЙ файл с temp_dir=tempfile.gettempdir(), а _cleanup_temp_files()
        # удаляла ВСЕ tmp*/ocr_* в системном temp — параллельные экземпляры
        # стирали temp-файлы (входной PNG .png и вывод .txt) друг друга прямо
        # во время работы tesseract → тихая потеря OCR-находок при
        # max_parallel_files > 1. Теперь temp-файлы изолированы в _work_dir.
        self._work_dir = self.temp_dir / f"ocr_{uuid.uuid4().hex[:12]}"
        self._work_dir.mkdir(parents=True, exist_ok=True)

        # Находим Tesseract
        self._tesseract_cmd = self._find_tesseract()
        self._languages = self._detect_languages()
        
        logger.debug(f"[OCR] Tesseract path: {self._tesseract_cmd}")
        logger.debug(f"[OCR] Languages: {self._languages}")
    
    def _find_tesseract(self) -> str:
        """Поиск Tesseract (53.4k v3.14.9: через @lru_cache — subprocess 1 раз на процесс).

        Раньше 'where tesseract' вызывался на каждом OCREngine (на каждый файл) —
        см. отчёт 53.4k Фаза 2. Теперь результат детекции кэшируется на процесс.
        """
        cmd = _get_tesseract_path()
        logger.debug(f"[OCR] Tesseract path: {cmd}")
        return cmd

    def _detect_languages(self) -> str:
        """Определение языков (53.4k v3.14.9: через @lru_cache — '--list-langs' 1 раз)."""
        langs = _get_tesseract_langs(self._tesseract_cmd)
        logger.debug(f"[OCR] Languages: {langs}")
        return langs
    
    def _cleanup_temp_files(self):
        """Очистка временных файлов ТОЛЬКО этого экземпляра (BUG-137).

        Раньше удалялись все `ocr_*`/`tmp*` в общем temp_dir (tempfile.gettempdir()).
        При параллельном сканировании один OCREngine удалял temp-файлы другого
        (активно работающий tesseract терял входной .png или выходной .txt) —
        OCR-находки терялись молча. Теперь чистим только свою подпапку.
        """
        if not self._work_dir.exists():
            return
        try:
            for f in self._work_dir.glob("*"):
                try:
                    if f.is_file():
                        f.unlink()
                except:
                    pass
        except:
            pass
    
    def _get_cache_key(self, image_data: bytes) -> str:
        """Получение ключа кэша"""
# MD5 используется как кэш-ключ для OCR temp-файла, НЕ для криптографии (BACKLOG-066).
        return hashlib.md5(image_data).hexdigest()  # nosemgrep: python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5
    
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
            # BUG-137: temp-файлы создаём в СВОЕЙ подпапке _work_dir, а не в
            # общем tempfile.gettempdir() — параллельные OCREngine не смогут
            # удалить чужие рабочие файлы во время tesseract.
            with tempfile.NamedTemporaryFile(dir=str(self._work_dir), suffix='.png', delete=False) as f:
                f.write(image_data)
                temp_img = f.name
            
            # Создаём временный файл для вывода
            with tempfile.NamedTemporaryFile(dir=str(self._work_dir), suffix='.txt', delete=False) as f:
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
                encoding='utf-8',
                errors='replace',
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
            logger.debug(f"[OCR] Timeout after {timeout}s")
            return None
        except Exception as e:
            self.stats["errors"] += 1
            logger.debug(f"[OCR] Error: {e}")
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
        logger.debug(f"[OCR] Reset completed")


__all__ = ['OCREngine']