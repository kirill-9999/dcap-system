#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Credentials Classifier
Поиск учётных данных (пароли, API ключи, токены)
"""

import re
import time
import math
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.base import (
    IClassifier, DataCategory, FileContext,
    ProcessingContext, ClassificationResult, ClassificationFinding
)


class CredentialsClassifier(IClassifier):
    """Классификатор учётных данных - Singleton"""
    
    _instance = None
    _lock = threading.Lock()
    
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
        self.cache = {}
        self.stats = {"files": 0, "findings": 0, "time": 0.0}
        self._initialized = True
        self.enabled = True
        self._entropy_threshold = 4.5
    
    @property
    def classifier_name(self) -> str:
        return "credentials_classifier"
    
    @property
    def category(self) -> DataCategory:
        return DataCategory.CREDENTIALS
    
    @property
    def version(self) -> str:
        return "1.0"
    
    def configure(self, config: Dict[str, Any]) -> None:
        if self.config:
            return
        self.config = config
        self._entropy_threshold = config.get("entropy_threshold", 4.5)
        self._patterns = self._get_default_patterns()
    
    def _get_default_patterns(self) -> List[Dict]:
        return [
            {"name": "API_KEY", "pattern": r'(?:api[_-]?key|apikey)[\s]*[:=][\s]*[\'"]?([A-Za-z0-9]{32,45})[\'"]?', "confidence": 0.9, "check_entropy": True},
            {"name": "AWS_ACCESS_KEY", "pattern": r'AKIA[0-9A-Z]{16}', "confidence": 0.95, "check_entropy": False},
            {"name": "AWS_SECRET_KEY", "pattern": r'(?:aws_secret_access_key|secret_key)[\s]*[:=][\s]*[\'"]?([A-Za-z0-9/+=]{40})[\'"]?', "confidence": 0.95, "check_entropy": True},
            {"name": "JWT_TOKEN", "pattern": r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', "confidence": 0.9, "check_entropy": False},
            {"name": "PASSWORD", "pattern": r'(?:password|passwd|pwd)[\s]*[:=][\s]*[\'"]?([^\s\'"]{8,})[\'"]?', "confidence": 0.7, "check_entropy": True},
            {"name": "DATABASE_URL", "pattern": r'(?:postgresql|mysql|mongodb|redis|sqlite|postgres)://[^\s\'"]+', "confidence": 0.9, "check_entropy": False},
            {"name": "SSH_PRIVATE_KEY", "pattern": r'-----BEGIN (?:RSA|DSA|EC|OPENSSH) PRIVATE KEY-----', "confidence": 0.99, "check_entropy": False},
            {"name": "GITHUB_TOKEN", "pattern": r'ghp_[A-Za-z0-9]{36}', "confidence": 0.95, "check_entropy": False},
            {"name": "GITHUB_TOKEN_OLD", "pattern": r'github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}', "confidence": 0.95, "check_entropy": False},
            {"name": "SLACK_TOKEN", "pattern": r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}', "confidence": 0.9, "check_entropy": False},
            {"name": "DISCORD_TOKEN", "pattern": r'[A-Za-z0-9]{24}\.[A-Za-z0-9]{6}\.[A-Za-z0-9]{27}', "confidence": 0.9, "check_entropy": False},
            {"name": "GENERIC_TOKEN", "pattern": r'token[\s]*[:=][\s]*[\'"]?([A-Za-z0-9_\-]{32,})[\'"]?', "confidence": 0.7, "check_entropy": True},
            {"name": "BEARER_TOKEN", "pattern": r'Bearer[\s]+([A-Za-z0-9_\-\.]{20,})', "confidence": 0.85, "check_entropy": True},
            {"name": "BASIC_AUTH", "pattern": r'Authorization:\s*Basic\s+[A-Za-z0-9+/=]+', "confidence": 0.8, "check_entropy": False},
        ]
    
    def _calculate_entropy(self, text: str) -> float:
        """Расчёт энтропии Шеннона для строки"""
        if not text:
            return 0.0
        freq = {}
        for c in text:
            freq[c] = freq.get(c, 0) + 1
        entropy = 0.0
        for count in freq.values():
            prob = count / len(text)
            entropy -= prob * math.log2(prob)
        return entropy
    
    def can_classify(self, file_context: FileContext) -> bool:
        """Проверка, может ли классификатор обработать файл"""
        ext = Path(file_context.path).suffix.lower().lstrip('.')
        # Изображения не обрабатываем
        image_exts = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp']
        if ext in image_exts:
            return False
        max_size = self.config.get("max_file_size_mb", 50) * 1024 * 1024
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
        
        # Поиск по паттернам
        for pattern_config in self._patterns:
            pattern = re.compile(pattern_config["pattern"], re.IGNORECASE | re.MULTILINE)
            for match in pattern.finditer(text):
                value = match.group(0)
                
                # Проверка энтропии если требуется
                if pattern_config.get("check_entropy", False):
                    entropy = self._calculate_entropy(value)
                    if entropy < self._entropy_threshold:
                        continue
                
                # Берём захваченную группу если есть
                matched_value = value
                if match.groups():
                    matched_value = match.group(1) if match.group(1) else value
                
                findings.append(ClassificationFinding(
                    category=DataCategory.CREDENTIALS,
                    subcategory=f"CRED_{pattern_config['name']}",
                    value=matched_value[:50] + "..." if len(matched_value) > 50 else matched_value,
                    position=match.start(),
                    context=self._get_context(text, value, 80),
                    confidence=pattern_config["confidence"],
                    detection_method="regex",
                    metadata={"pattern_name": pattern_config["name"]}
                ))
        
        # Поиск высокоэнтропийных строк (потенциальные ключи)
        high_entropy_findings = self._find_high_entropy_strings(text)
        findings.extend(high_entropy_findings)
        
        # Дедупликация по значению
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
        """Извлечение текста из файла для анализа"""
        cache_key = f"{file_context.id}_{file_context.modified_time}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        text = None
        ext = Path(file_context.path).suffix.lower().lstrip('.')
        
        # Текстовые форматы
        text_exts = ['txt', 'csv', 'log', 'json', 'py', 'js', 'java', 'cpp', 'c', 
                     'go', 'rs', 'sh', 'yaml', 'yml', 'xml', 'html', 'css', 'conf', 
                     'cfg', 'ini', 'env', 'properties']
        
        if ext in text_exts:
            try:
                text = file_context.content.decode('utf-8', errors='ignore')
                # Ограничиваем размер для анализа
                if len(text) > 100000:
                    text = text[:100000]
            except:
                try:
                    text = file_context.content.decode('cp1251', errors='ignore')[:100000]
                except:
                    pass
        
        # PDF
        elif ext == 'pdf':
            try:
                from pypdf import PdfReader
                import io
                reader = PdfReader(io.BytesIO(file_context.content))
                text = ""
                for page in reader.pages[:20]:  # Ограничиваем количество страниц
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + " "
                text = text[:50000] if text else None
            except:
                pass
        
        # DOCX
        elif ext == 'docx':
            try:
                from docx import Document
                import io
                doc = Document(io.BytesIO(file_context.content))
                text = " ".join([para.text for para in doc.paragraphs[:500]])
                text = text[:50000] if text else None
            except:
                pass
        
        if text:
            # Ограничиваем размер кэша
            if len(self.cache) > 1000:
                self.cache.pop(next(iter(self.cache)))
            self.cache[cache_key] = text
        
        return text
    
    def _find_high_entropy_strings(self, text: str) -> List[ClassificationFinding]:
        """Поиск строк с высокой энтропией (потенциальные секреты)"""
        findings = []
        
        # Паттерны для поиска потенциальных секретов
        patterns = [
            r'\b[A-Za-z0-9+/=]{20,}\b',  # Base64 подобные строки
            r'\b[A-Za-z0-9_\-]{32,}\b',  # Длинные alphanumeric строки
            r'\b[0-9a-f]{32,}\b',        # HEX строки (MD5, SHA1)
            r'\b[0-9a-f]{40,}\b',        # SHA1, SHA256
            r'\b[0-9a-f]{64,}\b',        # SHA256, SHA512
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                value = match.group(0)
                
                # Проверяем, не является ли это обычным словом
                if value.isalpha() and len(set(value)) < 5:
                    continue
                
                entropy = self._calculate_entropy(value)
                if entropy > self._entropy_threshold:
                    confidence = min(0.6 + (entropy - 4) * 0.1, 0.85)
                    findings.append(ClassificationFinding(
                        category=DataCategory.CREDENTIALS,
                        subcategory="CRED_HIGH_ENTROPY",
                        value=value[:30] + "..." if len(value) > 30 else value,
                        position=match.start(),
                        context=self._get_context(text, value, 80),
                        confidence=confidence,
                        detection_method="entropy",
                        metadata={"entropy": entropy}
                    ))
        
        return findings
    
    def _get_context(self, text: str, value: str, window: int = 60) -> str:
        """Получение контекста вокруг найденного значения"""
        pos = text.find(value)
        if pos == -1:
            return ""
        start = max(0, pos - window)
        end = min(len(text), pos + len(value) + window)
        return text[start:end].replace('\n', ' ').replace('\r', '')
    
    def reload_models(self) -> None:
        """Перезагрузка моделей (для credentials ничего не нужно)"""
        pass
    
    def get_requirements(self) -> Dict[str, Any]:
        """Требования к ресурсам"""
        return {
            "memory_mb": 256,
            "models": [],
            "dependencies": ["pypdf", "python-docx"]
        }


__all__ = ['CredentialsClassifier']