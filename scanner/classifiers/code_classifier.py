#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Code Classifier
Обнаружение программного кода, исполняемых файлов, скриптов и инсталляторов
"""

import re
import time
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from scanner.src.finding import Finding

from core.base import (
    IClassifier, DataCategory, FileContext,
    ProcessingContext, ClassificationResult, ClassificationFinding
)


class CodeClassifier(IClassifier):
    """
    Классификатор для обнаружения:
    - Исходного кода (Python, Java, C++, C#, JavaScript, Go, Rust, PHP, Ruby, Swift, Kotlin)
    - Исполняемых файлов (PE/ELF/Mach-O)
    - Скриптов (PowerShell, Bash, Batch, VBS, Perl, Lua, R)
    - Инсталляторов (MSI, EXE installers, DEB, RPM, PKG, DMG)
    - Библиотек (DLL, SO, DYLIB, JAR, AAR, Framework)
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, *args, **kwargs):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self.config = {}
        self.cache = {}
        self.stats = {"files": 0, "findings": 0, "time": 0.0}
        self._initialized = True
        self.enabled = True

    def scan_line(self, line: str, line_num: int) -> List[Finding]:
        """
        Сканирует одну строку (день 40.2).

        Code-классификатор работает на уровне файлов (определение типа кода),
        построчное детектирование секретов для него не используется.
        """
        return []
    
    @property
    def classifier_name(self) -> str:
        return "code_classifier"
    
    @property
    def category(self) -> DataCategory:
        return DataCategory.CODE_SECRETS
    
    @property
    def version(self) -> str:
        return "1.0"
    
    def configure(self, config: Dict[str, Any]) -> None:
        if self.config:
            return
        self.config = config
        self._init_patterns()
        self._init_magic_signatures()
    
    def _init_patterns(self):
        """Инициализация паттернов для обнаружения"""
        self.code_patterns = {
            "PYTHON": {
                "extensions": [".py", ".pyw", ".pyx", ".pyi"],
                "patterns": [
                    r'^\s*(?:import|from)\s+\w+',
                    r'^\s*def\s+\w+\s*\(',
                    r'^\s*class\s+\w+\s*[:\(]',
                    r'^\s*if\s+__name__\s*==\s*[\'"]__main__[\'"]',
                    r'@(?:staticmethod|classmethod|property)',
                ],
                "confidence": 0.95
            },
            "JAVA": {
                "extensions": [".java", ".class", ".jar"],
                "patterns": [
                    r'^\s*(?:public|private|protected)\s+(?:class|interface|enum)\s+\w+',
                    r'^\s*package\s+[\w.]+;',
                    r'^\s*import\s+[\w.]+;',
                    r'public\s+static\s+void\s+main\s*\(',
                    r'@(?:Override|Deprecated|SuppressWarnings)',
                ],
                "confidence": 0.95
            },
            "CSHARP": {
                "extensions": [".cs"],
                "patterns": [
                    r'^\s*(?:public|private|protected|internal)\s+(?:class|interface|struct|enum)\s+\w+',
                    r'^\s*using\s+[\w.]+;',
                    r'^\s*namespace\s+[\w.]+',
                    r'^\s*static\s+void\s+Main\s*\(',
                    r'^\s*#(?:region|endregion|if|endif)',
                ],
                "confidence": 0.9
            },
            "CPP": {
                "extensions": [".cpp", ".cxx", ".cc", ".c", ".h", ".hpp", ".hxx"],
                "patterns": [
                    r'^\s*#(?:include|define|ifdef|ifndef|endif|pragma)',
                    r'^\s*(?:class|struct|enum)\s+\w+\s*[:{]',
                    r'^\s*(?:int|void|char|float|double|bool)\s+\w+\s*\(',
                    r'std::\w+',
                    r'namespace\s+\w+\s*{',
                ],
                "confidence": 0.9
            },
            "JAVASCRIPT": {
                "extensions": [".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"],
                "patterns": [
                    r'^\s*(?:const|let|var)\s+\w+\s*=',
                    r'^\s*function\s+\w+\s*\(',
                    r'^\s*class\s+\w+\s*{',
                    r'^\s*import\s+.*\s+from\s+[\'"]',
                    r'^\s*export\s+(?:default|const|function|class)',
                    r'=>\s*{',
                ],
                "confidence": 0.9
            },
            "GO": {
                "extensions": [".go"],
                "patterns": [
                    r'^\s*package\s+\w+',
                    r'^\s*import\s+[\("]',
                    r'^\s*func\s+\w+\s*\(',
                    r'^\s*type\s+\w+\s+(?:struct|interface)',
                    r'^\s*var\s+\w+\s+\w+',
                    r'go\s+func\(',
                ],
                "confidence": 0.9
            },
            "RUST": {
                "extensions": [".rs"],
                "patterns": [
                    r'^\s*(?:fn|pub\s+fn)\s+\w+\s*\(',
                    r'^\s*let\s+(?:mut\s+)?\w+\s*=',
                    r'^\s*impl\s+\w+\s+for\s+\w+',
                    r'^\s*#\[derive\(.*\)\]',
                    r'^\s*use\s+[\w:]+::[\w:]+;?',
                    r'^\s*struct\s+\w+\s*{',
                    r'^\s*enum\s+\w+\s*{',
                ],
                "confidence": 0.9
            },
            "PHP": {
                "extensions": [".php", ".phtml", ".php3", ".php4", ".php5", ".php7"],
                "patterns": [
                    r'<\?php',
                    r'^\s*(?:function|class)\s+\w+\s*[\({]',
                    r'\$\w+\s*=',
                    r'echo\s+[\'"].*[\'"]',
                    r'require(?:_once)?\s*\(?[\'"]',
                    r'namespace\s+[\w\\]+;',
                ],
                "confidence": 0.9
            },
            "RUBY": {
                "extensions": [".rb", ".rake", ".gemspec"],
                "patterns": [
                    r'^\s*def\s+\w+\s*[\(\)]',
                    r'^\s*class\s+\w+\s*(?:<|$)',
                    r'^\s*module\s+\w+',
                    r'^\s*require\s+[\'"]',
                    r'^\s*attr_(?:accessor|reader|writer)',
                    r'^\s*#!.*ruby',
                ],
                "confidence": 0.9
            },
            "SWIFT": {
                "extensions": [".swift"],
                "patterns": [
                    r'^\s*(?:import|class|struct|enum|protocol)\s+\w+',
                    r'^\s*func\s+\w+\s*\(',
                    r'^\s*let\s+\w+\s*=',
                    r'^\s*var\s+\w+\s*[:=]',
                    r'^\s*guard\s+let\s+\w+',
                    r'^\s*@(?:IBOutlet|IBAction|objc)',
                ],
                "confidence": 0.9
            },
            "KOTLIN": {
                "extensions": [".kt", ".kts"],
                "patterns": [
                    r'^\s*(?:fun|class|interface|object|data\s+class)\s+\w+',
                    r'^\s*val\s+\w+\s*[:=]',
                    r'^\s*var\s+\w+\s*[:=]',
                    r'^\s*package\s+[\w.]+',
                    r'^\s*import\s+[\w.]+',
                    r'\?\.\s*\w+',
                ],
                "confidence": 0.9
            }
        }
        
        self.script_patterns = {
            "POWERSHELL": {
                "extensions": [".ps1", ".psm1", ".psd1", ".ps1xml"],
                "patterns": [
                    r'^\s*(?:function|cmdletbinding)\s+',
                    r'^\s*param\s*\(',
                    r'\$[A-Za-z0-9_]+',
                    r'Write-(?:Host|Output|Error|Warning|Debug)',
                    r'Get-\w+|Set-\w+|New-\w+|Remove-\w+',
                    r'#Requires\s+-\w+',
                ],
                "confidence": 0.85
            },
            "BASH": {
                "extensions": [".sh", ".bash", ".zsh", ".fish"],
                "patterns": [
                    r'^#!.*(?:ba|z|fi)?sh',
                    r'^\s*(?:if|then|else|elif|fi|for|while|until|do|done|case|esac)\b',
                    r'\$\{?[A-Za-z0-9_]+\}?',
                    r'^\s*function\s+\w+\s*{',
                    r'\$\(\(.*\)\)|\$\(.*\)',
                    r'^\s*export\s+\w+=',
                ],
                "confidence": 0.85
            },
            "BATCH": {
                "extensions": [".bat", ".cmd"],
                "patterns": [
                    r'^@echo\s+(?:off|on)',
                    r'^\s*(?:SET|ECHO|REM|GOTO|CALL|PAUSE|EXIT)\b',
                    r'%[A-Za-z0-9_]+%',
                    r'if\s+(?:not\s+)?errorlevel',
                    r':[A-Za-z0-9_]+',
                ],
                "confidence": 0.85
            },
            "VBSCRIPT": {
                "extensions": [".vbs", ".vba", ".vbe"],
                "patterns": [
                    r'^\s*(?:Dim|Option Explicit|Sub|Function|Class)\b',
                    r'^\s*CreateObject\s*\(',
                    r'^\s*MsgBox\s+',
                    r'^\s*WScript\.(?:Echo|Sleep|Quit)',
                    r'^\s*On\s+Error\s+Resume\s+Next',
                ],
                "confidence": 0.85
            },
            "PERL": {
                "extensions": [".pl", ".pm", ".t"],
                "patterns": [
                    r'^#!.*perl',
                    r'^\s*(?:use|require)\s+[\w:]+;?',
                    r'^\s*sub\s+\w+\s*{',
                    r'^\s*my\s+\$\w+\s*=',
                    r'^\$[A-Za-z0-9_]+\s*=\s*~',
                    r'@[A-Za-z0-9_]+',
                ],
                "confidence": 0.85
            },
            "LUA": {
                "extensions": [".lua"],
                "patterns": [
                    r'^\s*function\s+\w+\s*\(',
                    r'^\s*local\s+\w+\s*=',
                    r'^\s*for\s+\w+\s*=\s*\d+\s*,\s*\d+\s+do',
                    r'^\s*if\s+.*\s+then',
                    r'^\s*print\s*\(',
                ],
                "confidence": 0.85
            },
            "R": {
                "extensions": [".r", ".R", ".rdata"],
                "patterns": [
                    r'^\s*(?:library|require)\s*\(',
                    r'^\s*function\s*\(',
                    r'<-\s*function',
                    r'^\s*if\s*\(',
                    r'^\s*for\s*\(',
                    r'ggplot\s*\(',
                ],
                "confidence": 0.85
            }
        }
        
        self.installer_patterns = {
            "EXE_INSTALLER": {
                "extensions": [".exe"],
                "patterns": [
                    r'install',
                    r'setup',
                    r'uninstall',
                    r'Update\.exe',
                ],
                "confidence": 0.8
            }
        }
    
    def _init_magic_signatures(self):
        """Инициализация magic для определения типа файла"""
        pass
    
    def can_classify(self, file_context: FileContext) -> bool:
        max_size = self.config.get("max_file_size_mb", 50) * 1024 * 1024
        return file_context.size_bytes <= max_size
    
    def classify(self, context: ProcessingContext) -> ClassificationResult:
        start_time = time.perf_counter()
        findings = []
        file_context = context.file_context
        
        text = self._get_text(file_context)
        file_ext = Path(file_context.path).suffix.lower().lstrip('.')
        
        findings.extend(self._classify_by_extension(file_ext, text))
        
        if text:
            findings.extend(self._classify_by_patterns(text, file_ext))
        
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
    
    def _classify_by_extension(self, ext: str, text: str) -> List[ClassificationFinding]:
        findings = []
        
        for lang, config in self.code_patterns.items():
            if ext in config.get("extensions", []):
                confidence = config.get("confidence", 0.85)
                findings.append(ClassificationFinding(
                    category=self.category,
                    subcategory=f"CODE_{lang}",
                    value=f"Исходный код на {lang}",
                    position=0,
                    context=f"Файл с расширением .{ext}",
                    confidence=confidence,
                    detection_method="extension",
                    metadata={"language": lang, "extension": ext}
                ))
                break
        
        if not findings:
            for script, config in self.script_patterns.items():
                if ext in config.get("extensions", []):
                    confidence = config.get("confidence", 0.85)
                    findings.append(ClassificationFinding(
                        category=self.category,
                        subcategory=f"SCRIPT_{script}",
                        value=f"Скрипт {script}",
                        position=0,
                        context=f"Файл с расширением .{ext}",
                        confidence=confidence,
                        detection_method="extension",
                        metadata={"script_type": script, "extension": ext}
                    ))
                    break
        
        if not findings:
            for inst_type, config in self.installer_patterns.items():
                if ext in config.get("extensions", []):
                    confidence = config.get("confidence", 0.85)
                    findings.append(ClassificationFinding(
                        category=self.category,
                        subcategory=f"INSTALLER_{inst_type}",
                        value=f"Инсталлятор ({inst_type})",
                        position=0,
                        context=f"Файл с расширением .{ext}",
                        confidence=confidence,
                        detection_method="extension",
                        metadata={"installer_type": inst_type, "extension": ext}
                    ))
                    break
        
        return findings
    
    def _classify_by_patterns(self, text: str, ext: str) -> List[ClassificationFinding]:
        findings = []
        
        for lang, config in self.code_patterns.items():
            if ext in config.get("extensions", []):
                continue
            
            patterns = config.get("patterns", [])
            matches = 0
            for pattern in patterns:
                try:
                    if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
                        matches += 1
                        if matches >= 2:
                            confidence = config.get("confidence", 0.8)
                            findings.append(ClassificationFinding(
                                category=self.category,
                                subcategory=f"CODE_{lang}",
                                value=f"Обнаружен код на {lang}",
                                position=0,
                                context=f"Найдено {matches} характерных паттернов",
                                confidence=confidence,
                                detection_method="pattern_matching",
                                metadata={"language": lang, "matches": matches}
                            ))
                            break
                except re.error:
                    continue
            if findings:
                break
        
        if not findings:
            for script, config in self.script_patterns.items():
                if ext in config.get("extensions", []):
                    continue
                
                patterns = config.get("patterns", [])
                matches = 0
                for pattern in patterns:
                    try:
                        if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
                            matches += 1
                            if matches >= 2:
                                confidence = config.get("confidence", 0.8)
                                findings.append(ClassificationFinding(
                                    category=self.category,
                                    subcategory=f"SCRIPT_{script}",
                                    value=f"Обнаружен скрипт {script}",
                                    position=0,
                                    context=f"Найдено {matches} характерных паттернов",
                                    confidence=confidence,
                                    detection_method="pattern_matching",
                                    metadata={"script_type": script, "matches": matches}
                                ))
                                break
                    except re.error:
                        continue
                if findings:
                    break
        
        return findings
    
    def _get_text(self, file_context: FileContext) -> Optional[str]:
        cache_key = f"{file_context.id}_{file_context.modified_time}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        ext = Path(file_context.path).suffix.lower().lstrip('.')
        
        text_exts = ['txt', 'py', 'java', 'c', 'cpp', 'h', 'cs', 'js', 'ts', 'go', 'rs', 
                     'php', 'rb', 'swift', 'kt', 'sh', 'bash', 'ps1', 'bat', 'vbs', 'pl', 
                     'lua', 'r', 'json', 'xml', 'html', 'css', 'sql', 'md', 'yaml', 'yml']
        
        if ext in text_exts:
            try:
                text = file_context.content.decode('utf-8', errors='ignore')[:5000]
                if text:
                    max_cache = self.config.get("cache_size", 150)
                    if len(self.cache) >= max_cache:
                        items = list(self.cache.items())[:max_cache//5]
                        for k, _ in items:
                            del self.cache[k]
                    self.cache[cache_key] = text
                return text
            except:
                try:
                    text = file_context.content.decode('cp1251', errors='ignore')[:5000]
                    if text:
                        max_cache = self.config.get("cache_size", 150)
                        if len(self.cache) >= max_cache:
                            items = list(self.cache.items())[:max_cache//5]
                            for k, _ in items:
                                del self.cache[k]
                        self.cache[cache_key] = text
                    return text
                except:
                    return None
        
        return None
    
    def reload_models(self) -> None:
        pass
    
    def get_requirements(self) -> Dict[str, Any]:
        return {
            "memory_mb": 128,
            "models": [],
            "dependencies": []
        }


__all__ = ['CodeClassifier']