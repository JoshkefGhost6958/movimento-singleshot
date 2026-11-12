from sqlalchemy.orm import Session
from uuid import UUID
from fastapi import HTTPException, status
from ..models.motion_catalogue import MotionCatalogue, MotionDefinition, MotionSemantics, CaptureContract
from ..schemas.motion_catalogue import MotionCatalogueCreate, MotionDefinitionCreate

def get_active_catalogue(db: Session) -> MotionCatalogue:
    catalogue = db.query(MotionCatalogue).filter(
        MotionCatalogue.status == "PUBLISHED"
    ).order_by(MotionCatalogue.created_at.desc()).first()
    
    if not catalogue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No published catalogue found")
    return catalogue

def get_catalogue_by_version(db: Session, version: str) -> MotionCatalogue:
    catalogue = db.query(MotionCatalogue).filter(MotionCatalogue.version == version).first()
    if not catalogue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue version not found")
    return catalogue

def get_motion_definition(db: Session, motion_definition_id: UUID) -> MotionDefinition:
    definition = db.query(MotionDefinition).filter(
        MotionDefinition.motion_definition_id == motion_definition_id
    ).first()
    
    if not definition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Motion definition not found")
    return definition

# Admin services

def create_catalogue_draft(db: Session, data: MotionCatalogueCreate) -> MotionCatalogue:
    existing = db.query(MotionCatalogue).filter(MotionCatalogue.version == data.version).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version already exists")
        
    catalogue = MotionCatalogue(
        version=data.version,
        status="DRAFT",
        valid_from=data.valid_from,
        valid_until=data.valid_until
    )
    db.add(catalogue)
    db.commit()
    db.refresh(catalogue)
    return catalogue

def add_motion_definition(db: Session, catalogue_id: UUID, data: MotionDefinitionCreate) -> MotionDefinition:
    catalogue = db.query(MotionCatalogue).filter(MotionCatalogue.catalogue_id == catalogue_id).first()
    if not catalogue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue not found")
    if catalogue.status != "DRAFT":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot modify a published catalogue")
        
    definition = MotionDefinition(
        catalogue_id=catalogue_id,
        motion_code=data.motion_code,
        name=data.name,
        description=data.description,
        category=data.category,
        version=data.version
    )
    
    semantics = MotionSemantics(
        intent=data.semantics.intent,
        semantic_attributes=data.semantics.semantic_attributes
    )
    definition.semantics = semantics
    
    contract = CaptureContract(
        accepted_file_formats=data.capture_contract.accepted_file_formats,
        fps_requirements=data.capture_contract.fps_requirements,
        min_duration_sec=data.capture_contract.min_duration_sec,
        max_duration_sec=data.capture_contract.max_duration_sec,
        capture_quality_requirements=data.capture_contract.capture_quality_requirements
    )
    definition.capture_contract = contract
    
    db.add(definition)
    db.commit()
    db.refresh(definition)
    return definition

def publish_catalogue(db: Session, catalogue_id: UUID) -> MotionCatalogue:
    catalogue = db.query(MotionCatalogue).filter(MotionCatalogue.catalogue_id == catalogue_id).first()
    if not catalogue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue not found")
        
    catalogue.status = "PUBLISHED"
    db.commit()
    db.refresh(catalogue)
    return catalogue
