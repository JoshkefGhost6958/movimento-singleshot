import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base

class MotionCatalogue(Base):
    """
    Represents a coherent versioned catalogue snapshot.
    """
    __tablename__ = "motion_catalogues"
    
    catalogue_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, nullable=False, default="DRAFT") # DRAFT, PUBLISHED, RETIRED
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    definitions = relationship("MotionDefinition", back_populates="catalogue", cascade="all, delete-orphan")

class MotionDefinition(Base):
    """
    Represents the authoritative identity of a motion.
    """
    __tablename__ = "motion_definitions"
    
    motion_definition_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    catalogue_id = Column(UUID(as_uuid=True), ForeignKey("motion_catalogues.catalogue_id"), nullable=False)
    
    motion_code = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String, nullable=False)
    version = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")
    
    catalogue = relationship("MotionCatalogue", back_populates="definitions")
    
    semantics = relationship("MotionSemantics", back_populates="definition", uselist=False, cascade="all, delete-orphan")
    capture_contract = relationship("CaptureContract", back_populates="definition", uselist=False, cascade="all, delete-orphan")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MotionSemantics(Base):
    """
    Defines WHAT the motion means and what is intended to be captured.
    """
    __tablename__ = "motion_semantics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    motion_definition_id = Column(UUID(as_uuid=True), ForeignKey("motion_definitions.motion_definition_id"), unique=True, nullable=False)
    
    intent = Column(String, nullable=False)
    semantic_attributes = Column(JSON, nullable=True)
    
    definition = relationship("MotionDefinition", back_populates="semantics")

class CaptureContract(Base):
    """
    Defines HOW the motion should be captured at the TVET.
    """
    __tablename__ = "motion_capture_contracts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    motion_definition_id = Column(UUID(as_uuid=True), ForeignKey("motion_definitions.motion_definition_id"), unique=True, nullable=False)
    
    accepted_file_formats = Column(JSON, nullable=False) # e.g. ["FBX", "BVH"]
    fps_requirements = Column(Integer, nullable=False)
    min_duration_sec = Column(Integer, nullable=True)
    max_duration_sec = Column(Integer, nullable=True)
    capture_quality_requirements = Column(JSON, nullable=True)
    
    definition = relationship("MotionDefinition", back_populates="capture_contract")
