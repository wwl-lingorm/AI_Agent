# [file name]: web_app/schemas.py
# [file content begin]
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class AnalysisRequest(BaseModel):
    repo_path: str
    preferred_model: Optional[str] = "deepseek"

class TaskResponse(BaseModel):
    id: str
    repo_path: str
    preferred_model: str
    status: TaskStatus
    created_at: str
    completed_at: Optional[str] = None
    progress: int = 0
    current_step: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class SystemStatus(BaseModel):
    status: str
    agents_initialized: bool
    available_models: List[str]
    active_tasks: int
    total_tasks: int

class WebSocketMessage(BaseModel):
    type: str
    task_id: Optional[str] = None
    progress: Optional[int] = None
    message: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
# [file content end]