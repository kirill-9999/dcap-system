#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Загрузчик конфигурации для Scanner
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
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
    state_dir: str = "scanner_state"  # <-- ДОБАВЛЕНО
    progress_report_interval: float = 5.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScannerConfig':
        return cls(
            name=data.get("name", "scanner-1"),
            manager_url=data.get("manager_url", "http://localhost:8000"),
            scanner_id=data.get("scanner_id"),
            scan_interval=data.get("scan_interval", 10),
            log_level=data.get("log_level", "INFO"),
            state_dir=data.get("state_dir", "scanner_state"),  # <-- ДОБАВЛЕНО
            progress_report_interval=data.get("progress_report_interval", 5.0),
        )


DEFAULT_EXTENSIONS = [
    "txt", "csv", "log", "json", "yaml", "yml", "xml", "toml", "ini", "cfg", "conf",
    "env", "envrc", "properties", "py", "js", "ts", "tsx", "java", "c", "cpp", "h",
    "hpp", "go", "rs", "sh", "bash", "zsh", "ps1", "cmd", "bat", "sql", "php", "rb",
    "lua", "r", "swift", "kt", "md", "rst", "html", "css", "scss", "dockerfile",
    "makefile", "tf", "hcl",
    "pem", "key", "crt", "csr", "cert", "p12", "pfx", "jks",
    "doc", "docx", "xls", "xlsx",
    "pdf", "png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp",
]

DEFAULT_SKIP_DIRS = [
    "$Recycle.Bin", "System Volume Information", "tmp", "temp", "cache",
    "__pycache__", ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build",
    "target", ".idea", ".vscode",
    "_example", "sample", "template", "examples", "samples", "templates",
    "test_data", "fixtures", "mocks",
]


@dataclass
class S3ConnectorConfig:
    """Конфигурация S3/MinIO-коннектора (день 53.1b, BACKLOG-097).

    Секреты (access_key / secret_key) НЕ хранятся здесь — только ENV
    на хосте сканера: S3_ACCESS_KEY / S3_SECRET_KEY (политика TASK-018).
    """
    endpoint: str = "host.docker.internal:9000"
    bucket: str = ""
    prefix: str = ""
    secure: bool = False
    use_path_style: bool = True
    region: str = "us-east-1"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'S3ConnectorConfig':
        return cls(
            endpoint=data.get("endpoint", "host.docker.internal:9000"),
            bucket=data.get("bucket", ""),
            prefix=data.get("prefix", ""),
            secure=bool(data.get("secure", False)),
            use_path_style=bool(data.get("use_path_style", True)),
            region=data.get("region", "us-east-1"),
        )


