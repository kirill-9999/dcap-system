#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузчик конфигурации для Scanner
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScannerConfig:
    """Конфигурация сканера"""
    name: str = "scanner-1"
    manager_url: str = "http://localhost:8000"
    scanner_id: Optional[int] = None
    scan_interval: int = 10
    log_level: str = "INFO"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScannerConfig':
        return cls(
            name=data.get("name", "scanner-1"),
            manager_url=data.get("manager_url", "http://localhost:8000"),
            scanner_id=data.get("scanner_id"),
            scan_interval=data.get("scan_interval", 10),
            log_level=data.get("log_level", "INFO")
        )


@dataclass
class ConnectorConfig:
    """Конфигурация коннектора"""
    extensions: list = field(default_factory=lambda: ["txt", "pdf", "docx", "xlsx", "png", "jpg", "jpeg", "json", "csv", "log"])
    max_file_size_mb: int = 50
    recursive: bool = True
    skip_dirs: list = field(default_factory=lambda: ["$Recycle.Bin", "System Volume Information", "tmp", "temp", "cache"])
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectorConfig':
        return cls(
            extensions=data.get("extensions", ["txt", "pdf", "docx", "xlsx", "png", "jpg", "jpeg", "json", "csv", "log"]),
            max_file_size_mb=data.get("max_file_size_mb", 50),
            recursive=data.get("recursive", True),
            skip_dirs=data.get("skip_dirs", ["$Recycle.Bin", "System Volume Information", "tmp", "temp", "cache"])
        )


@dataclass
class PiiConfig:
    """Конфигурация PII классификатора"""
    enabled: bool = True
    ocr_enabled: bool = True
    min_confidence: float = 0.5
    ocr_languages: str = "rus+eng"
    ocr_psm: int = 6
    ocr_timeout: int = 60
    max_file_size_mb: int = 100
    quick_filter_enabled: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PiiConfig':
        return cls(
            enabled=data.get("enabled", True),
            ocr_enabled=data.get("ocr_enabled", True),
            min_confidence=data.get("min_confidence", 0.5),
            ocr_languages=data.get("ocr_languages", "rus+eng"),
            ocr_psm=data.get("ocr_psm", 6),
            ocr_timeout=data.get("ocr_timeout", 60),
            max_file_size_mb=data.get("max_file_size_mb", 100),
            quick_filter_enabled=data.get("quick_filter_enabled", True)
        )


@dataclass
class CredentialsConfig:
    """Конфигурация Credentials классификатора"""
    enabled: bool = True
    entropy_threshold: float = 4.5
    max_file_size_mb: int = 50
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CredentialsConfig':
        return cls(
            enabled=data.get("enabled", True),
            entropy_threshold=data.get("entropy_threshold", 4.5),
            max_file_size_mb=data.get("max_file_size_mb", 50)
        )


@dataclass
class CodeConfig:
    """Конфигурация Code классификатора"""
    enabled: bool = True
    max_file_size_mb: int = 50
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CodeConfig':
        return cls(
            enabled=data.get("enabled", True),
            max_file_size_mb=data.get("max_file_size_mb", 50)
        )


@dataclass
class ClassifiersConfig:
    """Конфигурация всех классификаторов"""
    pii: PiiConfig = field(default_factory=PiiConfig)
    credentials: CredentialsConfig = field(default_factory=CredentialsConfig)
    code: CodeConfig = field(default_factory=CodeConfig)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClassifiersConfig':
        return cls(
            pii=PiiConfig.from_dict(data.get("pii", {})),
            credentials=CredentialsConfig.from_dict(data.get("credentials", {})),
            code=CodeConfig.from_dict(data.get("code", {}))
        )


@dataclass
class PerformanceConfig:
    """Конфигурация производительности"""
    save_interval: int = 100
    catalog_save_interval: int = 500
    cache_cleanup_interval: int = 200
    cache_memory_threshold_rss: int = 2000
    cache_memory_threshold_vms: int = 8000
    models_reload_after_files: int = 1000
    models_memory_threshold_rss: int = 3000
    models_memory_threshold_vms: int = 12000
    emergency_restart_threshold: int = 85
    monitoring_enabled: bool = True
    monitor_interval: float = 5.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PerformanceConfig':
        return cls(
            save_interval=data.get("save_interval", 100),
            catalog_save_interval=data.get("catalog_save_interval", 500),
            cache_cleanup_interval=data.get("cache_cleanup_interval", 200),
            cache_memory_threshold_rss=data.get("cache_memory_threshold_rss", 2000),
            cache_memory_threshold_vms=data.get("cache_memory_threshold_vms", 8000),
            models_reload_after_files=data.get("models_reload_after_files", 1000),
            models_memory_threshold_rss=data.get("models_memory_threshold_rss", 3000),
            models_memory_threshold_vms=data.get("models_memory_threshold_vms", 12000),
            emergency_restart_threshold=data.get("emergency_restart_threshold", 85),
            monitoring_enabled=data.get("monitoring_enabled", True),
            monitor_interval=data.get("monitor_interval", 5.0)
        )


@dataclass
class OrchestratorConfig:
    """Конфигурация оркестратора"""
    state_file: str = "state.json"
    logs_folder: str = "logs"
    catalog_dir: str = "catalog"
    max_failed_log: int = 1000
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrchestratorConfig':
        return cls(
            state_file=data.get("state_file", "state.json"),
            logs_folder=data.get("logs_folder", "logs"),
            catalog_dir=data.get("catalog_dir", "catalog"),
            max_failed_log=data.get("max_failed_log", 1000),
            performance=PerformanceConfig.from_dict(data.get("performance", {}))
        )


