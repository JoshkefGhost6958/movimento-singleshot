"""
Institution Registration and Governance Router

Domain Ownership: TVET Institution layer
Responsibility: Expose institutional resource boundary, sync state, and API key lifecycle.
Authentication: X-API-Key for self-service, SDTVET mock admin for admin actions
Authorization: Institution boundary isolation
Resources Exposed: Institution identity, API key lifecycle
Resources Excluded: Motion Catalogue, Recording Sessions, Motion Assets
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from ...database.database import get_db
from ..dependencies import verify_institution_api_key, verify_sdtvet_admin
from ...models.institutions import TVETInstitution
from ...schemas.institutions import InstitutionAPIKeyCreate, InstitutionAPIKeyResponse, InstitutionAPIKeyCreateResponse, TVETInstitutionResponse
from ...services import institutions as inst_service

router = APIRouter(
    prefix="/v1/institutions",
    tags=["TVET Institutions"]
)

@router.get("/me", response_model=TVETInstitutionResponse)
def get_my_institution(institution: TVETInstitution = Depends(verify_institution_api_key)):
    """Retrieve own institutional identity."""
    return institution

@router.post("/{institution_id}/api-keys", response_model=InstitutionAPIKeyCreateResponse, dependencies=[Depends(verify_sdtvet_admin)])
def create_api_key(institution_id: UUID, key_data: InstitutionAPIKeyCreate, db: Session = Depends(get_db)):
    """Admin endpoint to create an API key for an institution. Returns the raw key once."""
    api_key_record, raw_key = inst_service.create_api_key(db, institution_id, key_data)
    record_dict = {c.name: getattr(api_key_record, c.name) for c in api_key_record.__table__.columns}
    record_dict["raw_api_key"] = raw_key
    return InstitutionAPIKeyCreateResponse.model_validate(record_dict)

@router.get("/{institution_id}/api-keys", response_model=List[InstitutionAPIKeyResponse], dependencies=[Depends(verify_sdtvet_admin)])
def list_api_keys(institution_id: UUID, db: Session = Depends(get_db)):
    """Admin endpoint to list API keys for an institution."""
    return inst_service.list_api_keys(db, institution_id)

@router.post("/{institution_id}/api-keys/{key_id}/revoke", dependencies=[Depends(verify_sdtvet_admin)])
def revoke_api_key(institution_id: UUID, key_id: UUID, db: Session = Depends(get_db)):
    """Admin endpoint to revoke an API key."""
    return inst_service.revoke_api_key(db, institution_id, key_id)