@dataclass
class ConnectorConfig:
    """Конфигурация коннектора"""
    extensions: list = field(default_factory=lambda: list(DEFAULT_EXTENSIONS))
    max_file_size_mb: int = 50
    recursive: bool = True
    skip_dirs: list = field(default_factory=lambda: list(DEFAULT_SKIP_DIRS))
    buffer_size: int = 1024 * 1024
    max_text_chars: int = 200000
    context_lines: int = 2  # <-- ДОБАВЛЕНО (день 40.2)
    max_parallel_files: int = 1  # <-- ДОБАВЛЕНО (день 42, параллельный скан)
    # День 53.1b (BACKLOG-097): опциональная секция S3/MinIO (без секретов).
    # None, если в конфиге секции connector.s3 нет.
    s3: Optional['S3ConnectorConfig'] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectorConfig':
        return cls(
            extensions=data.get("extensions", list(DEFAULT_EXTENSIONS)),
            max_file_size_mb=data.get("max_file_size_mb", 50),
            recursive=data.get("recursive", True),
            skip_dirs=data.get("skip_dirs", list(DEFAULT_SKIP_DIRS)),
            buffer_size=data.get("buffer_size", 1024 * 1024),
            max_text_chars=data.get("max_text_chars", 200000),
            context_lines=data.get("context_lines", 2),  # <-- ДОБАВЛЕНО
            max_parallel_files=data.get("max_parallel_files", 1),  # <-- ДОБАВЛЕНО
            s3=S3ConnectorConfig.from_dict(data["s3"]) if data.get("s3") else None,
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
    analyzer_pool_size: int = 0  # 0 = авто (по числу воркеров коннектора)
    # 53.4l (v3.14.10): NER-категории (person/location/organization/date_time/nrp)
    # не маскируются (ARCHITECTURE.md), но давали 99.9% находок. ner_enabled=false
    # исключает их из анализа и отключает spaCy parser/ner.
    ner_enabled: bool = False
    excluded_entities: List[str] = field(
        default_factory=lambda: ["PERSON", "LOCATION", "ORGANIZATION", "DATE_TIME", "NRP"]
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PiiConfig':
        excluded = data.get("excluded_entities")
        if isinstance(excluded, str):
            excluded = [e.strip() for e in excluded.split(",") if e.strip()]
        return cls(
            enabled=data.get("enabled", True),
            ocr_enabled=data.get("ocr_enabled", True),
            min_confidence=data.get("min_confidence", 0.5),
            ocr_languages=data.get("ocr_languages", "rus+eng"),
            ocr_psm=data.get("ocr_psm", 6),
            ocr_timeout=data.get("ocr_timeout", 60),
            max_file_size_mb=data.get("max_file_size_mb", 100),
            quick_filter_enabled=data.get("quick_filter_enabled", True),
            analyzer_pool_size=data.get("analyzer_pool_size", 0),  # <-- ДОБАВЛЕНО (день 40.2+)
            ner_enabled=data.get("ner_enabled", False),
            excluded_entities=excluded or ["PERSON", "LOCATION", "ORGANIZATION", "DATE_TIME", "NRP"],
        )


@dataclass
class CredentialsConfig:
    """Конфигурация Credentials классификатора"""
    enabled: bool = True
    entropy_threshold: float = 4.5
    min_length: int = 8
    max_file_size_mb: int = 50
    strict_filter: bool = True
    confidence_threshold: float = 0.7
    no_generic: bool = False
    require_mixed: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CredentialsConfig':
        return cls(
            enabled=data.get("enabled", True),
            entropy_threshold=data.get("entropy_threshold", 4.5),
            min_length=data.get("min_length", 8),
            max_file_size_mb=data.get("max_file_size_mb", 50),
            strict_filter=data.get("strict_filter", True),
            confidence_threshold=data.get("confidence_threshold", 0.7),
            no_generic=data.get("no_generic", False),
            require_mixed=data.get("require_mixed", False)
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
        # Поддержка обоих вариантов имён секций: "pii" и "pii_classifier" (день 42)
        return cls(
            pii=PiiConfig.from_dict(data.get("pii", data.get("pii_classifier", {}))),
            credentials=CredentialsConfig.from_dict(
                data.get("credentials", data.get("credentials_classifier", {}))
            ),
            code=CodeConfig.from_dict(data.get("code", data.get("code_classifier", {})))
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
    # 53.4m (v3.14.11): параллелизм обработки файлов
    executor: str = "process"
    max_workers: int = 4
    chunk_size: int = 100
    max_parallel_files: int = 8

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
            monitor_interval=data.get("monitor_interval", 5.0),
            executor=data.get("executor", "process"),
            max_workers=data.get("max_workers", 4),
            chunk_size=data.get("chunk_size", 100),
            max_parallel_files=data.get("max_parallel_files", 8),
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
    cert_path: Optional[str] = None
    key_path: Optional[str] = None
    ca_path: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClientConfig':
        return cls(
            timeout=data.get("timeout", 10),
            heartbeat_timeout=data.get("heartbeat_timeout", 5),
            submit_timeout=data.get("submit_timeout", 30),
            cert_path=data.get("cert_path"),
            key_path=data.get("key_path"),
            ca_path=data.get("ca_path")
        )


@dataclass
class LoggingConfig:
    """Конфигурация логирования (53.4n, v3.14.12, BUG-283)."""
    level: str = "INFO"
    file: str = "logs/scanner.log"
    max_size_mb: int = 100
    backup_count: int = 5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LoggingConfig':
        try:
            max_size_mb = int(data.get("max_size_mb", 100) or 100)
        except (TypeError, ValueError):
            max_size_mb = 100
        try:
            backup_count = int(data.get("backup_count", 5) or 5)
        except (TypeError, ValueError):
            backup_count = 5
        return cls(
            level=str(data.get("level", "INFO") or "INFO"),
            file=str(data.get("file", "logs/scanner.log") or "logs/scanner.log"),
            max_size_mb=max_size_mb,
            backup_count=backup_count,
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
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    # 53.4m (v3.14.11): верхнеуровневая секция performance (executor/max_workers/...)
    performance: PerformanceConfig = field(default_factory=lambda: PerformanceConfig())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        orchestrator_raw = data.get("orchestrator", {}) or {}
        performance_raw = data.get("performance")
        if performance_raw is None:
            performance_raw = orchestrator_raw.get("performance", {})
        return cls(
            scanner=ScannerConfig.from_dict(data.get("scanner", {})),
            connector=ConnectorConfig.from_dict(data.get("connector", {})),
            classifiers=ClassifiersConfig.from_dict(data.get("classifiers", {})),
            orchestrator=OrchestratorConfig.from_dict(orchestrator_raw),
            finding_collector=FindingCollectorConfig.from_dict(data.get("finding_collector", {})),
            client=ClientConfig.from_dict(data.get("client", {})),
            performance=PerformanceConfig.from_dict(performance_raw or {}),
            logging=LoggingConfig.from_dict(data.get("logging", {})),
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
                "log_level": self.scanner.log_level,
                "state_dir": self.scanner.state_dir,  # <-- ДОБАВЛЕНО
                "progress_report_interval": self.scanner.progress_report_interval
            },
            "connector": {
                "extensions": self.connector.extensions,
                "max_file_size_mb": self.connector.max_file_size_mb,
                "recursive": self.connector.recursive,
                "skip_dirs": self.connector.skip_dirs,
                "buffer_size": self.connector.buffer_size,
                "max_text_chars": self.connector.max_text_chars,
                "context_lines": self.connector.context_lines,
                "max_parallel_files": self.connector.max_parallel_files
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
                    "quick_filter_enabled": self.classifiers.pii.quick_filter_enabled,
                    "analyzer_pool_size": self.classifiers.pii.analyzer_pool_size,
                    "ner_enabled": self.classifiers.pii.ner_enabled,
                    "excluded_entities": self.classifiers.pii.excluded_entities
                },
                "credentials": {
                    "enabled": self.classifiers.credentials.enabled,
                    "entropy_threshold": self.classifiers.credentials.entropy_threshold,
                    "min_length": self.classifiers.credentials.min_length,
                    "max_file_size_mb": self.classifiers.credentials.max_file_size_mb,
                    "strict_filter": self.classifiers.credentials.strict_filter,
                    "confidence_threshold": self.classifiers.credentials.confidence_threshold,
                    "no_generic": self.classifiers.credentials.no_generic,
                    "require_mixed": self.classifiers.credentials.require_mixed
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
            },
            # 53.4m (v3.14.11): параллелизм обработки файлов
            "performance": {
                "max_parallel_files": self.performance.max_parallel_files,
                "executor": self.performance.executor,
                "max_workers": self.performance.max_workers,
                "chunk_size": self.performance.chunk_size
            }
        }
    
    def save(self, file_path: str) -> None:
        """Сохранение конфигурации в JSON файл"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


def load_config(config_path: str) -> AppConfig:
    """Загрузка конфигурации с проверкой.

    Конфиг обязателен. Отсутствующий обязательный параметр вызывает ошибку
    (значений по умолчанию для обязательных параметров нет).
    """
    if not config_path:
        print("[ERROR] Config file path is required")
        print("Usage: python run_scanner.py <config.json>")
        sys.exit(1)
    
    if not os.path.exists(config_path):
        print(f"[ERROR] Config file not found: {config_path}")
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in config file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error reading config: {e}")
        sys.exit(1)

    _apply_env_overrides(data)
    _validate_required(data)

    try:
        config = AppConfig.from_dict(data)
        print(f"[OK] Config loaded: {config_path}")
        return config
    except Exception as e:
        print(f"[ERROR] Error loading config: {e}")
        sys.exit(1)


def _apply_env_overrides(data: Dict[str, Any]):
    """Применение env-переопределений (для контейнерного запуска).

    MANAGER_URL / LOG_LEVEL имеют приоритет над значениями из файла конфига.
    """
    env_manager_url = os.environ.get("MANAGER_URL")
    if env_manager_url:
        data.setdefault("scanner", {})["manager_url"] = env_manager_url

    env_log_level = os.environ.get("LOG_LEVEL")
    if env_log_level:
        data.setdefault("scanner", {})["log_level"] = env_log_level


def _validate_required(data: Dict[str, Any]):
    """Проверка наличия обязательных параметров конфига.

    Отсутствующий обязательный параметр вызывает ошибку (без значений по умолчанию).
    """
    required_sections = ["scanner", "connector", "classifiers", "client", "logging"]
    missing_sections = [s for s in required_sections if s not in data]
    if missing_sections:
        print(f"[ERROR] Ошибка: отсутствуют обязательные секции конфига: {', '.join(missing_sections)}")
        sys.exit(1)

    missing_keys = []

    # scanner: name, manager_url, scan_interval, log_level
    for key in ["name", "manager_url", "scan_interval", "log_level"]:
        if key not in data["scanner"]:
            missing_keys.append(f"scanner.{key}")

    # connector: skip_dirs
    for key in ["skip_dirs"]:
        if key not in data["connector"]:
            missing_keys.append(f"connector.{key}")

    # client: timeout, heartbeat_timeout, submit_timeout
    for key in ["timeout", "heartbeat_timeout", "submit_timeout"]:
        if key not in data["client"]:
            missing_keys.append(f"client.{key}")

    # classifiers: обязана содержать хотя бы один классификатор
    classifier_keys = list(data["classifiers"].keys())
    if not classifier_keys:
        missing_keys.append("classifiers.<классификатор>")

    if missing_keys:
        print(f"[ERROR] Ошибка: отсутствуют обязательные параметры конфига: {', '.join(missing_keys)}")
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