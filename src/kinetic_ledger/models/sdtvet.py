import uuid
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base

class SDTVET(Base):
    """
    SDTVET Registration and Governance authority.
    Represents the governing body that registers TVETs.
    """
    __tablename__ = "sdtvet_governance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True, default="SDTVET Governing Body")
    status = Column(String, nullable=False, default="ACTIVE")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    institutions = relationship("TVETInstitution", back_populates="sdtvet", cascade="all, delete-orphan")
