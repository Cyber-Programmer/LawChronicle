# Common types and models for LawChronicle Web Application

from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from enum import Enum

# Enums
class PhaseStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class ProcessingStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"

# Base models
class BaseResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=50, ge=1, le=1000)
    sort_by: Optional[str] = None
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    limit: int
    pages: int

# Phase-specific models
class PhaseMetadata(BaseModel):
    phase: int
    status: PhaseStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    total_items: int = 0
    processed_items: int = 0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class BatchProcessingConfig(BaseModel):
    batch_size: int = Field(default=100, ge=1, le=10000)
    max_workers: int = Field(default=4, ge=1, le=16)
    timeout_seconds: int = Field(default=300, ge=60, le=3600)
    retry_attempts: int = Field(default=3, ge=0, le=10)

class ProcessingResult(BaseModel):
    success: bool
    processed_count: int
    error_count: int
    warning_count: int
    duration_seconds: float
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

# Database models
class StatuteBase(BaseModel):
    statute_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RawStatute(StatuteBase):
    raw_data: Dict[str, Any]
    field_coverage: Dict[str, float]
    metadata: Dict[str, Any]

class NormalizedStatute(StatuteBase):
    normalized_name: str
    original_name: str
    fields: Dict[str, Any]
    validation_status: str

class CleanedStatute(StatuteBase):
    cleaned_fields: Dict[str, Any]
    duplicate_count: int
    section_count: int
    cleaning_metadata: Dict[str, Any]

class DateEnrichedStatute(StatuteBase):
    date_fields: Dict[str, Any]
    date_coverage: float
    confidence_scores: Dict[str, float]
    extraction_method: str

class VersionedStatute(StatuteBase):
    base_name: str
    version: str
    group_id: str
    similarity_score: float
    versioning_metadata: Dict[str, Any]

class SectionVersion(StatuteBase):
    section_id: str
    statute_name: str
    section_content: str
    version: str
    parent_version: Optional[str] = None
    section_metadata: Dict[str, Any]

# API request/response models
class DatabaseConnectionRequest(BaseModel):
    connection_string: str
    database_name: str
    test_connection: bool = True

class DatabaseConnectionResponse(BaseModel):
    connected: bool
    database_name: str
    collection_count: int
    total_documents: int
    collections: List[str]

class FieldAnalysisRequest(BaseModel):
    collection_name: str
    sample_size: int = Field(default=100, ge=1, le=10000)

class FieldAnalysisResponse(BaseModel):
    collection_name: str
    total_documents: int
    field_coverage: Dict[str, float]
    unique_values: Dict[str, List[str]]
    sample_data: List[Dict[str, Any]]

# WebSocket models
class WebSocketMessage(BaseModel):
    type: str
    data: Any
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProgressUpdate(BaseModel):
    phase: int
    progress: float
    status: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
