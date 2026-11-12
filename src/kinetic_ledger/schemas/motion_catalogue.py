from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class MotionSemanticsBase(BaseModel):
    intent: str
    semantic_attributes: Optional[Dict[str, Any]] = None

class MotionSemanticsResponse(MotionSemanticsBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

class CaptureContractBase(BaseModel):
    accepted_file_formats: List[str]
    fps_requirements: int
    min_duration_sec: Optional[int] = None
    max_duration_sec: Optional[int] = None
    capture_quality_requirements: Optional[Dict[str, Any]] = None

class CaptureContractResponse(CaptureContractBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

class MotionDefinitionBase(BaseModel):
    motion_code: str
    name: str
    description: Optional[str] = None
    category: str
    version: str

class MotionDefinitionCreate(MotionDefinitionBase):
    semantics: MotionSemanticsBase
    capture_contract: CaptureContractBase

class MotionDefinitionResponse(MotionDefinitionBase):
    motion_definition_id: UUID
    status: str
    catalogue_id: UUID
    semantics: Optional[MotionSemanticsResponse] = None
    capture_contract: Optional[CaptureContractResponse] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class MotionCatalogueCreate(BaseModel):
    version: str
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

class MotionCatalogueResponse(BaseModel):
    catalogue_id: UUID
    version: str
    status: str
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    definitions: List[MotionDefinitionResponse] = []
    model_config = ConfigDict(from_attributes=True)
