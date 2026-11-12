import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base

class TVETInstitution(Base):
    """
    TVET Institution identity and state.
    """
    __tablename__ = "tvet_institutions"
    
    institution_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")  # PENDING, ACTIVE, SUSPENDED
    
    sdtvet_id = Column(UUID(as_uuid=True), ForeignKey("sdtvet_governance.id"), nullable=False)
    sdtvet = relationship("SDTVET", back_populates="institutions")
    
    api_keys = relationship("InstitutionAPIKey", back_populates="institution", cascade="all, delete-orphan")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class InstitutionAPIKey(Base):
    """
    Institution API Key credentials.
    """
    __tablename__ = "institution_api_keys"
    
    key_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(UUID(as_uuid=True), ForeignKey("tvet_institutions.institution_id"), nullable=False)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE") # ACTIVE, REVOKED, EXPIRED

    institution = relationship("TVETInstitution", back_populates="api_keys")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
