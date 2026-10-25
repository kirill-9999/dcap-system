#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR Worker - отдельный процесс для Tesseract OCR
"""

import logging
import os

logger = logging.getLogger(__name__)
import gc
import time
import tempfile
import subprocess
import hashlib
from queue import Empty
import multiprocessing as mp
from multiprocessing import Queue, Process
from typing import Dict, Any, Optional
from pathlib import Path
from typing import Dict, Optional, Tuple
from collections import OrderedDict
from functools import lru_cache


@lru_cache(maxsize=1)
def _find_tesseract_cached() -> str:
    for env_var in ("TESSERACT_PATH", "TESSERACT_CMD"):
        env_cmd = os.environ.get(env_var, "")
        if env_cmd and os.path.exists(env_cmd):
            return env_cmd
    possible_paths = [
        r"D:\dev\Tesseract-OCR\tesseract.exe",
        r"E:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    try:
        result = subprocess.run(['where', 'tesseract'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split('\n')[0]
    except Exception:
        pass
    return 'tesseract'


@lru_cache(maxsize=1)
def _detect_langs_cached(tesseract_cmd: str) -> str:
    try:
        result = subprocess.run([tesseract_cmd, '--list-langs'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5, shell=False)
        if result.returncode == 0:
            langs = result.stdout
            if 'rus' in langs and 'eng' in langs:
                return 'rus+eng'
            elif 'rus' in langs:
                return 'rus'
            elif 'eng' in langs:
                return 'eng'
    except Exception:
        pass
    return 'rus+eng'


class OCRWorker:
    """OCR Worker - запускается в отдельном процессе"""
    
    def __init__(self):
        self._tesseract_cmd = None
        self._languages = "rus+eng"
        self._running = True
        self._request_count = 0
        self._max_cache_size = 500
        self._cache = OrderedDict()
        self._stats = {"processed": 0, "errors": 0, "cache_hits": 0, "ocr_time": 0.0}
    
    def _find_tesseract(self) -> str:
        """     tesseract.exe  """
        try:
            cmd = _find_tesseract_cached()
            if cmd and os.path.exists(cmd):
                logger.debug(f"[OCR_WORKER] Found via cached: {cmd}")
                return cmd
        except Exception:
            pass
        #     (   )
        for env_var in ("TESSERACT_PATH", "TESSERACT_CMD"):
            env_cmd = os.environ.get(env_var, "")
            if env_cmd and os.path.exists(env_cmd):
                logger.debug(f"[OCR_WORKER] Tesseract from {env_var}: {env_cmd}")
                return env_cmd

        possible_paths = [
            r'D:\dev\Tesseract-OCR\tesseract.exe',
            r'E:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ]

        for path in possible_paths:
            if os.path.exists(path):
                logger.debug(f"[OCR_WORKER] Found Tesseract: {path}")
                return path

        try:
            result = subprocess.run(
                ['where', 'tesseract'],
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip().split('\n')[0]
                logger.debug(f"[OCR_WORKER] Found via 'where': {path}")
                return path
        except:
            pass

        logger.debug(f"[OCR_WORKER] WARNING: Tesseract not found, using 'tesseract' from PATH")
        return 'tesseract'
    
    def _detect_languages(self) -> str:
        """Определение доступных языков"""
        try:
            return _detect_langs_cached(self._tesseract_cmd)
        except Exception:
            pass
        try:
            result = subprocess.run(
                [self._tesseract_cmd, '--list-langs'],
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=10,
                shell=False
            )
            if result.returncode == 0:
                langs = result.stdout
                if 'rus' in langs and 'eng' in langs:
                    return 'rus+eng'
                elif 'rus' in langs:
                    return 'rus'
                elif 'eng' in langs:
                    return 'eng'
        except Exception as e:
            logger.debug(f"[OCR_WORKER] Language detection failed: {e}")
        return 'rus+eng'
    
    def _get_cache_key(self, image_data: bytes, languages: str, psm: int) -> str:
        """Генерация ключа кэша"""
# MD5 используется как кэш-ключ для OCR temp-файла, НЕ для криптографии (BACKLOG-066).
        return hashlib.md5(image_data + f"{languages}_{psm}".encode()).hexdigest()  # nosemgrep: python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5
    
    def _add_to_cache(self, key: str, value: str):
        """Добавление в кэш с LRU"""
        if key in self._cache:
            self._cache.move_to_end(key)
            return
        while len(self._cache) >= self._max_cache_size:
            self._cache.popitem(last=False)
        self._cache[key] = value
    
    def _get_from_cache(self, key: str) -> Optional[str]:
        """Получение из кэша"""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None
    
    def _perform_ocr(self, image_data: bytes, languages: str, psm: int, timeout: int) -> Optional[str]:
        """Выполнение OCR через Tesseract"""
        temp_img = None
        temp_txt = None
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(image_data)
                temp_img = f.name
            
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
                temp_txt = f.name
            
            output_base = temp_txt[:-4]
            
            cmd = [self._tesseract_cmd, temp_img, output_base, '-l', languages, '--psm', str(psm)]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=timeout,
                shell=False
            )
            
            if result.returncode != 0:
                return None
            
            if not os.path.exists(temp_txt):
                return None
            
            with open(temp_txt, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if not text or len(text.strip()) < 10:
                return None
            
            return text[:5000]
            
        except subprocess.TimeoutExpired:
            return None
        except Exception as e:
            return None
        finally:
            for path in [temp_img, temp_txt]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
    
    def _process_request(self, request: Dict) -> Dict:
        """Обработка одного OCR запроса"""
        request_id = request.get("id", 0)
        image_data = request.get("image_data")
        languages = request.get("languages", "rus+eng")
        psm = request.get("psm", 6)
        timeout = request.get("timeout", 60)
        
        if not image_data:
            return {
                "id": request_id,
                "success": False,
                "text": None,
                "error": "No image data"
            }
        
        cache_key = self._get_cache_key(image_data, languages, psm)
        
        cached_text = self._get_from_cache(cache_key)
        if cached_text is not None:
            self._stats["cache_hits"] += 1
            return {
                "id": request_id,
                "success": True,
                "text": cached_text,
                "from_cache": True
            }
        
        start = time.time()
        text = self._perform_ocr(image_data, languages, psm, timeout)
        elapsed = time.time() - start
        
        if text:
            self._add_to_cache(cache_key, text)
            self._stats["processed"] += 1
            self._stats["ocr_time"] += elapsed
            return {
                "id": request_id,
                "success": True,
                "text": text,
                "from_cache": False
            }
        else:
            self._stats["errors"] += 1
            return {
                "id": request_id,
                "success": False,
                "text": None,
                "error": "OCR failed or timeout"
            }
    
    def _cleanup_temp_files(self):
        """Очистка временных файлов"""
        temp_dir = Path(tempfile.gettempdir())
        try:
            for f in temp_dir.glob("tmp*"):
                try:
                    if f.is_file() and time.time() - f.stat().st_mtime > 3600:
                        f.unlink()
                except:
                    pass
        except:
            pass
    
    def run(self, request_queue: Queue, response_queue: Queue, max_cache_size: int = 500):
        """Основной цикл обработки"""
        self._max_cache_size = max_cache_size
        logger.debug(f"[OCR_WORKER] Процесс запущен (PID: {os.getpid()})")
        
        self._tesseract_cmd = self._find_tesseract()
        self._languages = self._detect_languages()
        logger.debug(f"[OCR_WORKER] Tesseract: {self._tesseract_cmd}")
        logger.debug(f"[OCR_WORKER] Языки: {self._languages}")
        
        last_gc = time.time()
        last_cleanup = time.time()
        
        while self._running:
            try:
                try:
                    request = request_queue.get(timeout=1.0)
                except Empty:
                    now = time.time()
                    if now - last_gc > 60:
                        gc.collect()
                        last_gc = now
                    if now - last_cleanup > 300:
                        self._cleanup_temp_files()
                        last_cleanup = now
                    continue
                
                if request is None:
                    break
                
                response = self._process_request(request)
                response_queue.put(response)
                
                self._request_count += 1
                
                if self._request_count % 100 == 0:
                    gc.collect()
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.debug(f"[OCR_WORKER] Error: {e}")
                if 'request' in locals():
                    try:
                        response_queue.put({
                            "id": request.get("id", 0),
                            "success": False,
                            "text": None,
                            "error": str(e)
                        })
                    except:
                        pass
        
        logger.debug(f"[OCR_WORKER] Завершение. Обработано запросов: {self._request_count}")
        logger.debug(f"[OCR_WORKER] Статистика: {self._stats}")
    
    def stop(self):
        self._running = False


# Глобальная функция для запуска процесса (должна быть на уровне модуля для pickle)
def _run_ocr_worker(request_queue: Queue, response_queue: Queue, max_cache_size: int):
    """Целевая функция для процесса"""
    import signal
    # Игнорируем Ctrl+C — завершение управляется через очередь родительским процессом
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    worker = OCRWorker()
    worker.run(request_queue, response_queue, max_cache_size)


def start_ocr_worker(models_cache: str = "models", max_cache_size: int = 500) -> Tuple[Process, Queue, Queue]:
    """Запуск OCR рабочего процесса"""
    try:
        mp.set_start_method('spawn', force=True)
    except RuntimeError:
        pass
    
    request_queue = Queue(maxsize=1000)
    response_queue = Queue(maxsize=1000)
    
    # Используем глобальную функцию, а не вложенную
    process = Process(
        target=_run_ocr_worker,
        args=(request_queue, response_queue, max_cache_size),
        name="OCRWorker",
        daemon=False
    )
    process.start()
    
    return process, request_queue, response_queue


def stop_ocr_worker(process: Process, request_queue: Queue, response_queue: Queue):
    """Остановка OCR рабочего процесса.

    BUG-081 (TASK-052, v3.13.20): graceful shutdown — сначала штатный выход через
    None в request_queue (процесс печатает «Завершение. Обработано запросов: N»),
    затем join(5) → terminate → join(2) → kill.
    """
    try:
        request_queue.put(None, timeout=1)
    except Exception:
        pass

    if process and process.is_alive():
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        if process.is_alive():
            process.kill()


__all__ = ['start_ocr_worker', 'stop_ocr_worker']