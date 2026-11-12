"""
Motion Catalogue Governance Router

Domain Ownership: Motion Catalogue Administration
Responsibility: Administrative management of catalogue definitions.
Authentication: SDTVET mock admin token
Authorization: SDTVET Admin role only
Resources Exposed: Catalogue creation, definition additions, publishing
Resources Excluded: TVET read API
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from ...database.database import get_db
from ..dependencies import verify_sdtvet_admin
from ...schemas.motion_catalogue import MotionCatalogueCreate, MotionCatalogueResponse, MotionDefinitionCreate, MotionDefinitionResponse
from ...services import motion_catalogue as catalogue_service

router = APIRouter(
    prefix="/v1/admin/motion-catalogue",
    tags=["Motion Catalogue Administration"],
    dependencies=[Depends(verify_sdtvet_admin)]
)

@router.post("", response_model=MotionCatalogueResponse)
def create_catalogue_draft(data: MotionCatalogueCreate, db: Session = Depends(get_db)):
    """Create a new catalogue draft."""
    return catalogue_service.create_catalogue_draft(db, data)

@router.post("/{catalogue_id}/definitions", response_model=MotionDefinitionResponse)
def add_motion_definition(catalogue_id: UUID, data: MotionDefinitionCreate, db: Session = Depends(get_db)):
    """Add a motion definition to a draft catalogue."""
    return catalogue_service.add_motion_definition(db, catalogue_id, data)

@router.post("/{catalogue_id}/publish", response_model=MotionCatalogueResponse)
def publish_catalogue(catalogue_id: UUID, db: Session = Depends(get_db)):
    """Publish a draft catalogue, making it authoritative and immutable."""
    return catalogue_service.publish_catalogue(db, catalogue_id)
