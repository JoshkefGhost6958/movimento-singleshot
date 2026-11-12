"""
SDTVET Registration and Governance Router

Domain Ownership: SDTVET Governance
Responsibility: SDTVET administrative governance operations (registering institutions, managing participation).
Authentication: SDTVET mock admin token
Authorization: SDTVET Admin role only
Resources Exposed: TVET Institution registration and status
Resources Excluded: TVET self-service, Motion Catalogue authoring
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from ...database.database import get_db
from ..dependencies import verify_sdtvet_admin
from ...schemas.institutions import TVETInstitutionCreate, TVETInstitutionUpdate, TVETInstitutionResponse
from ...services import sdtvet as sdtvet_service

router = APIRouter(
    prefix="/v1/sdtvet",
    tags=["SDTVET Governance"],
    dependencies=[Depends(verify_sdtvet_admin)]
)

@router.post("/institutions", response_model=TVETInstitutionResponse)
def register_institution(inst_data: TVETInstitutionCreate, db: Session = Depends(get_db)):
    """Register a new TVET institution under SDTVET governance."""
    return sdtvet_service.register_institution(db, inst_data)

@router.get("/institutions", response_model=List[TVETInstitutionResponse])
def list_institutions(db: Session = Depends(get_db)):
    """List all registered TVET institutions."""
    return sdtvet_service.get_institutions(db)

@router.get("/institutions/{institution_id}", response_model=TVETInstitutionResponse)
def get_institution(institution_id: UUID, db: Session = Depends(get_db)):
    """Get details of a specific TVET institution."""
    return sdtvet_service.get_institution(db, institution_id)

@router.patch("/institutions/{institution_id}", response_model=TVETInstitutionResponse)
def update_institution_status(institution_id: UUID, update_data: TVETInstitutionUpdate, db: Session = Depends(get_db)):
    """Update status or details of a TVET institution (e.g. activate/suspend)."""
    return sdtvet_service.update_institution_status(db, institution_id, update_data)