@dataclass
class FindingCollectorConfig:
    """Конфигурация сборщика находок"""
    max_findings: int = 50000
    max_failed_files: int = 1000
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FindingCollectorConfig':
        return cls(
            max_findings=data.get("max_findings", 50000),
            max_failed_files=data.get("max_failed_files", 1000)
        )


@dataclass
class ClientConfig:
    """Конфигурация HTTP клиента"""
    timeout: int = 10
    heartbeat_timeout: int = 5
    submit_timeout: int = 30
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClientConfig':
        return cls(
            timeout=data.get("timeout", 10),
            heartbeat_timeout=data.get("heartbeat_timeout", 5),
            submit_timeout=data.get("submit_timeout", 30)
        )


@dataclass
class AppConfig:
    """Полная конфигурация приложения"""
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    connector: ConnectorConfig = field(default_factory=ConnectorConfig)
    classifiers: ClassifiersConfig = field(default_factory=ClassifiersConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    finding_collector: FindingCollectorConfig = field(default_factory=FindingCollectorConfig)
    client: ClientConfig = field(default_factory=ClientConfig)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        return cls(
            scanner=ScannerConfig.from_dict(data.get("scanner", {})),
            connector=ConnectorConfig.from_dict(data.get("connector", {})),
            classifiers=ClassifiersConfig.from_dict(data.get("classifiers", {})),
            orchestrator=OrchestratorConfig.from_dict(data.get("orchestrator", {})),
            finding_collector=FindingCollectorConfig.from_dict(data.get("finding_collector", {})),
            client=ClientConfig.from_dict(data.get("client", {}))
        )
    
    @classmethod
    def from_file(cls, file_path: str) -> 'AppConfig':
        """Загрузка конфигурации из JSON файла"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "scanner": {
                "name": self.scanner.name,
                "manager_url": self.scanner.manager_url,
                "scanner_id": self.scanner.scanner_id,
                "scan_interval": self.scanner.scan_interval,
                "log_level": self.scanner.log_level
            },
            "connector": {
                "extensions": self.connector.extensions,
                "max_file_size_mb": self.connector.max_file_size_mb,
                "recursive": self.connector.recursive,
                "skip_dirs": self.connector.skip_dirs
            },
            "classifiers": {
                "pii": {
                    "enabled": self.classifiers.pii.enabled,
                    "ocr_enabled": self.classifiers.pii.ocr_enabled,
                    "min_confidence": self.classifiers.pii.min_confidence,
                    "ocr_languages": self.classifiers.pii.ocr_languages,
                    "ocr_psm": self.classifiers.pii.ocr_psm,
                    "ocr_timeout": self.classifiers.pii.ocr_timeout,
                    "max_file_size_mb": self.classifiers.pii.max_file_size_mb,
                    "quick_filter_enabled": self.classifiers.pii.quick_filter_enabled
                },
                "credentials": {
                    "enabled": self.classifiers.credentials.enabled,
                    "entropy_threshold": self.classifiers.credentials.entropy_threshold,
                    "max_file_size_mb": self.classifiers.credentials.max_file_size_mb
                },
                "code": {
                    "enabled": self.classifiers.code.enabled,
                    "max_file_size_mb": self.classifiers.code.max_file_size_mb
                }
            },
            "orchestrator": {
                "state_file": self.orchestrator.state_file,
                "logs_folder": self.orchestrator.logs_folder,
                "catalog_dir": self.orchestrator.catalog_dir,
                "max_failed_log": self.orchestrator.max_failed_log,
                "performance": {
                    "save_interval": self.orchestrator.performance.save_interval,
                    "catalog_save_interval": self.orchestrator.performance.catalog_save_interval,
                    "cache_cleanup_interval": self.orchestrator.performance.cache_cleanup_interval,
                    "cache_memory_threshold_rss": self.orchestrator.performance.cache_memory_threshold_rss,
                    "cache_memory_threshold_vms": self.orchestrator.performance.cache_memory_threshold_vms,
                    "models_reload_after_files": self.orchestrator.performance.models_reload_after_files,
                    "models_memory_threshold_rss": self.orchestrator.performance.models_memory_threshold_rss,
                    "models_memory_threshold_vms": self.orchestrator.performance.models_memory_threshold_vms,
                    "emergency_restart_threshold": self.orchestrator.performance.emergency_restart_threshold,
                    "monitoring_enabled": self.orchestrator.performance.monitoring_enabled,
                    "monitor_interval": self.orchestrator.performance.monitor_interval
                }
            },
            "finding_collector": {
                "max_findings": self.finding_collector.max_findings,
                "max_failed_files": self.finding_collector.max_failed_files
            },
            "client": {
                "timeout": self.client.timeout,
                "heartbeat_timeout": self.client.heartbeat_timeout,
                "submit_timeout": self.client.submit_timeout
            }
        }
    
    def save(self, file_path: str) -> None:
        """Сохранение конфигурации в JSON файл"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


def load_config(config_path: str) -> AppConfig:
    """Загрузка конфигурации с проверкой"""
    if not config_path:
        print("❌ Config file path is required")
        print("Usage: python run_scanner.py --config <config.json>")
        sys.exit(1)
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)
    
    try:
        config = AppConfig.from_file(config_path)
        print(f"✅ Config loaded: {config_path}")
        return config
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in config file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)


__all__ = [
    'AppConfig',
    'ScannerConfig',
    'ConnectorConfig',
    'ClassifiersConfig',
    'PiiConfig',
    'CredentialsConfig',
    'CodeConfig',
    'OrchestratorConfig',
    'PerformanceConfig',
    'FindingCollectorConfig',
    'ClientConfig',
    'load_config'
]