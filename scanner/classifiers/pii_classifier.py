#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PII Classifier на основе Presidio
Использует локальные модели spaCy: ru_core_news_sm, en_core_web_sm
"""

import re
import time
import bisect
import threading
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

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
        # Пул AnalyzerEngine (день 40.2+): по движку на рабочий поток,
        # чтобы Presidio-анализ файлов шёл параллельно, а не через один лок.
        self._analyzers: List[AnalyzerEngine] = []
        self._analyzer_next = 0
        self._thread_analyzers = threading.local()
        # Кастомные regex-паттерны для строчного сканирования (пустые по умолчанию)
        self.custom_patterns: List = []
        # Quick-паттерны компилируем один раз (день 42 — оптимизация)
        self._quick_line_patterns: List = [
            re.compile(p) for p in [
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
        ]
        self._quick_file_regex = re.compile(
            '|'.join(f'({p.pattern})' for p in self._quick_line_patterns)
        )
        # Presidio AnalyzerEngine не потокобезопасен — сериализуем analyze().
        # В день 40.2 заменён пулом движков (_get_analyzer), лок оставлен
        # как fallback для единичного движка (self._analyzers пуст).
        self._analyzer_lock = threading.Lock()

    def _get_analyzer(self) -> Tuple[Optional[AnalyzerEngine], Optional[threading.Lock]]:
        """Возвращает (движок Presidio, лок) для текущего потока.

        При пуле движков (self._analyzers) каждый поток получает свой движок
        по thread-local (round-robin при первом обращении) вместе с его локом —
        анализ файлов в воркерах идёт параллельно, двига мения на общий лок нет.
        Если же два потока делят один движок (пул меньше числа воркеров),
        лок движка гарантирует безопасность analyze().
        Если пул не создан (legacy) — возвращает (self._analyzer, self._analyzer_lock).
        """
        if self._analyzers:
            entry = getattr(self._thread_analyzers, "entry", None)
            if entry is None:
                with self._analyzer_lock:
                    entry = self._analyzers[self._analyzer_next % len(self._analyzers)]
                    self._analyzer_next += 1
                self._thread_analyzers.entry = entry
            return entry[0], entry[1]
        return self._analyzer, self._analyzer_lock
    
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
            # Пул движков (день 40.2+): размер — число параллельных воркеров
            # коннектора (или analyzer_pool_size), но не более 4 по умолчанию,
            # чтобы ограничить расход RAM на модели spaCy.
            pool_size = int(config.get(
                "analyzer_pool_size",
                max(1, min(config.get("max_parallel_files", 2), 4)),
            ) or 1)
            pool_size = max(1, min(pool_size, 8))

            self._analyzers = []
            for _ in range(pool_size):
                # Создаём NLP движок с локальными моделями
                nlp_engine = self._get_nlp_engine()
                # Создаём анализатор с указанием языков
                analyzer = AnalyzerEngine(
                    nlp_engine=nlp_engine,
                    supported_languages=["ru", "en"]
                )
                # Добавляем кастомные распознаватели для РФ
                self._add_custom_recognizers(analyzer)
                # (движок, лок) — движок может использоваться несколькими
                # потоками при пуле меньше числа воркеров, лок страхует.
                self._analyzers.append((analyzer, threading.Lock()))

            # совместимость: единичный движок используется как self._analyzer
            self._analyzer = self._analyzers[0][0]

            print(f"[PII] ✅ Presidio инициализирован с локальными моделями (пул: {pool_size})")
            
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

        # 1. Presidio (если доступен) — движок из пула, с локом движка
        analyzer, analyzer_lock = self._get_analyzer()
        if analyzer is not None:
            try:
                with analyzer_lock:
                    results = analyzer.analyze(text=line, language="ru")
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

    def scan_text(self, text: str) -> List[Finding]:
        """Файловый PII-анализ (день 42.5+): один вызов Presidio на весь текст.

        Номера строк находок вычисляются из offset'ов через предвычисленные
        начала строк (bisect) — построчный вызов analyze() не нужен.
        """
        findings: List[Finding] = []

        # Быстрый негативный фильтр уровня файла (объединённый regex)
        if not text or len(text.strip()) < 5:
            return findings
        if not self._quick_file_regex.search(text):
            return findings

        starts = self._line_starts(text)

        def _line_index(offset: int) -> int:
            i = bisect.bisect_right(starts, offset) - 1
            return i if 0 <= i < len(starts) else 0

        def _line_text(idx: int) -> str:
            s = starts[idx]
            e = starts[idx + 1] if idx + 1 < len(starts) else len(text)
            if e and text[e - 1] == '\n':
                e -= 1
            return text[s:e]

        # 1. Presidio — один вызов на весь текст (движок из пула текущего потока)
        analyzer, analyzer_lock = self._get_analyzer()
        if analyzer is not None:
            try:
                with analyzer_lock:
                    results = analyzer.analyze(text=text, language="ru")
                min_confidence = self.config.get("min_confidence", 0.5)
                for r in results:
                    if r.score < min_confidence:
                        continue
                    match_text = text[r.start:r.end]
                    if not match_text:
                        continue
                    idx = _line_index(r.start)
                    findings.append(Finding(
                        line_number=idx + 1,
                        line_text=_line_text(idx),
                        match_text=match_text,
                        start_pos=max(0, r.start - starts[idx]),
                        end_pos=max(0, r.end - starts[idx]),
                        finding_type="pii",
                        category=self._map_presidio_entity(r.entity_type),
                        severity=self._severity(r.entity_type),
                        confidence=float(r.score),
                        detector="presidio",
                    ))
            except Exception as e:
                logger.warning("Presidio failed on file-level scan: %s", e)
        else:
            logger.debug("Presidio analyzer not initialized, skip file-level scan")

        # 2. Regex-паттерны (кастомные) — по всему тексту, строки из offset
        for pattern, category, severity in self.custom_patterns:
            for m in pattern.finditer(text):
                idx = _line_index(m.start())
                findings.append(Finding(
                    line_number=idx + 1,
                    line_text=_line_text(idx),
                    match_text=m.group(),
                    start_pos=max(0, m.start() - starts[idx]),
                    end_pos=max(0, m.end() - starts[idx]),
                    finding_type="pii",
                    category=category,
                    severity=severity,
                    confidence=0.85,
                    detector="regex",
                ))

        # Дедупликация: ключ по номеру строки и позициям (относительно строки)
        seen = set()
        result = []
        for f in findings:
            key = (f.line_number, f.start_pos, f.end_pos, f.category)
            if key not in seen:
                seen.add(key)
                result.append(f)
        return result

    @staticmethod
    def _line_starts(text: str) -> List[int]:
        """Offset'ы начала каждой строки (0 — первая строка)."""
        starts = [0]
        for i, ch in enumerate(text):
            if ch == '\n':
                starts.append(i + 1)
        return starts

    def _quick_line_check(self, line: str) -> bool:
        """Быстрая проверка строки на наличие PII-признаков (до Presidio)."""
        stripped = line.strip()
        if len(stripped) < 5:
            return False
        for pattern in self._quick_line_patterns:
            if pattern.search(stripped):
                return True
        return False

    def file_prefilter(self, content: str) -> bool:
        """Быстрая проверка уровня файла: есть ли хоть один PII-признак во всём файле.

        Используется FilesystemConnector для пропуска файла целиком (день 42).
        Объединённый regex ищется по всему содержимому — безопасный суперсет
        построчной проверки _quick_line_check (может пропустить меньше, но не больше).
        """
        if len(content) < 5:
            return False
        return bool(self._quick_file_regex.search(content))

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

    def _add_custom_recognizers(self, analyzer: Optional[AnalyzerEngine] = None):
        """Добавление кастомных распознавателей для РФ"""
        analyzer = analyzer or self._analyzer
        
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
        analyzer.registry.add_recognizer(phone_recognizer)
        
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
        analyzer.registry.add_recognizer(passport_recognizer)
        
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
        analyzer.registry.add_recognizer(snils_recognizer)
        
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
        analyzer.registry.add_recognizer(inn_recognizer)
        
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
        analyzer.registry.add_recognizer(email_recognizer)
        
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