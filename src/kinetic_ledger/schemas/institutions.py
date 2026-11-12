from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class TVETInstitutionCreate(BaseModel):
    institution_code: str
    name: str

class TVETInstitutionUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None

class TVETInstitutionResponse(BaseModel):
    institution_id: UUID
    institution_code: str
    name: str
    status: str
    sdtvet_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class InstitutionAPIKeyCreate(BaseModel):
    name: str

class InstitutionAPIKeyResponse(BaseModel):
    key_id: UUID
    institution_id: UUID
    name: str
    status: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class InstitutionAPIKeyCreateResponse(InstitutionAPIKeyResponse):
    raw_api_key: str # Only returned once upon creation
