"""
Unified Motion Capture Design Router

Domain Ownership: Motion Catalogue
Responsibility: Authoritative TVET-facing Motion Catalogue boundary (Read-Only).
Authentication: X-API-Key (TVET authenticated context)
Authorization: Read-only access to catalogue snapshots and definitions.
Resources Exposed: Motion Catalogues, Motion Definitions
Resources Excluded: Catalogue authoring, downstream processing details
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from ...database.database import get_db
from ..dependencies import verify_institution_api_key
from ...models.institutions import TVETInstitution
from ...schemas.motion_catalogue import MotionCatalogueResponse, MotionDefinitionResponse
from ...services import motion_catalogue as catalogue_service

router = APIRouter(
    prefix="/v1/motion-catalogue",
    tags=["Motion Catalogue"],
    dependencies=[Depends(verify_institution_api_key)]
)

@router.get("", response_model=MotionCatalogueResponse)
def get_active_catalogue(db: Session = Depends(get_db)):
    """Returns the authoritative active catalogue snapshot."""
    return catalogue_service.get_active_catalogue(db)

@router.get("/versions/{catalogue_version}", response_model=MotionCatalogueResponse)
def get_catalogue_by_version(catalogue_version: str, db: Session = Depends(get_db)):
    """Returns a specific historical catalogue snapshot."""
    return catalogue_service.get_catalogue_by_version(db, catalogue_version)

@router.get("/{motion_definition_id}", response_model=MotionDefinitionResponse)
def get_motion_definition(motion_definition_id: UUID, db: Session = Depends(get_db)):
    """Returns a specific motion definition."""
    return catalogue_service.get_motion_definition(db, motion_definition_id)
