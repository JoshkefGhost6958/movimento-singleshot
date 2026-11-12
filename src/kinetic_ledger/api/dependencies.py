from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session
from ..database.database import get_db
from ..models.institutions import TVETInstitution, InstitutionAPIKey
from ..utils.crypto import hash_api_key

def verify_institution_api_key(
    x_api_key: str = Header(..., description="Institution API Key"),
    db: Session = Depends(get_db)
) -> TVETInstitution:
    """
    Validates the X-API-Key header.
    Resolves to an authenticated TVETInstitution context.
    """
    key_hash = hash_api_key(x_api_key)
    
    api_key_record = db.query(InstitutionAPIKey).filter(
        InstitutionAPIKey.key_hash == key_hash,
        InstitutionAPIKey.status == "ACTIVE"
    ).first()
    
    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API Key"
        )
        
    institution = api_key_record.institution
    if not institution or institution.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Institution is inactive or suspended"
        )
        
    return institution

def verify_sdtvet_admin(
    authorization: str = Header(..., description="Admin Bearer Token")
):
    """
    Validates SDTVET administrative access.
    For this scope, we implement a simple mock token boundary.
    """
    if authorization != "Bearer sdtvet-mock-admin-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid SDTVET administrative token"
        )
    return {"role": "sdtvet_admin"}
