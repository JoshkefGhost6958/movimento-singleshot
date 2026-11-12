from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class SDTVETBase(BaseModel):
    name: str

class SDTVETResponse(SDTVETBase):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
