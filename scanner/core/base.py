#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Базовые интерфейсы (без рисков)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class DataCategory(Enum):
    """Категории классифицируемых данных"""
    PII = "pii"
    CREDENTIALS = "credentials"
    FINANCIAL = "financial"
    MEDICAL = "medical"
    CODE_SECRETS = "code_secrets"
    CUSTOM = "custom"


class SourceType(Enum):
    """Типы источников данных"""
    FILESYSTEM = "filesystem"
    S3 = "s3"
    MINIO = "minio"
    SFTP = "sftp"
    SMB = "smb"
    SHAREPOINT = "sharepoint"
    DATABASE = "database"
    FTP = "ftp"
    AZURE_BLOB = "azure_blob"
    GCS = "gcs"


@dataclass
class FileContext:
    """Контекст файла для обработки"""
    id: str
    path: str
    source_type: SourceType
    size_bytes: int
    modified_time: datetime
    content: Optional[bytes] = None
    text_content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Для S3/Minio
    bucket: Optional[str] = None
    key: Optional[str] = None
    endpoint: Optional[str] = None


@dataclass
class ClassificationFinding:
    """Одна классифицированная находка (без риска)"""
    category: DataCategory
    subcategory: str
    value: str
    position: int
    context: str
    confidence: float
    detection_method: str
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassificationResult:
    """Результат классификации для одного файла"""
    classifier_name: str
    category: DataCategory
    findings: List[ClassificationFinding]
    processing_time: float
    success: bool = True
    error: Optional[str] = None


@dataclass
class ProcessingContext:
    """Контекст обработки, передаваемый между классификаторами"""
    file_context: FileContext
    classifier_results: Dict[str, ClassificationResult] = field(default_factory=dict)
    shared_cache: Dict[str, Any] = field(default_factory=dict)
    stop_processing: bool = False


class ISourceConnector(ABC):
    """Интерфейс коннектора к источнику данных"""
    
    @property
    @abstractmethod
    def connector_type(self) -> SourceType:
        pass
    
    @abstractmethod
    def configure(self, config: Dict[str, Any]) -> None:
        pass
    
    @abstractmethod
    def list_files(self, source: str) -> Iterator[FileContext]:
        pass
    
    @abstractmethod
    def get_content(self, file_context: FileContext) -> Optional[FileContext]:
        pass


class IClassifier(ABC):
    """Интерфейс классификатора данных"""
    
    @property
    @abstractmethod
    def classifier_name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def category(self) -> DataCategory:
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        pass
    
    @abstractmethod
    def configure(self, config: Dict[str, Any]) -> None:
        pass
    
    @abstractmethod
    def can_classify(self, file_context: FileContext) -> bool:
        pass
    
    @abstractmethod
    def classify(self, context: ProcessingContext) -> ClassificationResult:
        pass
    
    @abstractmethod
    def get_requirements(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def reload_models(self) -> None:
        pass


class IOutputHandler(ABC):
    """Интерфейс обработчика вывода"""
    
    @property
    @abstractmethod
    def handler_name(self) -> str:
        pass
    
    @abstractmethod
    def configure(self, config: Dict[str, Any]) -> None:
        pass
    
    @abstractmethod
    def write(self, result: ClassificationResult, file_context: FileContext) -> None:
        pass
    
    @abstractmethod
    def flush(self) -> None:
        pass
