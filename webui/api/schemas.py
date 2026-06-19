from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

# === SCHEMAS ===

class FindingResponse(BaseModel):
    id: int
    file_path: str
    classifier_name: str
    category: str
    subcategory: Optional[str]
    value: Optional[str]
    confidence: float
    task_id: int
    scanner_id: int
    
    class Config:
        from_attributes = True

class TaskResponse(BaseModel):
    id: int
    resource_id: int
    scanner_id: Optional[int]
    status: str
    files_scanned: int
    findings_count: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class ScannerResponse(BaseModel):
    id: int
    name: str
    endpoint: str
    status: str
    last_heartbeat: datetime
    total_files_scanned: int
    total_findings: int
    
    class Config:
        from_attributes = True

class ResourceResponse(BaseModel):
    id: int
    type: str
    path: str
    enabled: bool
    config: Optional[Dict]
    
    class Config:
        from_attributes = True

class StatsResponse(BaseModel):
    total_findings: int
    active_scanners: int
    pending_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_files_scanned: int
    findings_by_category: Dict[str, int]
    findings_by_scanner: Dict[str, int]
    tasks_by_status: Dict[str, int]