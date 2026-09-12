#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PII Classifier на основе Presidio
Использует локальные модели spaCy: ru_core_news_sm, en_core_web_sm
"""

import re
import time
import threading
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer import PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider

from core.base import (
    IClassifier, DataCategory, FileContext,
    ProcessingContext, ClassificationResult, ClassificationFinding
)
from utils.document_extractor import DocumentExtractor
from classifiers.ocr_worker import start_ocr_worker, stop_ocr_worker
from scanner.src.finding import Finding

logger = logging.getLogger(__name__)


class PiiClassifier(IClassifier):
    """PII классификатор на основе Presidio с локальными моделями"""
    
    _instance = None
    _lock = threading.Lock()
    
    # OCRWorker (отдельный процесс для Tesseract)
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
    
    def __init__(self):
        if self._initialized:
            return
        
        self.config = {}
        self.extractor = None
        self.cache = {}
        self.stats = {"files": 0, "findings": 0, "time": 0.0}
        self.ocr_count = 0
        self.ocr_errors = 0
        self.ocr_time = 0.0
        self._initialized = False
        self._timeout = 60.0
        self.enabled = True
        self._analyzer = None
        # Кастомные regex-паттерны для строчного сканирования (пустые по умолчанию)
        self.custom_patterns: List = []
    
    @property
    def classifier_name(self) -> str:
        return "pii_classifier"
    
    @property
    def category(self) -> DataCategory:
        return DataCategory.PII
    
    @property
    def version(self) -> str:
        return "4.0-presidio"
    
    def _wait_for_ocr_ready(self, timeout: float = 30.0) -> bool:
        """Ожидание готовности OCRWorker"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._ocr_ready:
                return True
            time.sleep(0.5)
        return False
    
    def _start_ocr_worker(self):
        """Запуск OCR процесса (для изоляции Tesseract)"""
        if self._ocr_started:
            return
        
        with self._lock:
            if self._ocr_started:
                return
            
            try:
                print("[PII] Запуск OCRWorker (изоляция Tesseract)...")
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
        """Отправка изображения в OCR процесс (изолированный)"""
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
    
    def _get_nlp_engine(self):
        """
        Создание NLP движка с локальными моделями.
        Использует NlpEngineProvider с конфигом.
        """
        # Конфиг для NlpEngineProvider
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": "en", "model_name": "en_core_web_sm"},
                {"lang_code": "ru", "model_name": "ru_core_news_sm"},
            ]
        }
        
        try:
            # Проверяем наличие моделей
            import spacy
            try:
                spacy.load("ru_core_news_sm")
                print("[PII] ✅ Модель ru_core_news_sm найдена")
            except Exception as e:
                print(f"[PII] ⚠️ Модель ru_core_news_sm не найдена: {e}")
                print("[PII]    Скачиваем...")
                spacy.cli.download("ru_core_news_sm")
                print("[PII] ✅ Модель ru_core_news_sm скачана")
            
            try:
                spacy.load("en_core_web_sm")
                print("[PII] ✅ Модель en_core_web_sm найдена")
            except Exception as e:
                print(f"[PII] ⚠️ Модель en_core_web_sm не найдена: {e}")
                print("[PII]    Скачиваем...")
                spacy.cli.download("en_core_web_sm")
                print("[PII] ✅ Модель en_core_web_sm скачана")
            
            # Создаём провайдер
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            
            print("[PII] ✅ NLP движок создан с моделями: en_core_web_sm, ru_core_news_sm")
            return nlp_engine
            
        except Exception as e:
            print(f"[PII] ❌ Ошибка создания NLP движка: {e}")
            raise
    
    def configure(self, config: Dict[str, Any]) -> None:
        if self._initialized:
            return
        
        self.config = config
        self._timeout = config.get("worker_timeout", 60.0)
        
        # Инициализация Presidio с локальными моделями
        try:
            # Создаём NLP движок с локальными моделями
            nlp_engine = self._get_nlp_engine()
            
            # Создаём анализатор с указанием языков
            self._analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine,
                supported_languages=["ru", "en"]
            )
            
            # Добавляем кастомные распознаватели для РФ
            self._add_custom_recognizers()
            
            print("[PII] ✅ Presidio инициализирован с локальными моделями")
            
        except Exception as e:
            print(f"[PII] ❌ Ошибка инициализации Presidio: {e}")
            print("[PII]    Установите модели вручную:")
            print("[PII]    python -m spacy download ru_core_news_sm")
            print("[PII]    python -m spacy download en_core_web_sm")
            raise
        
        # Настройка DocumentExtractor с OCR
        temp_dir = Path(self.config.get("temp_dir", "temp"))
        ocr_enabled = self.config.get("ocr_enabled", True)
        self.extractor = DocumentExtractor(temp_dir, ocr_enabled, 1)
        
        # Запускаем OCRWorker (для изоляции Tesseract)
        if self.config.get("ocr_enabled", True):
            self._start_ocr_worker()
        
        self._initialized = True

    def scan_line(self, line: str, line_num: int) -> List[Finding]:
        """
        Сканирует одну строку, возвращает список Finding с позициями.
        (День 40.2 — построчное сканирование.)
        """
        findings = []

        # Быстрый негативный фильтр (не гоняем Presidio на пустых/мусорных строках)
        if not self._quick_line_check(line):
            return []

        # 1. Presidio (если доступен)
        if self._analyzer is not None:
            try:
                results = self._analyzer.analyze(text=line, language="ru")
                min_confidence = self.config.get("min_confidence", 0.5)
                for r in results:
                    if r.score < min_confidence:
                        continue
                    match_text = line[r.start:r.end]
                    if not match_text:
                        continue
                    findings.append(Finding(
                        line_number=line_num,
                        line_text=line,
                        match_text=match_text,
                        start_pos=r.start,
                        end_pos=r.end,
                        finding_type="pii",
                        category=self._map_presidio_entity(r.entity_type),
                        severity=self._severity(r.entity_type),
                        confidence=float(r.score),
                        detector="presidio",
                    ))
            except Exception as e:
                logger.warning("Presidio failed on line %d: %s", line_num, e)
        else:
            logger.debug("Presidio analyzer not initialized, skip line %d", line_num)

        # 2. Regex-паттерны (кастомные)
        for pattern, category, severity in self.custom_patterns:
            for m in pattern.finditer(line):
                findings.append(Finding(
                    line_number=line_num,
                    line_text=line,
                    match_text=m.group(),
                    start_pos=m.start(),
                    end_pos=m.end(),
                    finding_type="pii",
                    category=category,
                    severity=severity,
                    confidence=0.85,
                    detector="regex",
                ))

        # Дедупликация внутри строки (по позиции)
        return self._deduplicate(findings)

    def _quick_line_check(self, line: str) -> bool:
        """Быстрая проверка строки на наличие PII-признаков (до Presidio)."""
        stripped = line.strip()
        if len(stripped) < 5:
            return False
        patterns = [
            r'\d{1,2}[./-]\d{1,2}[./-]\d{2,4}',
            r'[A-Za-z][A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
            r'\+?7\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',
            r'8\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',
            r'[А-Я][а-я]+\s+[А-Я][а-я]+',
            r'[A-Z][a-z]+\s+[A-Z][a-z]+',
            r'\b\d{4}\s+\d{6}\b',
            r'\b\d{3}-\d{3}-\d{3}\s+\d{2}\b',
            r'\b\d{6,12}\b',
            r'\b\d{16}\b',
        ]
        for pattern in patterns:
            if re.search(pattern, stripped):
                return True
        return False

    def _map_presidio_entity(self, entity_type: str) -> str:
        """PHONE_NUMBER → phone, EMAIL_ADDRESS → email, и т.д."""
        mapping = {
            "PHONE_NUMBER": "phone",
            "EMAIL_ADDRESS": "email",
            "PERSON": "person",
            "CREDIT_CARD": "credit_card",
            "PASSPORT": "passport",
            "RU_PASSPORT": "passport",
            "SNILS": "snils",
            "RU_SNILS": "snils",
            "INN": "inn",
            "RU_INN": "inn",
        }
        return mapping.get(entity_type, entity_type.lower())

    def _severity(self, entity_type: str) -> str:
        high = {"CREDIT_CARD", "PASSPORT", "RU_PASSPORT", "SNILS", "RU_SNILS", "INN", "RU_INN"}
        return "high" if entity_type in high else "medium"

    def _deduplicate(self, findings: List[Finding]) -> List[Finding]:
        """Убирает дубликаты (одинаковые позиции)."""
        seen = set()
        result = []
        for f in findings:
            key = (f.start_pos, f.end_pos, f.category)
            if key not in seen:
                seen.add(key)
                result.append(f)
        return result

    def _add_custom_recognizers(self):
        """Добавление кастомных распознавателей для РФ"""
        
        # 1. Телефоны РФ
        phone_patterns = [
            Pattern(
                name="phone_ru_full",
                regex=r"\+7\s*[\(\)]?\s*\d{3}\s*[\)]?\s*\d{3}\s*[-]?\s*\d{2}\s*[-]?\s*\d{2}",
                score=0.9
            ),
            Pattern(
                name="phone_ru_short",
                regex=r"8\s*[\(\)]?\s*\d{3}\s*[\)]?\s*\d{3}\s*[-]?\s*\d{2}\s*[-]?\s*\d{2}",
                score=0.85
            ),
        ]
        
        phone_recognizer = PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            name="PhoneRU",
            patterns=phone_patterns,
            supported_language="ru"
        )
        self._analyzer.registry.add_recognizer(phone_recognizer)
        
        # 2. Паспорт
        passport_patterns = [
            Pattern(
                name="passport_ru",
                regex=r"\b\d{4}\s+\d{6}\b",
                score=0.85
            )
        ]
        passport_recognizer = PatternRecognizer(
            supported_entity="PASSPORT",
            name="PassportRU",
            patterns=passport_patterns,
            supported_language="ru"
        )
        self._analyzer.registry.add_recognizer(passport_recognizer)
        
        # 3. СНИЛС
        snils_patterns = [
            Pattern(
                name="snils_ru",
                regex=r"\b\d{3}-\d{3}-\d{3}\s+\d{2}\b",
                score=0.9
            )
        ]
        snils_recognizer = PatternRecognizer(
            supported_entity="SNILS",
            name="SnilsRU",
            patterns=snils_patterns,
            supported_language="ru"
        )
        self._analyzer.registry.add_recognizer(snils_recognizer)
        
        # 4. ИНН
        inn_patterns = [
            Pattern(
                name="inn_ru",
                regex=r"\b\d{10}\b|\b\d{12}\b",
                score=0.7
            )
        ]
        inn_recognizer = PatternRecognizer(
            supported_entity="INN",
            name="InnRU",
            patterns=inn_patterns,
            supported_language="ru"
        )
        self._analyzer.registry.add_recognizer(inn_recognizer)
        
        # 5. Email
        email_patterns = [
            Pattern(
                name="email_ru",
                regex=r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                score=0.95
            )
        ]
        email_recognizer = PatternRecognizer(
            supported_entity="EMAIL_ADDRESS",
            name="EmailRU",
            patterns=email_patterns,
            supported_language="ru"
        )
        self._analyzer.registry.add_recognizer(email_recognizer)
        
        print("[PII]   Добавлены кастомные распознаватели: PhoneRU, PassportRU, SnilsRU, InnRU, EmailRU")
    
    def can_classify(self, file_context: FileContext) -> bool:
        max_size = self.config.get("max_file_size_mb", 100) * 1024 * 1024
        return file_context.size_bytes <= max_size
    
    def classify(self, context: ProcessingContext) -> ClassificationResult:
        start_time = time.perf_counter()
        findings = []
        file_context = context.file_context
        
        text = self._get_text(file_context)
        
        if not text or len(text.strip()) < 10:
            return ClassificationResult(
                classifier_name=self.classifier_name,
                category=self.category,
                findings=[],
                processing_time=time.perf_counter() - start_time
            )
        
        # Быстрый фильтр
        if not self._quick_check(text):
            return ClassificationResult(
                classifier_name=self.classifier_name,
                category=self.category,
                findings=[],
                processing_time=time.perf_counter() - start_time
            )
        
        try:
            # Анализ текста через Presidio
            results = self._analyzer.analyze(
                text=text,
                language="ru"
            )
            
            for result in results:
                entity_type = result.entity_type
                confidence = result.score
                value = text[result.start:result.end]
                position = result.start
                context_str = self._get_context(text, value)
                
                # Маппинг типов Presidio → DCAP
                category_map = {
                    "PERSON": "PII_PER",
                    "LOCATION": "PII_LOC", 
                    "DATE_TIME": "PII_DATE",
                    "EMAIL_ADDRESS": "PII_EMAIL",
                    "PHONE_NUMBER": "PII_PHONE",
                    "CREDIT_CARD": "PII_CC",
                    "IP_ADDRESS": "PII_IP",
                    "URL": "PII_URL",
                    "IBAN_CODE": "PII_IBAN",
                    "PhoneRU": "PII_PHONE",
                    "PassportRU": "PII_PASSPORT",
                    "SnilsRU": "PII_SNILS",
                    "InnRU": "PII_INN",
                    "EmailRU": "PII_EMAIL",
                }
                
                subcategory = category_map.get(entity_type, f"PII_{entity_type.upper()}")
                
                min_confidence = self.config.get("min_confidence", 0.5)
                if confidence < min_confidence:
                    continue
                
                findings.append(ClassificationFinding(
                    category=DataCategory.PII,
                    subcategory=subcategory,
                    value=value,
                    position=position,
                    context=context_str,
                    confidence=confidence,
                    detection_method="presidio",
                    metadata={"entity_type": entity_type}
                ))
                
        except Exception as e:
            print(f"[PII] Ошибка анализа: {e}")
        
        # Дедупликация
        unique_findings = {}
        for f in findings:
            key = f"{f.subcategory}:{f.value}"
            if key not in unique_findings or f.confidence > unique_findings[key].confidence:
                unique_findings[key] = f
        findings = list(unique_findings.values())
        
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
        text = None
        
        # Изображения -> OCR (через изолированный процесс)
        image_exts = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'tif', 'webp']
        if ext in image_exts and self.config.get("ocr_enabled", True):
            text = self._call_ocr_worker(file_context.content)
            if text:
                self.ocr_count += 1
                self.cache[cache_key] = text
                return text
            else:
                self.ocr_errors += 1
                return None
        
        # Документы -> через DocumentExtractor
        if self.extractor:
            text, error = self.extractor.extract_text(file_context.content, ext, file_context.path)
            if error:
                return None
            if text:
                self.cache[cache_key] = text
                return text
        
        # Простые тексты
        text_exts = ['txt', 'csv', 'log', 'json', 'md', 'ini', 'cfg', 'conf', 'yaml', 'yml', 'xml', 'html']
        if ext in text_exts:
            try:
                text = file_context.content.decode('utf-8', errors='ignore')[:100000]
                if text:
                    self.cache[cache_key] = text
                return text
            except:
                try:
                    text = file_context.content.decode('cp1251', errors='ignore')[:100000]
                    if text:
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
        
        patterns = [
            r'\d{1,2}[./-]\d{1,2}[./-]\d{2,4}',
            r'[A-Za-z][A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
            r'\+7\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',
            r'8\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',
            r'[А-Я][а-я]+\s+[А-Я][а-я]+',
            r'[A-Z][a-z]+\s+[A-Z][a-z]+',
            r'\b\d{4}\s+\d{6}\b',
            r'\b\d{3}-\d{3}-\d{3}\s+\d{2}\b',
        ]
        
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False
    
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
    
    def reload_models(self) -> None:
        """Перезагрузка (для Presidio не требуется)"""
        self.cache.clear()
        print("[PII] Кэш очищен")
    
    def shutdown(self):
        """Завершение работы"""
        print("[PII] Завершение...")
        self._stop_ocr_worker()
        print("[PII] Завершено")
    
    def get_requirements(self) -> Dict[str, Any]:
        return {
            "memory_mb": 256,
            "models": ["presidio-analyzer", "spacy"],
            "dependencies": ["presidio-analyzer", "spacy"]
        }


PIIClassifier = PiiClassifier

__all__ = ['PiiClassifier', 'PIIClassifier']