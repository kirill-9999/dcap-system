#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Managed Scanner — работает в непрерывном цикле, получает задания от Manager через REST API
"""

import os
import sys
import json
import time
import math
import base64
import hashlib
import uuid

math_isfinite = math.isfinite
import logging
import signal
import socket
import warnings
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
from scanner.connectors.filesystem import FileSystemConnector, FilesystemConnector
# День 53.1b (BACKLOG-097): коннектор выбирается по source_type из payload задачи
from scanner.connectors.factory import create_line_connector
from scanner.handlers.finding_collector import FindingCollector
from scanner.src.config_loader import AppConfig
from scanner.src.heartbeat import HeartbeatThread
from scanner.src import metrics as scanner_metrics
from scanner.src.encryption import get_encryption, mask, mask_line, mask_context
from scanner.src.finding import Finding

logger = logging.getLogger("dcap-scanner")


# BACKLOG-086 (TASK-046/050, v3.13.19): встраивание OCR-фрагментов в payload.
# MAX_FRAGMENT_EMBED_SIZE — файл больше лимита не встраиваем (остаётся fragment_path).
# MAX_BATCH_SIZE_BYTES — разбивка POST результатов по размеру (фрагменты 2 МБ).
MAX_FRAGMENT_EMBED_SIZE = int(os.environ.get("MAX_FRAGMENT_EMBED_SIZE", 2 * 1024 * 1024))
MAX_BATCH_SIZE_BYTES = int(os.environ.get("MAX_BATCH_SIZE_BYTES", 20 * 1024 * 1024))
_MAX_BATCH_COUNT = 500  # прежний лимит количества finding на POST
_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}


def _embed_fragment(finding: "Finding") -> dict:
    """BACKLOG-086 (TASK-046): встроить OCR-фрагмент в payload.

    Только для image_region (OCR). text_line — данные в line_text_encrypted,
    byte_range — отложено до v3.1.0. Если файл отсутствует или больше
    MAX_FRAGMENT_EMBED_SIZE — ничего не встраиваем (остаётся fragment_path).
    """
    if finding.fragment_type != "image_region":
        return {}
    if not finding.fragment_path or not os.path.exists(finding.fragment_path):
        return {}
    size = os.path.getsize(finding.fragment_path)
    if size > MAX_FRAGMENT_EMBED_SIZE:
        return {}
    with open(finding.fragment_path, "rb") as f:
        data = f.read()
    ext = os.path.splitext(finding.fragment_path)[1].lower()
    return {
        "fragment_base64": base64.b64encode(data).decode("ascii"),
        "fragment_mime": _IMAGE_MIME.get(ext, "image/png"),
        "fragment_hash": hashlib.sha256(data).hexdigest(),
        "fragment_size": len(data),
    }


def _split_by_size(findings: List[Dict[str, Any]], max_bytes: int) -> List[List[Dict[str, Any]]]:
    """BACKLOG-086 (TASK-050): разбивка findings на батчи по общему размеру.

    Счётный чанк (500) может всё ещё содержать 500 × 2 МБ base64-фрагментов —
    разбиваем ещё и по общему размеру payload (оценка по fragment_size).
    """
    batches: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    cur_size = 0
    for item in findings:
        fbytes = item.get("fragment_size") or 0
        if cur and (len(cur) >= _MAX_BATCH_COUNT or cur_size + fbytes > max_bytes):
            batches.append(cur)
            cur, cur_size = [], 0
        cur.append(item)
        cur_size += fbytes
    if cur:
        batches.append(cur)
    return batches or [[]]


class ProgressPoller(threading.Thread):
    """Периодически читает state.json оркестратора и обновляет прогресс в heartbeat.

    Позволяет показывать LIVE-прогресс (files_scanned / total) во время долгого
    сканирования, даже если основной цикл занят process_source.
    """

    def __init__(self, state_file: str, total: int, heartbeat: HeartbeatThread,
                 interval: int = 15):
        super().__init__(daemon=True, name="ProgressPoller")
        self.state_file = state_file
        self.total = total or 0
        self.heartbeat = heartbeat
        self.interval = interval
        self._stop = threading.Event()

    def _count_processed(self) -> int:
        if not self.state_file or not os.path.exists(self.state_file):
            return 0
        with open(self.state_file, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)

    def run(self):
        while not self._stop.wait(self.interval):
            try:
                processed = self._count_processed()
                if processed:
                    self.heartbeat.set_progress(processed, self.total)
            except Exception as e:
                logger.debug("ProgressPoller read error: %s", e)

    def stop(self):
        self._stop.set()


class SubmitStatus:
    """Итог отправки результатов (BUG-097, TASK-066, v3.13.25).

    Различает «временно не отправилось» (нужен повтор) и «задания больше нет
    в Manager» (повтор бессмысленен — задача удалена, повтор вёл к вечной
    петле 404 в логах и к зависшим заданиям в статусе assigned).
    """
    OK = "ok"
    RETRY = "retry"
    LOST = "lost"


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

        # HTTP retry (TASK-026, BUG-061): ретраи при 5xx и сетевых сбоях.
        # total=5, backoff=0.5, fire-and-forget (raise_on_status=False).
        retry = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset(['GET', 'POST']),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        if config and config.client:
            self.timeout = config.client.timeout
            self.heartbeat_timeout = config.client.heartbeat_timeout
            self.submit_timeout = config.client.submit_timeout

            # mTLS (День 34): cert/key/ca из config.client
            cert_path = getattr(config.client, "cert_path", None)
            key_path = getattr(config.client, "key_path", None)
            ca_path = getattr(config.client, "ca_path", None)
            if cert_path and key_path and ca_path:
                self.session.cert = (cert_path, key_path)
                self.session.verify = ca_path
                logger.info("[ManagerClient] mTLS enabled")
            else:
                logger.info("[ManagerClient] mTLS not configured, plain HTTP")
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
                logger.info(f"[Register] [OK] Scanner registered: ID={scanner_id}, name={result.get('name')}")
                self.scanner_id = scanner_id
                return scanner_id
            else:
                logger.error(f"[Register] [ERROR] Failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("[Register] [ERROR] Timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"[Register] [ERROR] Error: {e}")
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
        """Совместимая обёртка: True только при полной успешной отправке."""
        return self.submit_results_status(
            task_id, findings, catalog_entries, failed_files, stats
        ) == SubmitStatus.OK

    def submit_results_status(
        self,
        task_id: int,
        findings: List[Dict[str, Any]],
        catalog_entries: List[Dict[str, Any]],
        failed_files: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> str:
        """Отправка результатов с явным статусом (BUG-097, TASK-066, v3.13.25).

        Раньше метод возвращал только bool, из-за чего офлайн-буфер с
        удалённым заданием ретраился бесконечно: Manager отвечал 404, сканер
        сохранял файл заново и повторял попытку в каждом цикле main().
        Теперь 404 → SubmitStatus.LOST, и вызывающий код отбрасывает пачку.
        """
        if self.scanner_id is None:
            logger.warning("[SubmitResults] Scanner not registered")
            return SubmitStatus.RETRY
            
        url = f"{self.base_url}/api/scanner/tasks/{task_id}/results"
        # BACKLOG-086 (TASK-050): разбивка по размеру payload, а не только по
        # счётчику — встроенные фрагменты (до 2 МБ каждый) могут набрать мегабайты.
        chunks = _split_by_size(findings, MAX_BATCH_SIZE_BYTES)
        total_batches = len(chunks)

        try:
            for batch_idx, chunk in enumerate(chunks, start=1):
                is_last = batch_idx == total_batches
                data = {
                    "findings": chunk,
                    "catalog_entries": catalog_entries if is_last else [],
                    "failed_files": failed_files if is_last else [],
                    "stats": stats if is_last else {},
                }
                params = {"batch": batch_idx, "total": total_batches}
                response = self.session.post(url, json=data, params=params, timeout=self.submit_timeout)
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"[SubmitResults] batch {batch_idx}/{total_batches}: {result.get('findings_count', 0)} findings saved")
                elif response.status_code in (404, 410):
                    # BUG-097: задание удалено в Manager (или истекло) — повтор
                    # не имеет смысла, задача потеряна безвозвратно.
                    logger.warning(
                        f"[SubmitResults] task {task_id} not found in Manager "
                        f"(HTTP {response.status_code}, scanner_id={self.scanner_id}) — "
                        "results dropped"
                    )
                    return SubmitStatus.LOST
                else:
                    logger.error(f"[SubmitResults] batch {batch_idx}/{total_batches} failed: {response.status_code}")
                    logger.error(f"[SubmitResults] response: {response.text[:200]}")
                    return SubmitStatus.RETRY
            return SubmitStatus.OK
        except Exception as e:
            logger.error(f"[SubmitResults] error: {e}")
            return SubmitStatus.RETRY
    
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

    def check_fingerprints(self, fingerprints: List[str]) -> Optional[Dict[str, Any]]:
        """Batch-проверка fingerprint'ов перед отправкой (день 40.2).

        Возвращает {"false_positives": [...], "confirmed": [...], "new": [...]}
        или None при недоступности эндпоинта (в этом случае фильтр отключается).
        """
        if not fingerprints:
            return {"false_positives": [], "confirmed": [], "new": []}

        # Чанками по 5000 — эндпоинт Manager принимает не более 10000 за запрос (день 40.2+)
        FP_CHUNK = 5000
        merged: Dict[str, Any] = {"false_positives": [], "confirmed": [], "new": []}
        url = f"{self.base_url}/api/findings/check-fingerprints"
        try:
            for i in range(0, len(fingerprints), FP_CHUNK):
                chunk = fingerprints[i:i + FP_CHUNK]
                response = self.session.post(
                    url,
                    json={"fingerprints": chunk},
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    data = response.json()
                    merged["false_positives"].extend(data.get("false_positives", []))
                    merged["confirmed"].extend(data.get("confirmed", []))
                    merged["new"].extend(data.get("new", []))
                else:
                    logger.warning(
                        "[CheckFingerprints] Failed (chunk %d): %s %s",
                        i // FP_CHUNK + 1,
                        response.status_code,
                        response.text[:200],
                    )
                    return None
            return merged
        except Exception as e:
            logger.warning("[CheckFingerprints] Error: %s", e)
            return None

    def fail_task(self, task_id: int, reason: str = "scanner aborted") -> bool:
        """BUG-034: уведомить Manager о прерывании задачи (Ctrl+C/stop)."""
        if self.scanner_id is None:
            return False
        url = f"{self.base_url}/api/scanner/tasks/{task_id}/fail"
        try:
            response = self.session.post(url, json={"reason": reason}, timeout=self.timeout)
            if response.status_code == 200:
                logger.info(f"[FailTask] Task {task_id} marked failed")
                return True
            logger.warning(f"[FailTask] Failed: {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"[FailTask] Error: {e}")
            return False


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
        # Событие остановки (день 42.5+): устанавливается из stop()/Ctrl+C,
        # проверяется параллельным scan_path для немедленной остановки.
        self._stop_event = threading.Event()
        # BUG-081 (TASK-052, v3.13.20): SIGINT → graceful shutdown.
        # Обработчик ставит флаги; цикл выходит корректно, stop() завершает
        # heartbeat и OCRWorker (Windows-совместимо — только SIGINT/SIGBREAK).
        try:
            signal.signal(signal.SIGINT, self._handle_sigint)
            if hasattr(signal, "SIGBREAK"):
                signal.signal(signal.SIGBREAK, self._handle_sigint)
        except (ValueError, OSError) as e:
            logger.debug("SIGINT handler not installed: %s", e)
        
        self.client = None
        self.classifiers = []
        self.heartbeat_thread: Optional[HeartbeatThread] = None
        # Построчный конвейер (день 40.2)
        self._connector: Optional[FilesystemConnector] = None
        # День 53.1b (BACKLOG-097): тип источника текущей задачи
        # (filesystem | s3 | minio) — из payload Manager.
        self._current_source_type: str = "filesystem"
        # День 53.2 (BACKLOG-097): scan_config текущей задачи (payload Manager).
        # Нужен в _init_line_pipeline для merge scan_config.connector.s3 —
        # там scan_config является локальной переменной.
        self._current_scan_config: Dict[str, Any] = {}
        self._enc = None
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
                        "quick_filter_enabled": pii_config.quick_filter_enabled,
                        "analyzer_pool_size": pii_config.analyzer_pool_size,  # 0 = авто
                        # 53.4l (v3.14.10): NER-категории (person/location/...)
                        "ner_enabled": getattr(pii_config, "ner_enabled", False),
                        "excluded_entities": getattr(pii_config, "excluded_entities", None),
                    }
                    if self.config and self.config.connector and pii_config.analyzer_pool_size <= 0:
                        pii_config_dict["max_parallel_files"] = (
                            getattr(self.config.connector, "max_parallel_files", None) or 4
                        )
                    # 53.4m (v3.14.11): в process-режиме файлы обрабатывают
                    # воркеры (там пул = 1), родитель не анализирует — не грузим
                    # лишние потоки Presidio.
                    if self._is_process_executor():
                        pii_config_dict["analyzer_pool_size"] = 1
                pii.configure(pii_config_dict)
                self.classifiers.append(pii)
                logger.info(f"[OK] PII Classifier loaded (OCR enabled: {pii_config_dict.get('ocr_enabled', True)})")
            
            if not cred_config or cred_config.enabled:
                cred = CredentialsClassifier()
                cred_config_dict = {}
                if cred_config:
                    cred_config_dict = {
                        "entropy_threshold": cred_config.entropy_threshold,
                        "min_length": cred_config.min_length,
                        "max_file_size_mb": cred_config.max_file_size_mb,
                        "strict_filter": cred_config.strict_filter,
                        "confidence_threshold": cred_config.confidence_threshold,
                        "no_generic": cred_config.no_generic,
                        "require_mixed": cred_config.require_mixed,
                    }
                cred.configure(cred_config_dict)
                self.classifiers.append(cred)
                logger.info(f"[OK] Credentials Classifier loaded")
            
            if not code_config or code_config.enabled:
                code = CodeClassifier()
                code_config_dict = {}
                if code_config:
                    code_config_dict = {
                        "max_file_size_mb": code_config.max_file_size_mb
                    }
                code.configure(code_config_dict)
                self.classifiers.append(code)
                logger.info(f"[OK] Code Classifier loaded")
            
            logger.info(f"[OK] Загружено {len(self.classifiers)} классификаторов")
            
        except Exception as e:
            logger.error(f"[ERROR] Ошибка загрузки классификаторов: {e}")
    
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
        
        logger.error("[Register] [ERROR] Registration failed")
        return False
    
    def _get_connector_config(self) -> Dict[str, Any]:
        if self.config and self.config.connector:
            return {
                "extensions": self.config.connector.extensions,
                "max_file_size_mb": self.config.connector.max_file_size_mb or 500,
                "recursive": self.config.connector.recursive,
                "skip_dirs": self.config.connector.skip_dirs,
                "buffer_size": self.config.connector.buffer_size,
                "max_text_chars": self.config.connector.max_text_chars,
                "context_lines": self.config.connector.context_lines,
                "max_parallel_files": getattr(self.config.connector, "max_parallel_files", 1) or 1,
                # 53.4m (v3.14.11): режим исполнения и размер пула воркеров
                "performance": self._get_performance_dict(),
            }
        return {
            "extensions": ["*"],
            "max_file_size_mb": 500,
            "recursive": True,
            "skip_dirs": ["$Recycle.Bin", "System Volume Information", "tmp", "temp", "cache", "__pycache__", "node_modules", "venv", "logs", ".git"],
            "buffer_size": 1024 * 1024,
            "max_text_chars": 200000,
            "context_lines": 2,
            "max_parallel_files": 1,
            "performance": self._get_performance_dict(),
        }

    def _get_performance_dict(self) -> Dict[str, Any]:
        """Секция performance для коннектора (53.4m, v3.14.11)."""
        perf = getattr(self.config, "performance", None) if self.config else None
        if perf is None:
            return {}
        return {
            "max_parallel_files": getattr(perf, "max_parallel_files", 8),
            "executor": getattr(perf, "executor", "process"),
            "max_workers": getattr(perf, "max_workers", 4),
            "chunk_size": getattr(perf, "chunk_size", 100),
        }

    def _is_process_executor(self) -> bool:
        """True, если файлы обрабатываются ProcessPoolExecutor (53.4m)."""
        return str(self._get_performance_dict().get("executor") or "").lower() == "process"
    
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

    def _parent_of_path(self, file_path: str) -> str:
        """Родительская папка файла (поддерживает FS-пути и s3://bucket/key).

        Path('s3://bucket/key').parent даст 's3:/bucket' — сломано. Для s3://
        используем urlparse + posixpath.dirname.
        """
        if not file_path:
            return ""
        if file_path.startswith(("s3://", "minio://")):
            from urllib.parse import urlparse
            import posixpath
            parsed = urlparse(file_path)
            parent_dir = posixpath.dirname(parsed.path.lstrip("/"))
            bucket = parsed.netloc
            if parent_dir:
                return f"{parsed.scheme}://{bucket}/{parent_dir}"
            return f"{parsed.scheme}://{bucket}"
        return str(Path(file_path).parent)

    def _collect_catalog_entries(self, resource_path: str, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Собрать записи каталога - папки, в которых есть находки."""
        catalog_entries = {}
        
        for finding in findings:
            file_path = finding.get("file_path", "")
            if not file_path:
                continue
            
            folder_path = self._parent_of_path(file_path)
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
    
    def _init_line_pipeline(self) -> bool:
        """Инициализация построчного конвейера (день 40.2).

        Загружает шифрование (по ключам), строит коннектор через фабрику
        (день 53.1b — по source_type задачи).
        Возвращает True, если есть классификаторы со scan_line.
        """
        line_capable = [
            c for c in self.classifiers if hasattr(c, "scan_line")
        ]
        if not line_capable:
            logger.warning("[LineScan] Нет классификаторов с scan_line — построчный конвейер недоступен")
            return False

        self._enc = get_encryption()

        connector_cfg = self._get_connector_config()
        # TASK-029 (BUG-067c): OCR-ключ берём из classifiers.pii.ocr_enabled,
        # потому что в connector-секции его нет (день 46.7).
        pii_cfg = None
        if self.config is not None and self.config.classifiers is not None:
            pii_cfg = getattr(self.config.classifiers, "pii", None)
        ocr_enabled = bool(
            getattr(pii_cfg, "ocr_enabled", True)
            if pii_cfg is not None
            else True
        )
        connector_cfg["ocr_enabled"] = ocr_enabled
        # День 53.2 (BACKLOG-097): для S3/MinIO параметры endpoint/bucket/prefix
        # приходят в payload задачи (scan_config.connector.s3). Мержим поверх
        # локального конфига — приоритет у payload (per-task конфиг).
        self._current_scan_config = self._current_scan_config or {}
        s3_payload = (
            self._current_scan_config.get("connector", {}).get("s3", {}) or {}
        )
        if s3_payload:
            connector_cfg.update(s3_payload)
        # День 53.1b/53.2 (BACKLOG-097): коннектор выбирается по source_type
        # задачи через фабрику (filesystem | s3 | minio).
        try:
            self._connector = create_line_connector(self._current_source_type, connector_cfg)
            logger.info(
                "[LineScan] Connector created: source_type=%s, type=%s",
                self._current_source_type,
                type(self._connector).__name__,
            )
        except ValueError as exc:
            logger.error("[LineScan] %s", exc)
            self._connector = None
            return False

        logger.info(
            "[LineScan] Построчный конвейер готов: %d классификаторов, keys=%s",
            len(line_capable),
            "enabled" if self._enc else "disabled (legacy)",
        )
        return True

    def _legacy_fingerprint(self, file_path: str, line: int, match: str, finding_type: str) -> str:
        """
        Fingerprint БЕЗ HMAC (legacy-режим, когда ключей нет).

        Важно: SHA-256 с полным контекстом (file_path + line + match + type) —
        уменьшает коллизии; слабые 32-hex дайджесты не используются.
        """
        import hashlib

        msg = f"{file_path}|{line}|{match}|{finding_type}".encode("utf-8")
        return hashlib.sha256(msg).hexdigest()

    def _serialize_finding(self, finding: Finding, resource_path: str,
                           all_findings_in_line: Optional[List[Finding]] = None,
                           line_text: Optional[str] = None) -> Dict[str, Any]:
        """Сериализация находки для Manager (новый формат, день 40.2).

        При включённом шифровании открытый текст НЕ покидает хост:
        передаются encrypted + masked версии value/line/context.
        """
        enc = self._enc
        fpath = finding.fragment_path or resource_path
        cat = finding.category or "unknown"
        value = finding.match_text or ""
        line_text = finding.line_text or ""
        ctx_before = finding.context_before or ""
        ctx_after = finding.context_after or ""

        # BUG-022: маскируем ВСЕ PII в строке, а не только своей категории.
        positions = [
            (f.start_pos, f.end_pos, f.category or cat)
            for f in (all_findings_in_line or [finding])
            if f.start_pos is not None and f.end_pos is not None
        ]
        if not positions:
            positions = [(finding.start_pos, finding.end_pos, cat)]
        line_no = int(finding.line_number or 0)

        d: Dict[str, Any] = {
            "file_path": fpath,
            "line_number": line_no,
            "category": cat,
            "subcategory": finding.category,
            "finding_type": finding.finding_type,
            "value": value if enc is None else "(encrypted)",
            "confidence": finding.confidence or 1.0,
            "severity": finding.severity or "medium",
            "detector": finding.detector or "regex",
            "context": line_text if enc is None else None,
            "start_pos": finding.start_pos,
            "end_pos": finding.end_pos,
            "fragment_type": finding.fragment_type,
            "bounding_box": finding.bounding_box,
            "byte_offset": finding.byte_offset,
            "byte_length": finding.byte_length,
            "hex_preview": finding.hex_preview,
            **_embed_fragment(finding),  # BACKLOG-086 (TASK-046)
        }
        if getattr(finding, "metadata", None):
            d["metadata"] = finding.metadata

        if enc is not None:
            d["fingerprint"] = enc.fingerprint(fpath, line_no, value, finding.finding_type)
            d["match_text_encrypted"] = enc.encrypt(value) if value else None
            d["match_text_masked"] = mask(value, cat) if value else None
            d["line_text_encrypted"] = enc.encrypt(line_text) if line_text else None
            d["line_text_masked"] = mask_line(line_text, positions) if line_text else None
            d["context_before_masked"] = mask_context(ctx_before, cat) if ctx_before else None
            d["context_after_masked"] = mask_context(ctx_after, cat) if ctx_after else None
            d["encryption_key_id"] = enc.key_id
            d["legacy_fingerprint"] = self._legacy_fingerprint(fpath, line_no, value, finding.finding_type)
        else:
            d["fingerprint"] = None
            d["match_text_masked"] = mask(value, cat) if value else None
            d["line_text_masked"] = mask_line(line_text, positions) if line_text else None
            d["context_before_masked"] = mask_context(ctx_before, cat) if ctx_before else None
            d["context_after_masked"] = mask_context(ctx_after, cat) if ctx_after else None

        return d

    def _filter_false_positives(self, serialized: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Batch-фильтр FP через check-fingerprints (день 40.2).

        Находки с fingerprint, отмеченные как false_positive (или уже confirmed),
        НЕ отправляются в Manager. Если эндпоинт недоступен (старый Manager) —
        отправляем как раньше (backward compat).
        """
        if not serialized:
            return serialized

        fps = [d.get("fingerprint") for d in serialized if d.get("fingerprint")]
        if not fps:
            return serialized

        try:
            result = self.client.check_fingerprints(fps) if self.client else None
        except Exception as e:
            logger.warning("[FPFilter] check-fingerprints error: %s", e)
            result = None

        if not result:
            return serialized

        skip = set(result.get("false_positives", [])) | set(result.get("confirmed", []))

        filtered = [d for d in serialized if d.get("fingerprint") not in skip]
        if len(filtered) != len(serialized):
            logger.info(
                "[FPFilter] Отфильтровано %d находок (FP/confirmed)",
                len(serialized) - len(filtered),
            )
        return filtered

    def _scan_line_by_line(self, resource_path: str) -> Dict[str, Any]:
        """Построчное сканирование каталога (день 40.2).

        Возвращает {"findings": [...], "files_scanned": int, "error": str|None}.
        """
        line_capable = [c for c in self.classifiers if hasattr(c, "scan_line")]

        # счётчик обработанных файлов для stats
        scanned = [0]
        # тайминги для консольного прогресса (День 40.x: скорость + ETA)
        start_time = [time.time()]
        last_report = [0.0]
        report_interval = self._progress_report_interval()

        def _fmt_eta(seconds: Optional[float]) -> str:
            if seconds is None or not math_isfinite(seconds) or seconds <= 0:
                return "—"
            s = int(seconds)
            h, rem = divmod(s, 3600)
            m, _ = divmod(rem, 60)
            if h:
                return f"{h}ч {m}м"
            return f"{m}м"

        def _fmt_speed(speed: float) -> str:
            if not math_isfinite(speed) or speed < 0:
                return "—"
            if speed < 1:
                return f"{speed * 60:.1f} ф/мин"
            return f"{speed:.1f} ф/с"

        def _report(current: int, total: int):
            elapsed = time.time() - start_time[0]
            speed = current / elapsed if elapsed > 0 else 0.0
            rate = speed if speed > 0 else 0.0
            eta = (total - current) / rate if rate > 0 else None
            if self.heartbeat_thread is not None:
                try:
                    self.heartbeat_thread.set_progress(current, total, speed, int(eta) if eta else None)
                except Exception:
                    pass
            if total:
                pct = (current / total) * 100 if total else 0.0
                logger.info(
                    "[ScanProgress] %s%d/%d (%.1f%%) | скорость %s | ETA %s",
                    " ",
                    current,
                    total,
                    pct,
                    _fmt_speed(speed),
                    _fmt_eta(eta),
                )
            else:
                logger.info(
                    "[ScanProgress] %d файлов | скорость %s | прошло %.0fс",
                    current,
                    _fmt_speed(speed),
                    elapsed,
                )

        def _progress(stage: int, current: int, total: int, file_path: str):
            if stage == 1:
                scanned[0] = current
                now = time.time()
                if now - last_report[0] >= report_interval:
                    last_report[0] = now
                    _report(current, total)
                elif self.heartbeat_thread is not None:
                    # между консольными отчётами всё равно обновляем heartbeat в фоне
                    try:
                        elapsed = time.time() - start_time[0]
                        speed = current / elapsed if elapsed > 0 else 0.0
                        eta = (total - current) / speed if speed > 0 else None
                        self.heartbeat_thread.set_progress(current, total, speed, int(eta) if eta else None)
                    except Exception:
                        pass

        findings = self._connector.scan_path(
            resource_path,
            line_capable,
            progress_callback=_progress,
            stop_event=self._stop_event,
        )
        # финальный отчёт с общей скоростью
        _report(scanned[0], scanned[0])
        return {
            "findings": findings,
            "files_scanned": scanned[0],
            "error": None,
        }

    def _progress_report_interval(self) -> float:
        """Интервал консольного отчёта о прогрессе (по умолчанию 5 сек)."""
        try:
            if self.config and self.config.scanner:
                v = getattr(self.config.scanner, "progress_report_interval", None)
                if v is not None and v > 0:
                    return float(v)
        except Exception:
            pass
        return 5.0

    def _update_metrics(self, stats: Dict[str, Any]):
        """Инкремент Prometheus-метрик после завершения задания (День 39)."""
        sid = str(self.scanner_id)
        try:
            files = int(stats.get("files_scanned", 0) or 0)
            if files:
                scanner_metrics.files_scanned.labels(scanner_id=sid).inc(files)

            total_findings = int(stats.get("total_findings", 0) or 0)
            if total_findings:
                scanner_metrics.findings.labels(scanner_id=sid, type="total").inc(total_findings)

            category_stats = stats.get("category_stats") or {}
            for cat, count in category_stats.items():
                if count:
                    scanner_metrics.findings.labels(scanner_id=sid, type=str(cat)).inc(int(count))

            failed = int(stats.get("files_failed", 0) or 0)
            if failed:
                scanner_metrics.scan_errors.labels(scanner_id=sid, error_type="files_failed").inc(failed)
        except Exception as e:
            logger.debug("Metrics update error: %s", e)

    def _execute_task_linewise(self, task: Dict[str, Any], resource_path: str,
                               scan_config: Dict[str, Any]) -> Dict[str, Any]:
        """Построчное исполнение задания (день 40.2).

        Использует FilesystemConnector + scan_line классификаторов,
        шифрует/маскирует находки, фильтрует FP через check-fingerprints.
        """
        task_id = task["id"]

        if self.heartbeat_thread is not None:
            self.heartbeat_thread.set_task(task_id)
            self.heartbeat_thread.set_progress(0, None)

        logger.info(
            "[Scanner] Построчное сканирование %s (task %d, source_type=%s)",
            resource_path, task_id, self._current_source_type,
        )

        scan_result = self._scan_line_by_line(resource_path)
        findings_objects = scan_result["findings"]

        # Мгновенная остановка: если stop_event выставлен после скана —
        # НЕ сериализуем/шифруем находки и НЕ шлём FP-фильтр (день 40.2+).
        if self._should_exit or self._stop_event.is_set():
            logger.warning(
                f"[Scanner] Task {task_id} прервана при остановке — "
                f"post-processing пропущен ({len(findings_objects)} находок не сериализованы)"
            )
            return {
                "findings": [],
                "catalog_entries": [],
                "failed_files": [],
                "stats": {
                    "files_scanned": int(scan_result.get("files_scanned", 0) or 0),
                    "files_failed": 0,
                    "files_with_findings": 0,
                    "total_findings": 0,
                    "unique_findings": 0,
                    "category_stats": {},
                    "started_at": task.get("assigned_at", datetime.utcnow().isoformat()),
                    "completed_at": datetime.utcnow().isoformat(),
                    "encryption": "enabled" if self._enc else "legacy",
                    "aborted": True,
                },
            }

        # Сериализация в новый формат (шифрование/маскирование на хосте)
        # BUG-022: группируем находки по строке и маскируем ВСЕ PII строки,
        # а не только своей категории.
        findings_by_line: dict = {}
        for _f in findings_objects:
            _key = (_f.fragment_path or resource_path, int(_f.line_number or 0))
            findings_by_line.setdefault(_key, []).append(_f)

        serialized = [
            self._serialize_finding(
                f,
                resource_path,
                all_findings_in_line=findings_by_line[
                    (f.fragment_path or resource_path, int(f.line_number or 0))
                ],
            )
            for f in findings_objects
        ]

        # Batch FP-фильтр: FP/confirmed не отправляем
        serialized = self._filter_false_positives(serialized)

        failed_files: List[Dict[str, Any]] = []
        if scan_result.get("error"):
            failed_files.append({
                "path": resource_path,
                "error": scan_result["error"],
                "error_type": "scan",
            })

        files_scanned = int(scan_result.get("files_scanned", 0) or 0)
        files_with_findings = {
            d.get("file_path", "") for d in serialized if d.get("file_path")
        }
        category_stats: Dict[str, int] = {}
        for d in serialized:
            ft = d.get("finding_type", "unknown")
            category_stats[ft] = category_stats.get(ft, 0) + 1

        stats: Dict[str, Any] = {
            "files_scanned": files_scanned,
            "files_failed": len(failed_files),
            "files_with_findings": len(files_with_findings),
            "total_findings": len(serialized),
            "unique_findings": len(serialized),
            "category_stats": category_stats,
            "started_at": task.get("assigned_at", datetime.utcnow().isoformat()),
            "completed_at": datetime.utcnow().isoformat(),
            "encryption": "enabled" if self._enc else "legacy",
        }

        catalog_entries = self._collect_catalog_entries(resource_path, serialized)

        self._update_metrics(stats)

        logger.info(f"[Scanner] Task {task_id} completed (linewise):")
        logger.info(f"  - Files scanned: {stats['files_scanned']}")
        logger.info(f"  - Files with findings: {stats['files_with_findings']}")
        logger.info(f"  - Total findings: {stats['total_findings']}")
        logger.info(f"  - Folders with findings: {len(catalog_entries)}")
        logger.info(f"  - Failed files: {stats['files_failed']}")

        if serialized:
            logger.info("[Scanner] Sample findings (first 5):")
            for i, d in enumerate(serialized[:5]):
                logger.info(
                    f"  {i + 1}. [{d.get('finding_type')}/{d.get('category')}] "
                    f"{d.get('file_path', '')}:{d.get('line_number', '')}"
                )

        return {
            "findings": serialized,
            "catalog_entries": catalog_entries,
            "failed_files": failed_files,
            "stats": stats,
        }

    def _execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task["id"]
        resource_path = task["path"]
        scan_config = task.get("scan_config", {})
        
        # День 53.1b (BACKLOG-097): тип источника из payload Manager.
        # Fallback на filesystem — если задача создана до 53.1a.
        self._current_source_type = (task.get("source_type") or "filesystem").lower()
        # День 53.2 (BACKLOG-097): scan_config приходит per-task, а
        # _init_line_pipeline вызывается из _execute_task_linewise, где
        # scan_config — локальная переменная. Сохраняем в поле.
        self._current_scan_config = scan_config or {}
        # Коннектор пересоздаём на каждой задаче: дешёво (только конфиг) и
        # исключает переиспользование коннектора от другого source_type.
        self._connector = None

        logger.info(
            f"[Scanner] Executing task {task_id} on {resource_path} "
            f"(source_type={self._current_source_type})"
        )
        
        collector = FindingCollector()
        collector_config = self._get_collector_config()
        collector.configure(collector_config)
        collector.start_collection()
        
        orchestrator = None
        connector = None
        progress_poller = None
        
        try:
            # ===== День 40.2: построчный конвейер — приоритетный путь =====
            if self._connector is None:
                self._init_line_pipeline()
            if self._connector is not None:
                scanner_metrics.set_current_task(self.scanner_id, task_id)
                return self._execute_task_linewise(task, resource_path, scan_config)

            # ===== Fallback: классический конвейер (Orchestrator) =====
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
                    "failed_files": [{"path": resource_path, "error": "No files found", "error_type": "connection"}],
                    "stats": {"files_scanned": 0, "files_failed": 1, "total_findings": 0}
                }
            
            # Прогресс + метрики перед сканированием (День 39)
            if self.heartbeat_thread is not None:
                self.heartbeat_thread.set_task(task_id)
                self.heartbeat_thread.set_progress(0, len(test_files))
                progress_poller = ProgressPoller(
                    orchestrator_config["state_file"],
                    len(test_files),
                    self.heartbeat_thread,
                )
                progress_poller.start()
            scanner_metrics.set_current_task(self.scanner_id, task_id)
            
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
            
            self._update_metrics(stats)
            
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
            
            self._update_metrics(results.get("stats", {}))
            
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
            if progress_poller is not None:
                progress_poller.stop()
            if self.heartbeat_thread is not None:
                self.heartbeat_thread.set_task(None)
                self.heartbeat_thread.set_progress(0)
            try:
                scanner_metrics.clear_current_task(self.scanner_id)
            except Exception:
                pass
            if orchestrator:
                try:
                    if hasattr(orchestrator, 'stop'):
                        orchestrator.stop()
                except Exception as e:
                    logger.debug(f"Error stopping orchestrator: {e}")
    
    def _get_offline_dir(self) -> Path:
        """Директория для оффлайн-режима (scanner/data/offline)"""
        offline_dir = Path("scanner") / "data" / "offline"
        offline_dir.mkdir(parents=True, exist_ok=True)
        return offline_dir

    def _save_offline(self, task_id: int, result: Dict[str, Any]) -> bool:
        """Сохранить результат задания в оффлайн-хранилище при недоступности Manager"""
        try:
            offline_dir = self._get_offline_dir()
            payload = {
                "task_id": task_id,
                "scanner_id": self.scanner_id,
                "saved_at": datetime.utcnow().isoformat(),
                "result": result
            }
            file_path = offline_dir / f"task_{task_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info(f"[Offline] Результаты задания {task_id} сохранены: {file_path}")
            return True
        except Exception as e:
            logger.error(f"[Offline] Ошибка сохранения результатов: {e}")
            return False

    def _flush_offline(self) -> int:
        """Попытаться отправить сохранённые оффлайн-результаты в Manager.

        Возвращает количество успешно отправленных заданий.

        BUG-097 (TASK-066, v3.13.25): если Manager больше не знает задание
        (404/410 — задача удалена вручную, очищена E2E-фикстурой или
        удалена политикой хранения), пачка отбрасывается, а не ретраится
        бесконечно. Раньше такой файл ждал своей очереди часами, засоряя
        лог 404-ошибками на каждом цикле main().
        """
        offline_dir = self._get_offline_dir()
        flushed = 0
        for file_path in sorted(offline_dir.glob("task_*.json")):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    payload = json.load(f)
                task_id = payload["task_id"]
                result = payload.get("result", {})

                status = self.client.submit_results_status(
                    task_id=task_id,
                    findings=result.get("findings", []),
                    catalog_entries=result.get("catalog_entries", []),
                    failed_files=result.get("failed_files", []),
                    stats=result.get("stats", {})
                )
                if status == SubmitStatus.OK:
                    file_path.unlink()
                    flushed += 1
                    logger.info(f"[Offline] Задание {task_id} отправлено из оффлайн-очереди")
                elif status == SubmitStatus.LOST:
                    file_path.unlink()
                    logger.warning(
                        f"[Offline] Задание {task_id} удалено в Manager — "
                        "оффлайн-пачка отброшена"
                    )
                else:
                    logger.warning(f"[Offline] Не удалось отправить задание {task_id} из очереди")
                    break
            except Exception as e:
                logger.error(f"[Offline] Ошибка обработки {file_path}: {e}")
                break
        return flushed

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
        print("[X] DCAP MANAGED SCANNER (REST API)")
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
            logger.error("[ERROR] Ошибка регистрации сканера")
            return
        
        logger.info(f"[X] Сканер {self.name} запущен (ID: {self.scanner_id})")
        
        self.client.heartbeat(status="idle")
        
        # Метрики на :9101 (fail-open) + выделенный поток heartbeat (День 39)
        scanner_metrics.start_metrics_server(self.scanner_id, port=9101)
        self.heartbeat_thread = HeartbeatThread(
            manager_url=self.manager_url,
            scanner_id=self.scanner_id,
            interval=30,
        )
        self.heartbeat_thread.start()
        
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
                    logger.warning("[WARN] Heartbeat не удался после 3 попыток")

                # Попытка отправить накопленные оффлайн-результаты
                if heartbeat_ok:
                    self._flush_offline()

                task = self.client.get_task()
                
                if task:
                    self.client.heartbeat(status="busy", task_id=task["id"])
                    
                    # BUG-097 (TASK-066, v3.13.25): раньше исключение внутри
                    # _execute_task гасилось внешним except, и задание оставалось
                    # в статусе assigned до срабатывания stale-таймаута Manager
                    # (TASK_TIMEOUT_MINUTES = 30) — очередь вставала, все
                    # последующие задания копились в assigned. Теперь задание
                    # сразу переводится в failed, а причина логируется со стеком.
                    try:
                        result = self._execute_task(task)
                    except Exception as e:
                        logger.exception(
                            f"[ERROR] Task {task['id']} failed during execution: {e}"
                        )
                        self._fail_task_safely(task["id"], f"scanner error: {e}")
                        self.client.heartbeat(status="idle")
                        continue
                    
                    if self._should_exit or self._stop_event.is_set():
                        logger.warning("[STOP] Задача прервана пользователем — уведомляем Manager")
                        try:
                            self.client.fail_task(task["id"], reason="scanner aborted (Ctrl+C)")
                        except Exception as e:
                            logger.error(f"[STOP] Не удалось уведомить Manager: {e}")
                        break
                    
                    submit_status = self.client.submit_results_status(
                        task_id=task["id"],
                        findings=result.get("findings", []),
                        catalog_entries=result.get("catalog_entries", []),
                        failed_files=result.get("failed_files", []),
                        stats=result.get("stats", {})
                    )
                    
                    if submit_status == SubmitStatus.OK:
                        logger.info(f"[OK] Task {task['id']} completed successfully")
                    elif submit_status == SubmitStatus.LOST:
                        # BUG-097: задание удалено в Manager — оффлайн-пачку не
                        # создаём, иначе получим вечный цикл 404.
                        logger.warning(
                            f"[WARN] Task {task['id']} удалён в Manager — результаты отброшены"
                        )
                    else:
                        logger.error(f"[ERROR] Failed to submit results for task {task['id']}")
                        self._save_offline(task["id"], result)
                    
                    self.client.heartbeat(status="idle")
                else:
                    time.sleep(self.interval)
                    
            except KeyboardInterrupt:
                logger.warning("[STOP] Ctrl+C — задача прервана, уведомляем Manager")
                try:
                    if "task" in locals() and task:
                        self.client.fail_task(task["id"], reason="scanner aborted (Ctrl+C)")
                except Exception as e:
                    logger.error(f"[STOP] Не удалось уведомить Manager: {e}")
                break
            except Exception as e:
                logger.error(f"[ERROR] Ошибка в основном цикле: {e}")
                time.sleep(5)
        
        self.client.heartbeat(status="offline")
        if self.heartbeat_thread is not None:
            self.heartbeat_thread.stop()
        self._shutdown_classifiers()
        logger.info("[X] Сканер остановлен")

    def _fail_task_safely(self, task_id: int, reason: str) -> bool:
        """Сообщить Manager об ошибке задания, не роняя основной цикл.

        BUG-097 (TASK-066, v3.13.25): без этого задание оставалось в статусе
        assigned и блокировало очередь на TASK_TIMEOUT_MINUTES.
        """
        try:
            ok = self.client.fail_task(task_id, reason=reason)
            if ok:
                logger.info(f"[Task] Task {task_id} marked as failed: {reason}")
            else:
                logger.warning(f"[Task] Не удалось перевести задание {task_id} в failed")
            return ok
        except Exception as e:
            logger.error(f"[Task] Ошибка при переводе задания {task_id} в failed: {e}")
            return False

    def _shutdown_classifiers(self):
        """Корректное завершение классификаторов (OCRWorker и др. процессы) —
        иначе после остановки сканера остаются осиротевшие дочерние процессы.
        Идемпотентно (PiiClassifier._stop_ocr_worker имеет guard _ocr_started).
        """
        for clf in self.classifiers:
            shutdown = getattr(clf, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown()
                except Exception as e:
                    logger.debug("Classifier shutdown error %s: %s", getattr(clf, "classifier_name", clf), e)

    def _handle_sigint(self, signum, frame):
        """BUG-081 (TASK-052): SIGINT → graceful shutdown (Windows-совместимо)."""
        logger.warning("[Scanner] SIGINT received, stopping...")
        self._should_exit = True
        self._stop_event.set()

    def stop(self):
        """Graceful shutdown — вызывается из SIGINT-handler, KeyboardInterrupt или извне.

        BUG-081 (TASK-052): останавливает heartbeat, затем классификаторы
        (OCRWorker): None в request_queue → join(5) → terminate → join(2) → kill.
        """
        logger.info("[Scanner] Stopping...")
        self._should_exit = True
        self._stop_event.set()

        logger.info("[Scanner] Stopping heartbeat...")
        if self.heartbeat_thread is not None:
            try:
                self.heartbeat_thread.stop()
            except Exception as e:
                logger.debug("Heartbeat stop error: %s", e)

        logger.info("[Scanner] Stopping OCRWorker/classifiers...")
        self._shutdown_classifiers()

        logger.info("[Scanner] Stopped")


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
        print("\n[STOP] Прервано пользователем")
    finally:
        scanner.stop()


if __name__ == "__main__":
    main()