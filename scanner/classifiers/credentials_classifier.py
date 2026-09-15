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
from scanner.src.finding import Finding


# ===========================================================================
# КАТЕГОРИИ ПАТТЕРНОВ (день 40.2) — для построчного сканирования и Manager
# ===========================================================================

CATEGORY_MAP = {
    "API_KEY": "api_key",
    "AWS_ACCESS_KEY": "aws_key",
    "AWS_SECRET_KEY": "aws_key",
    "JWT_TOKEN": "jwt_token",
    "PASSWORD": "password",
    "DATABASE_URL": "database_url",
    "SSH_PRIVATE_KEY": "ssh_key",
    "GITHUB_TOKEN": "github_token",
    "GITHUB_TOKEN_OLD": "github_token",
    "SLACK_TOKEN": "slack_token",
    "DISCORD_TOKEN": "discord_token",
    "GENERIC_TOKEN": "token",
    "GENERIC_SECRET": "token",
    "BEARER_TOKEN": "token",
    "BASIC_AUTH": "basic_auth",
}


# ===========================================================================
# FP-ФИЛЬТРЫ (день 34.5) — подавление ложных срабатываний
# ===========================================================================

# Значения, похожие на плейсхолдеры/заглушки
PLACEHOLDER_PATTERNS = [
    r'your_[a-z_]+',           # your_key, your_password
    r'example_[a-z_]+',        # example_key
    r'changeme',               # changeme
    r'<[A-Z_]+>',              # <PASSWORD>
    r'{{[A-Z_]+}}',            # {{PASSWORD}}
    r'xxx+',                   # xxx, xxxx
    r'[0-9x]{8,}',             # 12345678, xxxxxxxx
    r'NNN[_-]?[A-Z]+',         # NNN_KEY
    r'password[0-9]{1,2}',     # password1, password12
    r'admin[0-9]{1,2}',        # admin1
    r'test[_-]?[a-z0-9]+',     # test_key, test-123
    r'sample[_-]?[a-z0-9]+',   # sample_key
    r'demo[_-]?[a-z0-9]+',     # demo_key
    r'example\.com',           # example.com
    r'changeme\.com',          # changeme.com
]

# Строки-комментарии (маркеры начала строки)
COMMENT_PATTERNS = [
    r'^\s*#',                  # shell/python
    r'^\s*//',                 # C/JS/Go
    r'^\s*;',                  # INI
    r'^\s*\*',                 # многострочные
    r'^\s*--',                 # SQL
    r'^\s*<!--',               # HTML
]

# Дамп-значения (только цифры / короткий hex / один регистр).
# Аккуратно: AWS/GH-ключи (AKIA..., ghp_...) — верхний регистр+цифры,
# поэтому не перекрываем их избыточными паттернами ^[A-Z0-9]{16,}$.
DUMP_PATTERNS = [
    r'^\d+$',                  # только цифры
    r'^[0-9x]+$',              # цифры/иксы
    r'^[0-9A-Fa-f]{8,16}$',    # короткий hex (длинный hex — похож на hash-секрет)
    r'^[A-Z]{16,}$',           # только заглавные буквы
    r'^[a-z]{16,}$',           # только строчные буквы
    r'^([0-9]+[-_.]){2,}[0-9]+$',  # версии вида 1.2.3
]

# Префиксы реальных токенов — не отбрасывать даже если похожи на дамп
SIGNATURE_PREFIXES = (
    'AKIA', 'ASIA', 'ghp_', 'ghs_', 'gho_', 'xox', 'eyJ',
    '-----BEGIN', 'sk-', 'pk-live-', 'pk-test-',
)

