#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Managed Scanner — работает в непрерывном цикле, получает задания от Manager через REST API
"""

import os
import sys
import json
import time
import logging
import signal
import socket
import warnings
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import requests

# ============================================================
# ПОДАВЛЕНИЕ ШУМНЫХ ЛОГОВ И ПРЕДУПРЕЖДЕНИЙ
# ============================================================
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message="Multiple definitions in dictionary")

logging.getLogger("presidio-analyzer").setLevel(logging.WARNING)
logging.getLogger("presidio-analyzer").disabled = True
logging.getLogger("presidio-analyzer").propagate = False
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pypdf.generic").setLevel(logging.ERROR)
logging.getLogger("pypdf._reader").setLevel(logging.ERROR)
logging.getLogger("PdfReader").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ============================================================

sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.core.orchestrator import Orchestrator
from scanner.core.base import FileContext, ClassificationResult, ClassificationFinding, DataCategory
from scanner.connectors.filesystem import FileSystemConnector
from scanner.handlers.finding_collector import FindingCollector
from scanner.src.config_loader import AppConfig

logger = logging.getLogger("dcap-scanner")


class ManagerClient:
    def __init__(self, base_url: str, scanner_id: Optional[int] = None, config: AppConfig = None):
        self.base_url = base_url.rstrip('/')
        self.scanner_id = scanner_id
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        if config and config.client:
            self.timeout = config.client.timeout
            self.heartbeat_timeout = config.client.heartbeat_timeout
            self.submit_timeout = config.client.submit_timeout
        else:
            self.timeout = 30
            self.heartbeat_timeout = 10
            self.submit_timeout = 60
        
        self.files_scanned = 0
        self.findings_found = 0
        
        logger.info(f"[ManagerClient] Initialized: URL={base_url}, ScannerID={scanner_id}")
    
    def register(self, name: str, hostname: str = None, ip_address: str = None, scan_interval: int = 10) -> Optional[int]:
        url = f"{self.base_url}/api/scanner/register"
        
        if hostname is None:
            try:
                hostname = socket.gethostname()
            except:
                hostname = "unknown"
        
        if ip_address is None:
            try:
                ip_address = socket.gethostbyname(hostname)
            except:
                ip_address = "127.0.0.1"
        
        data = {
            "name": name,
            "hostname": hostname,
            "ip_address": ip_address,
            "scan_interval": scan_interval
        }
        
        try:
            logger.info(f"[Register] Registering scanner: {name}")
            response = self.session.post(url, json=data, timeout=self.timeout)
            
            if response.status_code == 200:
                result = response.json()
                scanner_id = result.get("scanner_id")
                logger.info(f"[Register] ✅ Scanner registered: ID={scanner_id}, name={result.get('name')}")
                self.scanner_id = scanner_id
                return scanner_id
            else:
                logger.error(f"[Register] ❌ Failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("[Register] ❌ Timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"[Register] ❌ Error: {e}")
            return None
    
    def heartbeat(self, status: str = "idle", task_id: Optional[int] = None) -> bool:
        if self.scanner_id is None:
            logger.warning("[Heartbeat] Scanner not registered")
            return False
            
        url = f"{self.base_url}/api/scanner/heartbeat"
        data = {
            "scanner_id": self.scanner_id,
            "status": status,
            "current_task_id": task_id
        }
        
        try:
            response = self.session.post(url, json=data, timeout=self.heartbeat_timeout)
            if response.status_code == 200:
                logger.debug(f"[Heartbeat] OK: {status}")
                return True
            else:
                logger.warning(f"[Heartbeat] Failed: {response.status_code}")
                return False
        except requests.exceptions.Timeout:
            logger.debug("[Heartbeat] Timeout")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"[Heartbeat] Error: {e}")
            return False
    
    def get_task(self) -> Optional[Dict[str, Any]]:
        if self.scanner_id is None:
            logger.warning("[GetTask] Scanner not registered")
            return None
            
        url = f"{self.base_url}/api/scanner/tasks/pending"
        params = {"scanner_id": self.scanner_id}
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                task = data.get("task")
                if task:
                    logger.info(f"[GetTask] Received task {task['id']}")
                    return task
                else:
                    logger.debug("[GetTask] No pending tasks")
                    return None
            else:
                logger.warning(f"[GetTask] Failed: {response.status_code}")
                return None
        except requests.exceptions.Timeout:
            logger.warning("[GetTask] Timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"[GetTask] Error: {e}")
            return None
    
    def submit_results(
        self,
        task_id: int,
        findings: List[Dict[str, Any]],
        catalog_entries: List[Dict[str, Any]],
        failed_files: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> bool:
        if self.scanner_id is None:
            logger.warning("[SubmitResults] Scanner not registered")
            return False
            
        url = f"{self.base_url}/api/scanner/tasks/{task_id}/results"
        data = {
            "findings": findings,
            "catalog_entries": catalog_entries,
            "failed_files": failed_files,
            "stats": stats
        }
        
        try:
            response = self.session.post(url, json=data, timeout=self.submit_timeout)
            if response.status_code == 200:
                result = response.json()
                logger.info(f"[SubmitResults] OK: {result.get('findings_count', 0)} findings, {result.get('catalog_entries_count', 0)} catalog entries")
                return True
            else:
                logger.error(f"[SubmitResults] Failed: {response.status_code}")
                logger.error(f"[SubmitResults] Response: {response.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"[SubmitResults] Error: {e}")
            return False
    
    def get_scanner_info(self) -> Optional[Dict[str, Any]]:
        if self.scanner_id is None:
            logger.warning("[GetScannerInfo] Scanner not registered")
            return None
            
        url = f"{self.base_url}/api/scanner/{self.scanner_id}"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"[GetScannerInfo] Failed: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"[GetScannerInfo] Error: {e}")
            return None


class ManagedScanner:
    def __init__(
        self,
        name: str,
        manager_url: str = "http://localhost:8000",
        scanner_id: Optional[int] = None,
        interval: int = 10,
        config: Optional[AppConfig] = None
    ):
        self.name = name
        self.manager_url = manager_url
        self.scanner_id = scanner_id
        self.interval = interval
        self.config = config
        self._should_exit = False
        
        self.client = None
        self.classifiers = []
        self._load_classifiers()
    
    def _load_classifiers(self):
        try:
            from scanner.classifiers.pii_classifier import PiiClassifier
            from scanner.classifiers.credentials_classifier import CredentialsClassifier
            from scanner.classifiers.code_classifier import CodeClassifier
            
            if self.config and self.config.classifiers:
                pii_config = self.config.classifiers.pii
                cred_config = self.config.classifiers.credentials
                code_config = self.config.classifiers.code
            else:
                pii_config = None
                cred_config = None
                code_config = None
            
            if not pii_config or pii_config.enabled:
                pii = PiiClassifier()
                pii_config_dict = {}
                if pii_config:
                    pii_config_dict = {
                        "ocr_enabled": pii_config.ocr_enabled,
                        "min_confidence": pii_config.min_confidence,
                        "ocr_languages": pii_config.ocr_languages,
                        "ocr_psm": pii_config.ocr_psm,
                        "ocr_timeout": pii_config.ocr_timeout,
                        "max_file_size_mb": pii_config.max_file_size_mb,
                        "quick_filter_enabled": pii_config.quick_filter_enabled
                    }
                pii.configure(pii_config_dict)
                self.classifiers.append(pii)
                logger.info(f"✅ PII Classifier loaded (OCR enabled: {pii_config_dict.get('ocr_enabled', True)})")
            
            if not cred_config or cred_config.enabled:
                cred = CredentialsClassifier()
                cred_config_dict = {}
                if cred_config:
                    cred_config_dict = {
                        "entropy_threshold": cred_config.entropy_threshold,
                        "max_file_size_mb": cred_config.max_file_size_mb
                    }
                cred.configure(cred_config_dict)
                self.classifiers.append(cred)
                logger.info(f"✅ Credentials Classifier loaded")
            
            if not code_config or code_config.enabled:
                code = CodeClassifier()
                code_config_dict = {}
                if code_config:
                    code_config_dict = {
                        "max_file_size_mb": code_config.max_file_size_mb
                    }
                code.configure(code_config_dict)
                self.classifiers.append(code)
                logger.info(f"✅ Code Classifier loaded")
            
            logger.info(f"✅ Загружено {len(self.classifiers)} классификаторов")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки классификаторов: {e}")
    
    def _register_scanner(self) -> bool:
        if self.client is None:
            logger.error("[Register] Client not initialized")
            return False
        
        if self.scanner_id is not None:
            logger.info(f"[Register] Using existing scanner ID: {self.scanner_id}")
            info = self.client.get_scanner_info()
            if info:
                logger.info(f"[Register] Scanner found: {info.get('name')}, status={info.get('status')}")
                return True
            else:
                logger.warning(f"[Register] Scanner ID {self.scanner_id} not found, re-registering...")
        
        scanner_id = self.client.register(
            name=self.name,
            scan_interval=self.interval
        )
        
        if scanner_id is not None:
            self.scanner_id = scanner_id
            return True
        
        logger.error("[Register] ❌ Registration failed")
        return False
    
    def _get_connector_config(self) -> Dict[str, Any]:
        if self.config and self.config.connector:
            return {
                "extensions": self.config.connector.extensions,
                "max_file_size_mb": self.config.connector.max_file_size_mb or 500,
                "recursive": self.config.connector.recursive,
                "skip_dirs": self.config.connector.skip_dirs
            }
        return {
            "extensions": ["*"],
            "max_file_size_mb": 500,
            "recursive": True,
            "skip_dirs": ["$Recycle.Bin", "System Volume Information", "tmp", "temp", "cache", "__pycache__", "node_modules", "venv", "logs", ".git"]
        }
    
    def _get_orchestrator_config(self) -> Dict[str, Any]:
        """Получить конфигурацию оркестратора"""
        # Получаем state_dir из конфига сканера
        state_dir = "scanner_state"  # значение по умолчанию
        if self.config and self.config.scanner:
            state_dir = self.config.scanner.state_dir or "scanner_state"
        
        return {
            "state_file": str(Path(state_dir) / "state.json"),  # Полный путь к state.json
            "logs_folder": "logs",
            "catalog_dir": "catalog",
            "max_failed_log": 100000,
            "performance": {
                "save_interval": 1000,
                "cache_cleanup_interval": 10000,
                "models_reload_after_files": 50000,
                "cache_memory_threshold_rss": 4096,
                "models_memory_threshold_rss": 6144,
            }
        }
    
    def _get_collector_config(self) -> Dict[str, Any]:
        return {
            "max_findings": 10000000,
            "max_failed_files": 100000
        }
    
    def _get_state_dir(self) -> Path:
        """Получить путь к директории состояния"""
        state_dir = "scanner_state"
        if self.config and self.config.scanner:
            state_dir = self.config.scanner.state_dir or "scanner_state"
        
        state_path = Path(state_dir)
        state_path.mkdir(parents=True, exist_ok=True)
        return state_path

    def _collect_catalog_entries(self, resource_path: str, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Собрать записи каталога - папки, в которых есть находки."""
        catalog_entries = {}
        
        for finding in findings:
            file_path = finding.get("file_path", "")
            if not file_path:
                continue
            
            folder_path = str(Path(file_path).parent)
            category = finding.get("category", "unknown")
            
            if folder_path not in catalog_entries:
                catalog_entries[folder_path] = {
                    "path": folder_path,
                    "classifiers": {},
                    "total_findings": 0,
                    "file_count": 0,
                    "files": set()
                }
            
            if category not in catalog_entries[folder_path]["classifiers"]:
                catalog_entries[folder_path]["classifiers"][category] = {
                    "count": 0,
                    "last_detected": datetime.utcnow().isoformat()
                }
            catalog_entries[folder_path]["classifiers"][category]["count"] += 1
            catalog_entries[folder_path]["total_findings"] += 1
            catalog_entries[folder_path]["files"].add(file_path)
        
        result = []
        for folder_path, data in catalog_entries.items():
            result.append({
                "path": folder_path,
                "metadata": {
                    "classifiers": data["classifiers"],
                    "total_findings": data["total_findings"],
                    "file_count": len(data["files"]),
                    "last_scanned": datetime.utcnow().isoformat()
                }
            })
        
        logger.info(f"[Catalog] Collected {len(result)} folders with findings")
        return result
    
    def _execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task["id"]
        resource_path = task["path"]
        scan_config = task.get("scan_config", {})
        
        logger.info(f"[Scanner] Executing task {task_id} on {resource_path}")
        
        collector = FindingCollector()
        collector_config = self._get_collector_config()
        collector.configure(collector_config)
        collector.start_collection()
        
        orchestrator = None
        connector = None
        
        try:
            orchestrator_config = self._get_orchestrator_config()
            orchestrator = Orchestrator(
                config=orchestrator_config,
                shared_classifiers=self.classifiers,
                shared_handlers=[collector]
            )
            
            connector = FileSystemConnector()
            connector_config = self._get_connector_config()
            connector.configure(connector_config)
            
            orchestrator.configure(connector)
            
            logger.info(f"[Scanner] Checking connector on {resource_path}")
            test_files = list(connector.list_files(resource_path))
            logger.info(f"[Scanner] Connector found {len(test_files)} files")
            
            if not test_files:
                logger.warning(f"[Scanner] No files found!")
                return {
                    "findings": [],
                    "catalog_entries": [],
                    "failed_files": [{"path": resource_path, "error": "No files found"}],
                    "stats": {"files_scanned": 0, "files_failed": 1, "total_findings": 0}
                }
            
            logger.info(f"[Scanner] Starting scan of {resource_path}")
            
            if hasattr(orchestrator, 'process_source'):
                orchestrator.process_source(resource_path)
            else:
                logger.warning("[Scanner] process_source not available, using manual processing")
                self._manual_scan(resource_path, orchestrator, connector)
            
            collector.finish_collection()
            
            results = collector.get_results()
            
            findings = results.get("findings", [])
            failed_files = results.get("failed_files", [])
            stats = results.get("stats", {})
            
            # Собираем каталог (папки с находками)
            catalog_entries = self._collect_catalog_entries(resource_path, findings)
            
            stats["started_at"] = task.get("assigned_at", datetime.utcnow().isoformat())
            stats["completed_at"] = datetime.utcnow().isoformat()
            
            logger.info(f"[Scanner] Task {task_id} completed:")
            logger.info(f"  - Files scanned: {stats.get('files_scanned', 0)}")
            logger.info(f"  - Files with findings: {stats.get('files_with_findings', 0)}")
            logger.info(f"  - Total findings: {stats.get('total_findings', 0)}")
            logger.info(f"  - Folders with findings: {len(catalog_entries)}")
            logger.info(f"  - Failed files: {stats.get('files_failed', 0)}")
            
            if findings:
                logger.info(f"[Scanner] Sample findings (first 5):")
                for i, f in enumerate(findings[:5]):
                    logger.info(f"  {i+1}. [{f.get('category')}] {f.get('value', '')[:50]} in {f.get('file_path', '')}")
            
            return {
                "findings": findings,
                "catalog_entries": catalog_entries,
                "failed_files": failed_files,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"[Scanner] Task {task_id} failed: {e}", exc_info=True)
            if collector:
                try:
                    collector.finish_collection()
                except:
                    pass
            
            results = collector.get_results() if collector else {"findings": [], "failed_files": [], "stats": {}}
            findings = results.get("findings", [])
            
            catalog_entries = []
            if findings:
                catalog_entries = self._collect_catalog_entries(resource_path, findings)
            
            return {
                "findings": findings,
                "catalog_entries": catalog_entries,
                "failed_files": results.get("failed_files", []) + [{
                    "path": resource_path,
                    "error": str(e),
                    "error_type": "scan_exception"
                }],
                "stats": {
                    "files_scanned": results.get("stats", {}).get("files_scanned", 0),
                    "files_failed": results.get("stats", {}).get("files_failed", 0) + 1,
                    "total_findings": results.get("stats", {}).get("total_findings", 0),
                    "started_at": task.get("assigned_at", datetime.utcnow().isoformat()),
                    "completed_at": datetime.utcnow().isoformat(),
                    "error": str(e)
                }
            }
        finally:
            if orchestrator:
                try:
                    if hasattr(orchestrator, 'stop'):
                        orchestrator.stop()
                except Exception as e:
                    logger.debug(f"Error stopping orchestrator: {e}")
    
    def _manual_scan(self, resource_path: str, orchestrator, connector):
        logger.info(f"[ManualScan] Starting manual scan of {resource_path}")
        
        try:
            files = list(connector.list_files(resource_path))
            logger.info(f"[ManualScan] Found {len(files)} files")
            
            for i, file_ctx in enumerate(files):
                try:
                    file_with_content = connector.get_content(file_ctx)
                    if not file_with_content or not file_with_content.content:
                        continue
                    
                    from scanner.core.base import ProcessingContext
                    context = ProcessingContext(file_context=file_with_content)
                    
                    if hasattr(orchestrator, '_process_file'):
                        orchestrator._process_file(context, len(files))
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"[ManualScan] Processed {i + 1}/{len(files)} files")
                        
                except Exception as e:
                    logger.debug(f"[ManualScan] Error processing file: {e}")
            
            logger.info(f"[ManualScan] Completed: {len(files)} files processed")
            
        except Exception as e:
            logger.error(f"[ManualScan] Error: {e}")
    
    def run_loop(self):
        print("=" * 60)
        print("🔍 DCAP MANAGED SCANNER (REST API)")
        print("=" * 60)
        print(f"   Имя: {self.name}")
        print(f"   Manager: {self.manager_url}")
        print(f"   Scanner ID: {self.scanner_id or 'auto-register'}")
        print(f"   Интервал: {self.interval} сек")
        print("   Для остановки: Ctrl+C")
        print("=" * 60)
        
        self.client = ManagerClient(
            base_url=self.manager_url,
            scanner_id=self.scanner_id,
            config=self.config
        )
        
        if not self._register_scanner():
            logger.error("❌ Ошибка регистрации сканера")
            return
        
        logger.info(f"🔄 Сканер {self.name} запущен (ID: {self.scanner_id})")
        
        self.client.heartbeat(status="idle")
        
        while not self._should_exit:
            try:
                heartbeat_ok = False
                for attempt in range(3):
                    if self.client.heartbeat(status="idle"):
                        heartbeat_ok = True
                        break
                    if attempt < 2:
                        time.sleep(1)
                
                if not heartbeat_ok:
                    logger.warning("⚠️ Heartbeat не удался после 3 попыток")
                
                task = self.client.get_task()
                
                if task:
                    self.client.heartbeat(status="busy", task_id=task["id"])
                    
                    result = self._execute_task(task)
                    
                    success = self.client.submit_results(
                        task_id=task["id"],
                        findings=result.get("findings", []),
                        catalog_entries=result.get("catalog_entries", []),
                        failed_files=result.get("failed_files", []),
                        stats=result.get("stats", {})
                    )
                    
                    if success:
                        logger.info(f"✅ Task {task['id']} completed successfully")
                    else:
                        logger.error(f"❌ Failed to submit results for task {task['id']}")
                    
                    self.client.heartbeat(status="idle")
                else:
                    time.sleep(self.interval)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в основном цикле: {e}")
                time.sleep(5)
        
        self.client.heartbeat(status="offline")
        logger.info("👋 Сканер остановлен")
    
    def stop(self):
        self._should_exit = True


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    for name in logging.root.manager.loggerDict:
        if 'presidio' in name.lower() or 'pypdf' in name.lower():
            logging.getLogger(name).setLevel(logging.WARNING)
            logging.getLogger(name).disabled = True
    
    config_path = "scanner/config/scanner_config.json"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    try:
        from scanner.src.config_loader import load_config
        config = load_config(config_path)
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        config = None
    
    if config:
        name = config.scanner.name
        manager_url = config.scanner.manager_url
        scanner_id = config.scanner.scanner_id
        interval = config.scanner.scan_interval
    else:
        name = "scanner-1"
        manager_url = "http://localhost:8000"
        scanner_id = None
        interval = 10
    
    scanner = ManagedScanner(
        name=name,
        manager_url=manager_url,
        scanner_id=scanner_id,
        interval=interval,
        config=config
    )
    
    try:
        scanner.run_loop()
    except KeyboardInterrupt:
        print("\n⏹️ Прервано пользователем")
    finally:
        scanner.stop()


if __name__ == "__main__":
    main()