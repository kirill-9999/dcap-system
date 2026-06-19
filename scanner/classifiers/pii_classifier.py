#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - PII Classifier (IPC версия)
"""

import os
import re
import time
import gc
import threading
import sys
import ctypes
from pathlib import Path
from typing import Dict, Any, List, Optional

# Добавляем путь для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.base import (
    IClassifier, DataCategory, FileContext,
    ProcessingContext, ClassificationResult, ClassificationFinding
)
from utils.document_extractor import DocumentExtractor
from classifiers.ocr_worker import start_ocr_worker, stop_ocr_worker


class PiiClassifier(IClassifier):
    _instance = None
    _lock = threading.Lock()
    
    # Для ModelWorker
    _worker_process = None
    _request_queue = None
    _response_queue = None
    _worker_started = False
    _worker_ready = False
    _response_thread = None
    _pending_requests = {}
    _next_request_id = 1
    _pending_lock = threading.Lock()
    
    # Для OCRWorker
    _ocr_process = None
    _ocr_request_queue = None
    _ocr_response_queue = None
    _ocr_started = False
    _ocr_ready = False
    _ocr_response_thread = None
    _ocr_pending_requests = {}
    _ocr_next_request_id = 1
    _ocr_pending_lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
                    cls._instance.enabled = True
        return cls._instance
    
    def __init__(self, *args, **kwargs):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self.config = {}
        self.extractor = None
        self.cache = {}
        self.stats = {"files": 0, "findings": 0, "time": 0.0}
        self.ocr_count = 0
        self.ocr_errors = 0
        self.ocr_time = 0.0
        self._initialized = True
        self._timeout = 60.0
        self.enabled = True
    
    @property
    def classifier_name(self) -> str:
        return "pii_classifier"
    
    @property
    def category(self) -> DataCategory:
        return DataCategory.PII
    
    @property
    def version(self) -> str:
        return "3.0-ipc"
    
    def _wait_for_worker_ready(self, timeout: float = 120.0) -> bool:
        """Ожидание готовности ModelWorker"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._worker_ready:
                return True
            time.sleep(0.5)
        return False
    
    def _wait_for_ocr_ready(self, timeout: float = 30.0) -> bool:
        """Ожидание готовности OCRWorker"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._ocr_ready:
                return True
            time.sleep(0.5)
        return False
    
    def _start_worker(self):
        """Запуск ModelWorker"""
        if self._worker_started:
            return
        
        with self._lock:
            if self._worker_started:
                return
            
            try:
                print("[PII] Запуск ModelWorker...")
                from classifiers.model_worker import start_model_worker
                
                models_cache = self.config.get("models_cache", "models")
                use_bert = self.config.get("use_bert", True)
                process, req_q, resp_q = start_model_worker(models_cache, use_bert)
                
                self._worker_process = process
                self._request_queue = req_q
                self._response_queue = resp_q
                self._worker_started = True
                self._worker_ready = False
                
                self._response_thread = threading.Thread(target=self._process_responses, daemon=True)
                self._response_thread.start()
                
                print(f"[PII] ModelWorker запущен (PID: {self._worker_process.pid})")
                
                # Ожидаем готовности worker'а
                if self._wait_for_worker_ready():
                    print(f"[PII] ModelWorker готов к работе")
                else:
                    print(f"[PII] ⚠️ ModelWorker не ответил о готовности")
                
            except Exception as e:
                print(f"[PII] Ошибка запуска ModelWorker: {e}")
                import traceback
                traceback.print_exc()
                self._worker_started = False
    
    def _process_responses(self):
        """Обработка ответов от ModelWorker"""
        while self._worker_started and self._response_queue is not None:
            try:
                response = self._response_queue.get(timeout=0.5)
                request_id = response.get("id")
                if request_id is not None:
                    if request_id == 0 and response.get("ready"):
                        self._worker_ready = True
                    else:
                        with self._pending_lock:
                            self._pending_requests[request_id] = response
            except:
                pass
    
    def _call_model_worker(self, text: str) -> Dict:
        """Вызов ModelWorker для NLP"""
        if not self._worker_started:
            self._start_worker()
        
        if not self._worker_started:
            return {"persons": [], "locations": []}
        
        if not self._worker_ready:
            if not self._wait_for_worker_ready():
                return {"persons": [], "locations": []}
        
        with self._pending_lock:
            request_id = self._next_request_id
            self._next_request_id += 1
            self._pending_requests[request_id] = None
        
        try:
            self._request_queue.put({
                "id": request_id,
                "text": text[:10000]
            }, timeout=5)
        except Exception as e:
            print(f"[PII] Ошибка отправки: {e}")
            return {"persons": [], "locations": []}
        
        start_time = time.time()
        while time.time() - start_time < self._timeout:
            with self._pending_lock:
                response = self._pending_requests.get(request_id)
                if response is not None:
                    del self._pending_requests[request_id]
                    return response.get("result", {"persons": [], "locations": []})
            time.sleep(0.01)
        
        print(f"[PII] Timeout ожидания ответа от ModelWorker (request {request_id})")
        
        with self._pending_lock:
            if request_id in self._pending_requests:
                del self._pending_requests[request_id]
        
        return {"persons": [], "locations": []}
    
    def _stop_worker(self):
        """Остановка ModelWorker"""
        if not self._worker_started:
            return
        
        print("[PII] Остановка ModelWorker...")
        
        try:
            from classifiers.model_worker import stop_model_worker
            stop_model_worker(self._worker_process, self._request_queue, self._response_queue)
        except:
            if self._worker_process and self._worker_process.is_alive():
                self._worker_process.terminate()
                self._worker_process.join(timeout=5)
                if self._worker_process.is_alive():
                    self._worker_process.kill()
        
        self._worker_started = False
        self._worker_ready = False
        self._worker_process = None
        self._request_queue = None
        self._response_queue = None
        
        with self._pending_lock:
            self._pending_requests.clear()
        
        print(f"[PII] ModelWorker остановлен")
    
    def _start_ocr_worker(self):
        """Запуск OCR процесса"""
        if self._ocr_started:
            return
        
        with self._lock:
            if self._ocr_started:
                return
            
            try:
                print("[PII] Запуск OCRWorker...")
                from classifiers.ocr_worker import start_ocr_worker
                
                models_cache = self.config.get("models_cache", "models")
                max_cache_size = self.config.get("ocr_cache_size", 500)
                
                process, req_q, resp_q = start_ocr_worker(models_cache, max_cache_size)
                
                self._ocr_process = process
                self._ocr_request_queue = req_q
                self._ocr_response_queue = resp_q
                self._ocr_started = True
                self._ocr_ready = True
                
                self._ocr_response_thread = threading.Thread(target=self._process_ocr_responses, daemon=True)
                self._ocr_response_thread.start()
                
                print(f"[PII] OCRWorker запущен (PID: {self._ocr_process.pid})")
                
            except Exception as e:
                print(f"[PII] Ошибка запуска OCRWorker: {e}")
                import traceback
                traceback.print_exc()
                self._ocr_started = False
    
    def _process_ocr_responses(self):
        """Обработка ответов от OCR процесса"""
        while self._ocr_started and self._ocr_response_queue is not None:
            try:
                response = self._ocr_response_queue.get(timeout=0.5)
                request_id = response.get("id")
                if request_id is not None:
                    with self._ocr_pending_lock:
                        self._ocr_pending_requests[request_id] = response
            except:
                pass
    
    def _call_ocr_worker(self, image_data: bytes) -> Optional[str]:
        """Отправка изображения в OCR процесс"""
        if not self._ocr_started:
            self._start_ocr_worker()
        
        if not self._ocr_started:
            return None
        
        with self._ocr_pending_lock:
            request_id = self._ocr_next_request_id
            self._ocr_next_request_id += 1
            self._ocr_pending_requests[request_id] = None
        
        try:
            self._ocr_request_queue.put({
                "id": request_id,
                "image_data": image_data,
                "languages": self.config.get("ocr_languages", "rus+eng"),
                "psm": self.config.get("ocr_psm", 6),
                "timeout": self.config.get("ocr_timeout", 60)
            }, timeout=5)
        except Exception as e:
            print(f"[PII] Ошибка отправки в OCRWorker: {e}")
            return None
        
        start_time = time.time()
        timeout = self.config.get("ocr_timeout", 60)
        
        while time.time() - start_time < timeout + 5:
            with self._ocr_pending_lock:
                response = self._ocr_pending_requests.get(request_id)
                if response is not None:
                    del self._ocr_pending_requests[request_id]
                    if response.get("success"):
                        return response.get("text")
                    else:
                        return None
            time.sleep(0.01)
        
        print(f"[PII] Timeout ожидания ответа от OCRWorker (request {request_id})")
        
        with self._ocr_pending_lock:
            if request_id in self._ocr_pending_requests:
                del self._ocr_pending_requests[request_id]
        
        return None
    
    def _stop_ocr_worker(self):
        """Остановка OCR процесса"""
        if not self._ocr_started:
            return
        
        print("[PII] Остановка OCRWorker...")
        
        try:
            from classifiers.ocr_worker import stop_ocr_worker
            stop_ocr_worker(self._ocr_process, self._ocr_request_queue, self._ocr_response_queue)
        except:
            if self._ocr_process and self._ocr_process.is_alive():
                self._ocr_process.terminate()
                self._ocr_process.join(timeout=5)
                if self._ocr_process.is_alive():
                    self._ocr_process.kill()
        
        self._ocr_started = False
        self._ocr_ready = False
        self._ocr_process = None
        self._ocr_request_queue = None
        self._ocr_response_queue = None
        
        with self._ocr_pending_lock:
            self._ocr_pending_requests.clear()
        
        print(f"[PII] OCRWorker остановлен")
    
    def _trim_memory_windows(self):
        """Сброс рабочего набора памяти Windows"""
        if sys.platform == 'win32':
            try:
                kernel32 = ctypes.windll.kernel32
                process = kernel32.GetCurrentProcess()
                kernel32.SetProcessWorkingSetSize(process, -1, -1)
            except:
                pass
    
    def configure(self, config: Dict[str, Any]) -> None:
        if self.config:
            return
            
        self.config = config
        self._timeout = config.get("worker_timeout", 60.0)
        
        models_cache = config.get("models_cache")
        if models_cache:
            os.environ['HF_HOME'] = models_cache
            os.environ['HF_HUB_CACHE'] = os.path.join(models_cache, 'hub')
            os.environ['TRANSFORMERS_CACHE'] = os.path.join(models_cache, 'transformers')
            os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
            
            for d in [models_cache, os.environ['HF_HUB_CACHE'], os.environ['TRANSFORMERS_CACHE']]:
                os.makedirs(d, exist_ok=True)
            print(f"[PII] Кэш моделей: {models_cache}")
        
        temp_dir = Path(self.config.get("temp_dir", "temp"))
        
        # ИСПРАВЛЕНО: берём ocr_enabled из конфига
        ocr_enabled = self.config.get("ocr_enabled", True)
        self.extractor = DocumentExtractor(temp_dir, ocr_enabled, 1)
        
        self._start_worker()
        if self.config.get("ocr_enabled", True):
            self._start_ocr_worker()
    
    def can_classify(self, file_context: FileContext) -> bool:
        max_size = self.config.get("max_file_size_mb", 100) * 1024 * 1024
        return file_context.size_bytes <= max_size
    
    def classify(self, context: ProcessingContext) -> ClassificationResult:
        start_time = time.perf_counter()
        findings = []
        file_context = context.file_context
        text = self._get_text(file_context)
        
        if not text:
            return ClassificationResult(
                classifier_name=self.classifier_name,
                category=self.category,
                findings=[],
                processing_time=time.perf_counter() - start_time
            )
        
        if not self._quick_check(text):
            return ClassificationResult(
                classifier_name=self.classifier_name,
                category=self.category,
                findings=[],
                processing_time=time.perf_counter() - start_time
            )
        
        model_result = self._call_model_worker(text)
        
        for name, source, confidence in model_result.get("persons", []):
            if not any(f.value == name for f in findings):
                findings.append(ClassificationFinding(
                    category=DataCategory.PII,
                    subcategory="PII_PER",
                    value=name,
                    position=text.find(name) if name in text else 0,
                    context=self._get_context(text, name),
                    confidence=confidence,
                    detection_method=f"ml_{source}"
                ))
        
        for loc, source, confidence in model_result.get("locations", []):
            if not any(f.value == loc for f in findings):
                findings.append(ClassificationFinding(
                    category=DataCategory.PII,
                    subcategory="PII_LOC",
                    value=loc,
                    position=text.find(loc) if loc in text else 0,
                    context=self._get_context(text, loc),
                    confidence=confidence,
                    detection_method=f"ml_{source}"
                ))
        
        findings.extend(self._find_dates(text))
        
        self.stats["files"] += 1
        self.stats["findings"] += len(findings)
        self.stats["time"] += time.perf_counter() - start_time
        
        return ClassificationResult(
            classifier_name=self.classifier_name,
            category=self.category,
            findings=findings,
            processing_time=time.perf_counter() - start_time
        )
    
    def _get_text(self, file_context: FileContext) -> Optional[str]:
        cache_key = f"{file_context.id}_{file_context.modified_time}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        ext = Path(file_context.path).suffix.lower().lstrip('.')
        
        image_exts = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'tif', 'webp']
        if ext in image_exts and self.config.get("ocr_enabled", True):
            text = self._call_ocr_worker(file_context.content)
            if text:
                max_cache = self.config.get("cache_size", 500)
                if len(self.cache) >= max_cache:
                    items = list(self.cache.items())[:max_cache//5]
                    for k, _ in items:
                        del self.cache[k]
                    gc.collect()
                self.cache[cache_key] = text
                self.ocr_count += 1
                return text
            else:
                self.ocr_errors += 1
                return None
        
        if self.extractor:
            text, error = self.extractor.extract_text(file_context.content, ext, file_context.path)
            
            if error:
                # Сохраняем ошибку для логирования в оркестраторе
                if not hasattr(file_context, '_extract_error'):
                    file_context._extract_error = error
                print(f"[PII] Ошибка извлечения текста из {file_context.path}: {error}")
                return None
            
            if text:
                max_cache = self.config.get("cache_size", 500)
                if len(self.cache) >= max_cache:
                    items = list(self.cache.items())[:max_cache//5]
                    for k, _ in items:
                        del self.cache[k]
                    gc.collect()
                self.cache[cache_key] = text
                return text
            
            return None
        
        text_exts = ['txt', 'csv', 'log', 'json', 'md', 'ini', 'cfg', 'conf', 'yaml', 'yml', 'xml', 'html']
        if ext in text_exts:
            try:
                text = file_context.content.decode('utf-8', errors='ignore')[:5000]
                if text:
                    max_cache = self.config.get("cache_size", 500)
                    if len(self.cache) >= max_cache:
                        items = list(self.cache.items())[:max_cache//5]
                        for k, _ in items:
                            del self.cache[k]
                        gc.collect()
                    self.cache[cache_key] = text
                return text
            except:
                try:
                    text = file_context.content.decode('cp1251', errors='ignore')[:5000]
                    if text:
                        max_cache = self.config.get("cache_size", 500)
                        if len(self.cache) >= max_cache:
                            items = list(self.cache.items())[:max_cache//5]
                            for k, _ in items:
                                del self.cache[k]
                            gc.collect()
                        self.cache[cache_key] = text
                    return text
                except:
                    return None
        
        return None
    
    def _quick_check(self, text: str) -> bool:
        if not self.config.get("quick_filter_enabled", True):
            return True
        
        if len(text) < 30:
            return False
        
        has_date = re.search(r'\d{1,2}[./-]\d{1,2}[./-]\d{2,4}', text) is not None
        has_names = re.search(r'[А-Я][а-я]+\s+[А-Я][а-я]+|[A-Z][a-z]+\s+[A-Z][a-z]+', text) is not None
        
        return has_date or has_names
    
    def _find_dates(self, text: str) -> List[ClassificationFinding]:
        findings = []
        date_set = set()
        
        patterns = [
            r'\b\d{1,2}\.\d{1,2}\.\d{2,4}\b',
            r'\b\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}\b',
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{4}-\d{1,2}-\d{1,2}\b',
            r'\b\d{4}/\d{1,2}/\d{1,2}\b',
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',
        ]
        
        for pattern in patterns:
            for match in re.findall(pattern, text, re.IGNORECASE):
                date_set.add(match)
        
        for date in date_set:
            findings.append(ClassificationFinding(
                category=DataCategory.PII,
                subcategory="PII_DATE",
                value=date,
                position=text.find(date),
                context=self._get_context(text, date),
                confidence=0.95,
                detection_method="regex"
            ))
        
        return findings
    
    def _get_context(self, text: str, value: str, window: int = 50) -> str:
        pos = text.find(value)
        if pos == -1:
            return ""
        start = max(0, pos - window)
        end = min(len(text), pos + len(value) + window)
        context = text[start:end].replace('\n', ' ').replace('\r', ' ')
        if len(context) > 120:
            context = context[:117] + "..."
        return context
    
    def reset_ocr_engine(self):
        if self.config.get("ocr_enabled", True):
            print("[PII] Перезапуск OCRWorker по запросу...")
            self._stop_ocr_worker()
            time.sleep(1)
            self._start_ocr_worker()
            print(f"[PII] OCRWorker перезапущен")
    
    def reload_models(self) -> None:
        """Перезагрузка моделей и OCR процесса"""
        print(f"[PII] Перезапуск ModelWorker и OCRWorker для освобождения памяти...")
        
        cache_size_before = len(self.cache)
        if cache_size_before > 0:
            self.cache.clear()
            print(f"[PII] Очищен кэш текста: {cache_size_before} -> 0")
        
        if self.extractor and hasattr(self.extractor, '_ocr_engine'):
            if self.extractor._ocr_engine and hasattr(self.extractor._ocr_engine, '_cache'):
                cache_size = len(self.extractor._ocr_engine._cache)
                if cache_size > 0:
                    self.extractor._ocr_engine._cache.clear()
                    print(f"[PII] Очищен кэш OCR: {cache_size} -> 0")
        
        self.stats = {"files": 0, "findings": 0, "time": 0.0}
        self.ocr_count = 0
        self.ocr_errors = 0
        self.ocr_time = 0.0
        
        for _ in range(3):
            gc.collect()
        
        self._stop_worker()
        if self.config.get("ocr_enabled", True):
            self._stop_ocr_worker()
        
        for _ in range(3):
            gc.collect()
        time.sleep(2)
        
        self._start_worker()
        if self.config.get("ocr_enabled", True):
            self._start_ocr_worker()
        
        for _ in range(3):
            gc.collect()
        
        self._trim_memory_windows()
        
        try:
            import psutil
            mem = psutil.Process().memory_info().rss / 1024 / 1024
            print(f"[PII] ModelWorker и OCRWorker перезапущены, память основного процесса: {mem:.0f} MB")
        except:
            pass
        
        print(f"[PII] ModelWorker и OCRWorker перезапущены")
    
    def get_requirements(self) -> Dict[str, Any]:
        return {
            "memory_mb": 100,
            "models": ["natasha", "transformers"],
            "dependencies": ["pypdf", "pillow", "python-docx", "openpyxl"]
        }
    
    def shutdown(self):
        print("[PII] Завершение всех рабочих процессов...")
        self._stop_worker()
        self._stop_ocr_worker()
        gc.collect()
        print("[PII] Завершение выполнено")


PIIClassifier = PiiClassifier


__all__ = ['PiiClassifier', 'PIIClassifier']