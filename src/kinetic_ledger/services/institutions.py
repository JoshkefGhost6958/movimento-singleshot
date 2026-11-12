from sqlalchemy.orm import Session
from uuid import UUID
from fastapi import HTTPException, status
from ..models.institutions import TVETInstitution, InstitutionAPIKey
from ..schemas.institutions import InstitutionAPIKeyCreate
from ..utils.crypto import hash_api_key, generate_api_key
from datetime import datetime, timezone

def create_api_key(db: Session, institution_id: UUID, key_data: InstitutionAPIKeyCreate) -> tuple[InstitutionAPIKey, str]:
    institution = db.query(TVETInstitution).filter(TVETInstitution.institution_id == institution_id).first()
    if not institution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")
        
    raw_key = generate_api_key()
    hashed_key = hash_api_key(raw_key)
    
    api_key_record = InstitutionAPIKey(
        institution_id=institution_id,
        key_hash=hashed_key,
        name=key_data.name,
        status="ACTIVE"
    )
    db.add(api_key_record)
    db.commit()
    db.refresh(api_key_record)
    
    return api_key_record, raw_key

def list_api_keys(db: Session, institution_id: UUID):
    return db.query(InstitutionAPIKey).filter(InstitutionAPIKey.institution_id == institution_id).all()

def revoke_api_key(db: Session, institution_id: UUID, key_id: UUID):
    api_key_record = db.query(InstitutionAPIKey).filter(
        InstitutionAPIKey.key_id == key_id,
        InstitutionAPIKey.institution_id == institution_id
    ).first()
    
    if not api_key_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found")
        
    api_key_record.status = "REVOKED"
    api_key_record.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "revoked"}
