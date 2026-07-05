#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация для сканирования E:\much_of_test_files
"""

CONFIG = {
    # ========================================
    # ПУТЬ К ТЕСТОВЫМ ФАЙЛАМ
    # ========================================
    "source_folders": [r"E:\much_of_test_files"],
    
    "logs_folder": "logs_large",
    "state_file": "state_large.json",
    "catalog_dir": "catalog_large",
    
    "performance": {
        "memory_limit_rss_mb": 8192,
        "memory_limit_vms_mb": 12000,
        "cache_cleanup_interval": 500,           # очистка каждые 500 файлов
        "models_reload_after_files": 3000,        # перезагрузка моделей каждые 3000 файлов
        "save_interval": 500,                     # сохранение состояния каждые 500 файлов
        "cache_memory_threshold_rss": 4000,
        "cache_memory_threshold_vms": 8000,
        "models_memory_threshold_rss": 6000,
        "models_memory_threshold_vms": 12000,
        "emergency_restart_threshold": 85,
        "monitor_interval": 5.0,
        "gc_interval_seconds": 30,
        "warning_threshold": 0.8
    },
    
    "classifiers": {
        "pii_classifier": {
            "enabled": True,
            "config": {
                "ocr_enabled": True,
                "min_confidence": 0.5,
                "max_file_size_mb": 50,
                "cache_size": 500,
                "ocr_cache_size": 500,
                "temp_dir": "temp_large",
                "models_cache": "models_large",
                "quick_filter_enabled": True,
                "worker_timeout": 60
            }
        },
        "credentials_classifier": {
            "enabled": True,
            "config": {
                "entropy_threshold": 4.5,
                "max_file_size_mb": 50,
                "cache_size": 500
            }
        },
        "code_classifier": {
            "enabled": True,
            "config": {
                "max_file_size_mb": 50,
                "cache_size": 500
            }
        }
    },
    
    "connectors": {
        "filesystem": {
            "enabled": True,
            "config": {
                "extensions": [
                    "txt", "pdf", "docx", "doc", "xlsx", "xls",
                    "png", "jpg", "jpeg", "gif", "bmp", "tiff",
                    "csv", "log", "json", "md", "ini", "cfg",
                    "conf", "yaml", "yml", "xml", "html", "css",
                    "py", "js", "java", "cpp", "c", "h", "go", "rs",
                    "sh", "ps1", "bat", "vbs", "pl", "rb", "swift", "kt"
                ],
                "max_file_size_mb": 50,
                "recursive": True,
                "skip_dirs": [
                    "$Recycle.Bin", "System Volume Information",
                    "tmp", "temp", "cache", ".git", "__pycache__",
                    "venv", "node_modules", "logs", "models",
                    "Thumbs.db", ".DS_Store"
                ]
            }
        }
    },
    
    "pipeline": {
        "connector": "filesystem",
        "classifiers": ["pii_classifier", "credentials_classifier", "code_classifier"],
        "handlers": ["grpc_handler"]
    },
    
    "monitoring_enabled": True,
    "max_failed_log": 1000
}

if __name__ == "__main__":
    import json
    print(json.dumps(CONFIG, indent=2, ensure_ascii=False))