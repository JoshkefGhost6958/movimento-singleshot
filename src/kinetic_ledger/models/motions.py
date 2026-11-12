# src/db/models/motions.py

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


if TYPE_CHECKING:
    from .institutions import TVETInstitution


# ============================================================
# Motion Asset
# ============================================================


class MotionAsset(Base):
    """
    First-class animation asset.

    Represents the logical animation and its ownership.
    Source, tensor, preview and skeleton are persisted as
    separate one-to-one records.
    """

    __tablename__ = "motion_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    motion_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tvet_institutions.institution_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="RECEIVED",
        index=True,
    )

    institution: Mapped["TVETInstitution"] = relationship(
        "TVETInstitution",
        foreign_keys=[institution_id],
    )

    source: Mapped["MotionSource | None"] = relationship(
        "MotionSource",
        back_populates="motion",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    tensor: Mapped["MotionTensor | None"] = relationship(
        "MotionTensor",
        back_populates="motion",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    preview: Mapped["MotionPreview | None"] = relationship(
        "MotionPreview",
        back_populates="motion",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    skeleton: Mapped["MotionSkeleton | None"] = relationship(
        "MotionSkeleton",
        back_populates="motion",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    parent_derivations: Mapped[list["MotionDerivation"]] = relationship(
        "MotionDerivation",
        foreign_keys="MotionDerivation.parent_motion_id",
        back_populates="parent_motion",
    )

    child_derivations: Mapped[list["MotionDerivation"]] = relationship(
        "MotionDerivation",
        foreign_keys="MotionDerivation.child_motion_id",
        back_populates="child_motion",
    )

    canonical_packs: Mapped[list["MotionCanonicalPack"]] = relationship(
        "MotionCanonicalPack",
        back_populates="motion",
        cascade="all, delete-orphan",
    )


# ============================================================
# Source
# ============================================================


class MotionSource(Base):
    """
    Original animation source.

    Examples:
        - uploaded FBX
        - uploaded BVH
        - external URI
        - internal library object
    """

    __tablename__ = "motion_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    motion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("motion_assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    filename: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    content_type: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
        index=True,
    )

    motion: Mapped["MotionAsset"] = relationship(
        "MotionAsset",
        back_populates="source",
    )


# ============================================================
# Tensor
# ============================================================


class MotionTensor(Base):
    """
    Generated tensor representation of an animation.
    """

    __tablename__ = "motion_tensors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    motion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("motion_assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    representation: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    fps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    frame_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    joint_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    features: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
        index=True,
    )

    motion: Mapped["MotionAsset"] = relationship(
        "MotionAsset",
        back_populates="tensor",
    )


# ============================================================
# Preview
# ============================================================


class MotionPreview(Base):
    """
    Rendered preview artifact for an animation.
    """

    __tablename__ = "motion_previews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    motion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("motion_assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
        index=True,
    )

    motion: Mapped["MotionAsset"] = relationship(
        "MotionAsset",
        back_populates="preview",
    )


# ============================================================
# Skeleton
# ============================================================


class MotionSkeleton(Base):
    """
    Canonical skeleton information associated with an animation.
    """

    __tablename__ = "motion_skeletons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    motion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("motion_assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    skeleton_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    retarget_profile: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    joint_map_uri: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    motion: Mapped["MotionAsset"] = relationship(
        "MotionAsset",
        back_populates="skeleton",
    )


# ============================================================
# Derivation
# ============================================================


class MotionDerivation(Base):
    """
    Parent/child relationship between animations.

    Example:

        walk.fbx
            ↓
        walk_retargeted
            ↓
        walk_blended
    """

    __tablename__ = "motion_derivations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    parent_motion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("motion_assets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    child_motion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("motion_assets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    derivation_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    derivation_depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    parent_motion: Mapped["MotionAsset"] = relationship(
        "MotionAsset",
        foreign_keys=[parent_motion_id],
        back_populates="parent_derivations",
    )

    child_motion: Mapped["MotionAsset"] = relationship(
        "MotionAsset",
        foreign_keys=[child_motion_id],
        back_populates="child_derivations",
    )

    __table_args__ = (
        UniqueConstraint(
            "parent_motion_id",
            "child_motion_id",
            name="uq_motion_derivation",
        ),
    )


# ============================================================
# Blend Request
# ============================================================


class MotionBlendRequest(Base):
    """
    A request to combine one or more MotionAssets.
    """

    __tablename__ = "motion_blend_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    request_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tvet_institutions.institution_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    blend_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    npc_context: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    policy: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    inputs: Mapped[list["MotionBlendInput"]] = relationship(
        "MotionBlendInput",
        back_populates="request",
        cascade="all, delete-orphan",
    )

    segments: Mapped[list["MotionBlendSegment"]] = relationship(
        "MotionBlendSegment",
        back_populates="request",
        cascade="all, delete-orphan",
    )


class MotionBlendInput(Base):
    """
    A MotionAsset participating in a blend request.
    """

    __tablename__ = "motion_blend_inputs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "motion_blend_requests.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    motion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "motion_assets.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    sequence_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    request: Mapped["MotionBlendRequest"] = relationship(
        "MotionBlendRequest",
        back_populates="inputs",
    )

    motion: Mapped["MotionAsset"] = relationship(
        "MotionAsset",
    )

    __table_args__ = (
        UniqueConstraint(
            "request_id",
            "sequence_order",
            name="uq_blend_input_order",
        ),
    )


class MotionBlendSegment(Base):
    """
    Temporal segment in a MotionBlendRequest.
    """

    __tablename__ = "motion_blend_segments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "motion_blend_requests.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    label: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    start_frame: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    end_frame: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    request: Mapped["MotionBlendRequest"] = relationship(
        "MotionBlendRequest",
        back_populates="segments",
    )


# ============================================================
# Canonical Pack
# ============================================================


class MotionCanonicalPack(Base):
    """
    Persisted canonical-processing manifest.

    Flexible processing metadata is JSONB because versions,
    Gemini metadata and policy can evolve independently.
    """

    __tablename__ = "motion_canonical_packs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    request_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    motion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "motion_assets.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    pack_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="MotionCanonicalPack/v1",
    )

    versions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    gemini: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    policy: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    motion: Mapped["MotionAsset"] = relationship(
        "MotionAsset",
        back_populates="canonical_packs",
    )