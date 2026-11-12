from sqlalchemy.orm import Session
from uuid import UUID
from fastapi import HTTPException, status
from ..models.sdtvet import SDTVET
from ..models.institutions import TVETInstitution
from ..schemas.institutions import TVETInstitutionCreate, TVETInstitutionUpdate

def get_or_create_sdtvet(db: Session) -> SDTVET:
    sdtvet = db.query(SDTVET).first()
    if not sdtvet:
        sdtvet = SDTVET(name="SDTVET Governing Body")
        db.add(sdtvet)
        db.commit()
        db.refresh(sdtvet)
    return sdtvet

def register_institution(db: Session, inst_data: TVETInstitutionCreate) -> TVETInstitution:
    sdtvet = get_or_create_sdtvet(db)
    
    # Check if institution code already exists
    existing = db.query(TVETInstitution).filter(TVETInstitution.institution_code == inst_data.institution_code).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Institution code already exists")
        
    institution = TVETInstitution(
        institution_code=inst_data.institution_code,
        name=inst_data.name,
        sdtvet_id=sdtvet.id,
        status="ACTIVE"
    )
    db.add(institution)
    db.commit()
    db.refresh(institution)
    return institution

def get_institutions(db: Session):
    return db.query(TVETInstitution).all()

def get_institution(db: Session, institution_id: UUID) -> TVETInstitution:
    institution = db.query(TVETInstitution).filter(TVETInstitution.institution_id == institution_id).first()
    if not institution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")
    return institution

def update_institution_status(db: Session, institution_id: UUID, update_data: TVETInstitutionUpdate) -> TVETInstitution:
    institution = db.query(TVETInstitution).filter(TVETInstitution.institution_id == institution_id).first()
    if not institution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")
        
    if update_data.name is not None:
        institution.name = update_data.name
    if update_data.status is not None:
        institution.status = update_data.status
        
    db.commit()
    db.refresh(institution)
    return institution
