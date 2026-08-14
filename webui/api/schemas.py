from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

# ==================== ОБЩИЕ ====================

class StatsResponse(BaseModel):
    total_findings: int
    active_scanners: int
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_files_scanned: int
    total_resources: int
    findings_by_category: Dict[str, int]
    findings_by_scanner: Dict[str, int]
    tasks_by_status: Dict[str, int]


# ==================== НАХОДКИ ====================

class FindingResponse(BaseModel):
    id: int
    file_path: str
    file_hash: Optional[str]
    file_size: int
    file_modified: Optional[datetime]
    classifier_name: str
    category: str
    subcategory: str
    value: str
    confidence: float
    detection_method: str
    context: Optional[str]
    task_id: int
    scanner_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== ЗАДАНИЯ ====================

class TaskResponse(BaseModel):
    id: int
    resource_id: int
    scanner_id: Optional[int]
    status: str
    files_total: int
    files_scanned: int
    findings_count: int
    created_at: datetime
    assigned_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress_percent: Optional[float] = 0.0
    resource_path: Optional[str] = None
    scanner_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class CreateTaskRequest(BaseModel):
    resource_path: str
    resource_type: str = "FILESYSTEM"
    extensions: Optional[str] = "txt,pdf,docx,xlsx,png,jpg,jpeg"
    max_file_size_mb: Optional[int] = 50
    recursive: bool = True


# ==================== СКАНЕРЫ ====================

class ScannerResponse(BaseModel):
    id: int
    name: str
    endpoint: str
    status: str
    last_heartbeat: Optional[datetime]
    total_files_scanned: int
    total_findings: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== РЕСУРСЫ ====================

class ResourceResponse(BaseModel):
    id: int
    type: str
    path: str
    enabled: bool
    config: Optional[Dict[str, Any]]
    last_scan_start: Optional[datetime]
    last_scan_end: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class CreateResourceRequest(BaseModel):
    type: str = "FILESYSTEM"
    path: str
    enabled: bool = True
    extensions: Optional[str] = "txt,pdf,docx,xlsx,png,jpg,jpeg"
    max_file_size_mb: Optional[int] = 50
    recursive: bool = True


class UpdateResourceRequest(BaseModel):
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


# ==================== УПРАВЛЕНИЕ ДОСТУПОМ ====================

class UpdateAlertStatusRequest(BaseModel):
    status: str  # open, acknowledged, resolved, ignored