# Имена файлов, которые считаются credential-файлами по имени
CRED_FILE_NAMES = {
    'id_rsa': 'ssh_private_key',
    'id_dsa': 'ssh_private_key',
    'id_ecdsa': 'ssh_private_key',
    'id_ed25519': 'ssh_private_key',
    '.pgpass': 'postgres_password',
    '.netrc': 'netrc_credentials',
    '_netrc': 'netrc_credentials',
    'kubeconfig': 'kubeconfig',
    'admin.conf': 'kubeconfig',
    'jaas.conf': 'jaas_credentials',
    'kafka_client_jaas.conf': 'jaas_credentials',
    'secrets': 'secrets_file',
    'secrets.json': 'secrets_file',
    'secrets.yaml': 'secrets_file',
    'secrets.yml': 'secrets_file',
    '.env': 'env_file',
    '.htpasswd': 'htpasswd_credentials',
    'passwd': 'passwd_file',
    'shadow': 'shadow_file',
}


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
        self._min_length = 8
        self._strict_filter = True
        self._confidence_threshold = 0.7
        self._no_generic = False
        self._require_mixed = False
        self._patterns = self._get_default_patterns()
        self._compile_all()
    
    @property
    def classifier_name(self) -> str:
        return "credentials_classifier"
    
    @property
    def category(self) -> DataCategory:
        return DataCategory.CREDENTIALS
    
    @property
    def version(self) -> str:
        return "1.1"
    
    def configure(self, config: Dict[str, Any]) -> None:
        if self.config:
            return
        self.config = config
        self._entropy_threshold = config.get("entropy_threshold", 4.5)
        self._min_length = config.get("min_length", 8)
        self._strict_filter = config.get("strict_filter", True)
        self._confidence_threshold = config.get("confidence_threshold", 0.7)
        self._no_generic = config.get("no_generic", False)
        self._require_mixed = config.get("require_mixed", False)
        self._patterns = self._get_default_patterns()
        self._compile_all()
    
    def _get_default_patterns(self) -> List[Dict]:
        return [
            {"name": "API_KEY", "pattern": r'(?:api[_-]?key|apikey)[\s]*[:=][\s]*[\'"]?([A-Za-z0-9]{32,45})[\'"]?', "confidence": 0.9, "check_entropy": True},
            {"name": "AWS_ACCESS_KEY", "pattern": r'AKIA[0-9A-Z]{16}', "confidence": 0.95, "check_entropy": False},
            {"name": "AWS_SECRET_KEY", "pattern": r'(?:aws_secret_access_key|secret_key)[\s]*[:=][\s]*[\'"]?([A-Za-z0-9/+=]{40})[\'"]?', "confidence": 0.95, "check_entropy": True},
            {"name": "JWT_TOKEN", "pattern": r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', "confidence": 0.9, "check_entropy": False},
            {"name": "PASSWORD", "pattern": r'(?:password|passwd|pwd)[\s]*[:=][\s]*[\'"]?([^\s\'"]{8,})[\'"]?', "confidence": 0.7, "check_entropy": True},
            {"name": "DATABASE_URL", "pattern": r'(?:postgresql|mysql|mongodb|redis|sqlite|postgres|jdbc)://[^\s\'"]+', "confidence": 0.9, "check_entropy": False},
            {"name": "SSH_PRIVATE_KEY", "pattern": r'-----BEGIN (?:RSA|DSA|EC|OPENSSH) PRIVATE KEY-----', "confidence": 0.99, "check_entropy": False},
            {"name": "GITHUB_TOKEN", "pattern": r'ghp_[A-Za-z0-9]{36}', "confidence": 0.95, "check_entropy": False},
            {"name": "GITHUB_TOKEN_OLD", "pattern": r'github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}', "confidence": 0.95, "check_entropy": False},
            {"name": "SLACK_TOKEN", "pattern": r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}', "confidence": 0.9, "check_entropy": False},
            {"name": "DISCORD_TOKEN", "pattern": r'[A-Za-z0-9]{24}\.[A-Za-z0-9]{6}\.[A-Za-z0-9]{27}', "confidence": 0.9, "check_entropy": False},
            {"name": "GENERIC_TOKEN", "pattern": r'token[\s]*[:=][\s]*[\'"]?([A-Za-z0-9_\-]{32,})[\'"]?', "confidence": 0.7, "check_entropy": True},
            {"name": "GENERIC_SECRET", "pattern": r'(?:secret|api_secret|client_secret)[\s]*[:=][\s]*[\'"]?([A-Za-z0-9_\-]{16,})[\'"]?', "confidence": 0.6, "check_entropy": True},
            {"name": "BEARER_TOKEN", "pattern": r'Bearer[\s]+([A-Za-z0-9_\-\.]{20,})', "confidence": 0.85, "check_entropy": True},
            {"name": "BASIC_AUTH", "pattern": r'Authorization:\s*Basic\s+[A-Za-z0-9+/=]+', "confidence": 0.8, "check_entropy": False},
        ]
    
    def _compile_all(self) -> None:
        """Компиляция всех regex один раз (день 42 — оптимизация).

        - prefilter_regex — единый prefilter по всем паттернам (для быстрой
          проверки всего файла целиком через file_prefilter).
        - compiled_patterns — скомпилированные regex всех паттернов (используются
          в scan_line/classify без re.compile в горячем цикле).
        - _entropy_patterns — скомпилированные токены для энтропийной проверки.
        """
        all_patterns = [p["pattern"] for p in self._patterns]
        combined = '|'.join(f'({p})' for p in all_patterns)
        self.prefilter_regex = re.compile(combined, re.IGNORECASE | re.MULTILINE)
        self.compiled_patterns = []
        for p in self._patterns:
            item = dict(p)
            item["compiled"] = re.compile(p["pattern"], re.IGNORECASE | re.MULTILINE)
            self.compiled_patterns.append(item)
        self._entropy_patterns = [
            re.compile(p) for p in [
                r'\b[A-Za-z0-9+/=]{20,}\b',
                r'\b[A-Za-z0-9_\-]{32,}\b',
                r'\b[0-9a-f]{32,}\b',
                r'\b[0-9a-f]{40,}\b',
                r'\b[0-9a-f]{64,}\b',
            ]
        ]
    
    def _compile_prefilter(self) -> None:
        """Компиляция единого regex-префильтра по всем паттернам"""
        all_patterns = [p["pattern"] for p in self._patterns]
        combined = '|'.join(f'({p})' for p in all_patterns)
        self.prefilter_regex = re.compile(combined, re.IGNORECASE | re.MULTILINE)
    
    def prefilter(self, content: str) -> bool:
        """Быстрая проверка: есть ли хоть один паттерн в контенте"""
        return bool(self.prefilter_regex.search(content))

    def file_prefilter(self, content: str) -> bool:
        """Быстрая проверка уровня файла: есть ли хоть один паттерн во всём файле.

        Используется FilesystemConnector для пропуска файла целиком, если ни один
        классификатор не видит быстрых признаков (день 42 — оптимизация).
        """
        return bool(self.prefilter_regex.search(content))

    # =====================================================================
    # Построчное сканирование (день 40.2)
    # =====================================================================

    def scan_line(self, line: str, line_num: int) -> List[Finding]:
        """
        Сканирует одну строку, возвращает список Finding с позициями.
        Применяет те же FP-фильтры и энтропийные проверки, что и classify().
        """
        findings: List[Finding] = []

        # Префильтр: если ни один паттерн не встречается в строке — пропускаем
        if not self.prefilter(line):
            return findings

        # Поиск по паттернам (precompiled, день 42)
        for pattern_config in self.compiled_patterns:
            # no_generic: пропускаем общие правила
            if self._no_generic and pattern_config["name"] in ("GENERIC_TOKEN", "GENERIC_SECRET"):
                continue
            # confidence_threshold: пропускаем низкодоверенные правила
            if pattern_config["confidence"] < self._confidence_threshold:
                continue

            pattern = pattern_config["compiled"]
            for match in pattern.finditer(line):
                value = match.group(0)

                # Проверка энтропии если требуется
                if pattern_config.get("check_entropy", False):
                    entropy = self._calculate_entropy(value)
                    if entropy < self._entropy_threshold:
                        continue

                # Берём захваченную группу если есть (позиции — по секрету)
                matched_value = value
                match_start, match_end = match.start(), match.end()
                if match.groups() and match.group(1):
                    matched_value = match.group(1)
                    match_start, match_end = match.span(1)

                # Применение FP-фильтров
                if not self._apply_filters(matched_value, line):
                    continue

                findings.append(Finding(
                    line_number=line_num,
                    line_text=line,
                    match_text=matched_value,
                    start_pos=match_start,
                    end_pos=match_end,
                    finding_type="credentials",
                    category=CATEGORY_MAP.get(pattern_config["name"], pattern_config["name"].lower()),
                    severity="high" if pattern_config["confidence"] >= 0.9 else "medium",
                    confidence=pattern_config["confidence"],
                    detector="regex",
                ))

        # Высокоэнтропийные строки (компактные токены)
        findings.extend(self._find_high_entropy_in_line(line, line_num))

        # Дедупликация по позиции/категории (сохраняем максимальную уверенность)
        unique: Dict = {}
        for f in findings:
            key = (f.start_pos, f.end_pos, f.category)
            if key not in unique or f.confidence > unique[key].confidence:
                unique[key] = f
        return list(unique.values())

    def _find_high_entropy_in_line(self, line: str, line_num: int) -> List[Finding]:
        """Поиск компактных высокоэнтропийных токенов в одной строке."""
        findings = []
        stripped = line.strip()
        # Не рассматриваем строки с пробелами (это текст, не токен) и короткие
        if not stripped or len(stripped) < 20 or any(c.isspace() for c in stripped):
            return findings

        patterns = self._entropy_patterns

        for pattern in patterns:
            for match in pattern.finditer(stripped):
                value = match.group(0)
                if value.isalpha() and len(set(value)) < 5:
                    continue
                entropy = self._calculate_entropy(value)
                if entropy > self._entropy_threshold:
                    confidence = min(0.6 + (entropy - 4) * 0.1, 0.85)
                    findings.append(Finding(
                        line_number=line_num,
                        line_text=line,
                        match_text=value,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        finding_type="credentials",
                        category="high_entropy",
                        severity="medium",
                        confidence=confidence,
                        detector="entropy",
                    ))
        return findings
    
    # =====================================================================
    # FP-фильтры
    # =====================================================================
    
    def _is_placeholder(self, value: str) -> bool:
        """Проверка: является ли значение плейсхолдером"""
        for pattern in PLACEHOLDER_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    @staticmethod
    def _is_comment_line(line: str) -> bool:
        """Проверка: является ли строка комментарием"""
        for pattern in COMMENT_PATTERNS:
            if re.match(pattern, line):
                return True
        return False
    
    def _is_dump_value(self, value: str) -> bool:
        """Проверка: является ли значение дампом (только цифры/hex и т.п.)"""
        if value.startswith(SIGNATURE_PREFIXES):
            return False
        for pattern in DUMP_PATTERNS:
            if re.fullmatch(pattern, value):
                return True
        return False
    
    @staticmethod
    def _has_mixed_case(value: str) -> bool:
        """Проверка: содержит ли значение >=3 из 4 категорий символов"""
        has_lower = any(c.islower() for c in value)
        has_upper = any(c.isupper() for c in value)
        has_digit = any(c.isdigit() for c in value)
        has_special = any(not c.isalnum() for c in value)
        return sum([has_lower, has_upper, has_digit, has_special]) >= 3
    
    def _apply_filters(self, value: str, line: str) -> bool:
        """Применение всех FP-фильтров к найденному значению.
        
        Returns:
            True — значение проходит фильтры (оставляем), False — отбрасываем.
        """
        # 1. Минимальная длина
        if len(value) < self._min_length:
            return False
        
        # 2. Плейсхолдеры
        if self._is_placeholder(value):
            return False
        
        # 3. Дампы (строгий фильтр для коротких значений)
        if self._is_dump_value(value):
            return False
        
        # 4. Комментарии
        if self._is_comment_line(line):
            return False
        
        # 5. Смешанные символы (если включено)
        if self._require_mixed and not self._has_mixed_case(value):
            return False
        
        return True
    
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
        
        # Детекция по имени файла (независимо от содержимого)
        filename_finding = self._credential_file_finding(file_context)
        if filename_finding:
            findings.append(filename_finding)
        
        if not text:
            return ClassificationResult(
                classifier_name=self.classifier_name,
                category=self.category,
                findings=findings,
                processing_time=time.perf_counter() - start_time
            )
        
        # Префильтр: если ни один паттерн не встречается в тексте — пропускаем
        # детальный анализ (но сохраняем находку по имени файла, если была)
        if not self.prefilter(text):
            self.stats["files"] += 1
            self.stats["findings"] += len(findings)
            self.stats["time"] += time.perf_counter() - start_time
            return ClassificationResult(
                classifier_name=self.classifier_name,
                category=self.category,
                findings=findings,
                processing_time=time.perf_counter() - start_time
            )
        
        # Поиск по паттернам (precompiled, день 42)
        for pattern_config in self.compiled_patterns:
            # no_generic: пропускаем общие правила
            if self._no_generic and pattern_config["name"] in ("GENERIC_TOKEN", "GENERIC_SECRET"):
                continue
            # confidence_threshold: пропускаем низкодоверенные правила
            if pattern_config["confidence"] < self._confidence_threshold:
                continue
            
            pattern = pattern_config["compiled"]
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
                
                # Строка, в которой найдено значение (для фильтра комментариев)
                line = self._line_at(text, match.start())
                
                # Применение FP-фильтров
                if not self._apply_filters(matched_value, line):
                    continue
                
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
    
    def _credential_file_finding(self, file_context: FileContext) -> Optional[ClassificationFinding]:
        """Детекция credential-файла по имени файла"""
        name = Path(file_context.path).name.lower()
        for cred_name, cred_type in CRED_FILE_NAMES.items():
            if name == cred_name:
                return ClassificationFinding(
                    category=DataCategory.CREDENTIALS,
                    subcategory=f"CRED_{cred_type.upper()}",
                    value=f"<file: {Path(file_context.path).name}>",
                    position=0,
                    context=f"Файл с учётными данными по имени: {cred_type}",
                    confidence=0.9,
                    detection_method="filename",
                    metadata={"credential_name": cred_name, "credential_type": cred_type}
                )
        return None
    
    @staticmethod
    def _line_at(text: str, char_offset: int) -> str:
        """Возвращает строку текста, содержащую offset (для фильтра комментариев)"""
        start = text.rfind('\n', 0, char_offset) + 1
        end = text.find('\n', char_offset)
        if end == -1:
            end = len(text)
        return text[start:end]
    
    def _get_text(self, file_context: FileContext) -> Optional[str]:
        """Извлечение текста из файла для анализа"""
        cache_key = f"{file_context.id}_{file_context.modified_time}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        text = None
        ext = Path(file_context.path).suffix.lower().lstrip('.')
        
        # Текстовые форматы (расширено день 34.5: pem/key/crt/env/office)
        text_exts = [
            'txt', 'csv', 'log', 'json', 'py', 'js', 'java', 'cpp', 'c',
            'go', 'rs', 'sh', 'yaml', 'yml', 'xml', 'html', 'css', 'conf',
            'cfg', 'ini', 'env', 'properties',
            'pem', 'key', 'crt', 'csr', 'cert', 'p12', 'pfx', 'jks',
            'toml', 'ts', 'tsx', 'jsx', 'bash', 'zsh', 'ps1', 'cmd', 'bat',
            'sql', 'php', 'rb', 'pl', 'lua', 'r', 'swift', 'kt', 'md', 'rst',
            'dockerfile', 'makefile', 'tf', 'hcl',
        ]
        
        if ext in text_exts:
            try:
                text = self._decode_text(file_context.content)
            except:
                text = None
        
        # Файлы с нестандартными именами (.env, kubeconfig, .netrc и т.п.)
        # анализируются по имени даже без привычного расширения
        elif Path(file_context.path).name.lower() in CRED_FILE_NAMES:
            try:
                text = self._decode_text(file_context.content)
            except:
                text = None
        
        # PDF / Office-документы
        elif ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx']:
            text = self._extract_document(file_context, ext)
        
        if text:
            # Ограничиваем размер текста для анализа
            if len(text) > 200000:
                text = text[:200000]
            # Ограничиваем размер кэша
            if len(self.cache) > 1000:
                self.cache.pop(next(iter(self.cache)))
            self.cache[cache_key] = text
        
        return text
    
    def _decode_text(self, content: bytes) -> Optional[str]:
        """Декодирование текста с перебором кодировок"""
        for encoding in ('utf-8', 'cp1251'):
            try:
                return content.decode(encoding, errors='ignore')
            except:
                continue
        try:
            return content.decode('utf-8', errors='ignore')
        except:
            return None
    
    def _extract_document(self, file_context: FileContext, ext: str) -> Optional[str]:
        """Извлечение текста из документов (PDF/DOC/DOCX/XLS/XLSX)"""
        try:
            from utils.document_extractor import DocumentExtractor
            import tempfile
            
            extractor = DocumentExtractor(
                temp_dir=Path(tempfile.gettempdir()),
                ocr_enabled=False
            )
            result, error = extractor.extract_text(file_context.content, ext, Path(file_context.path).name)
            return result
        except Exception:
            return None
    
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
            "dependencies": ["pypdf", "python-docx", "xlrd", "openpyxl"]
        }


__all__ = ['CredentialsClassifier']