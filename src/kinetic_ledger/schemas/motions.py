# src/schemas/motions.py

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================
# Shared / Artifact References
# ============================================================


class SourceRef(BaseModel):
    """
    Reference to the original animation source.
    """

    model_config = ConfigDict(from_attributes=True)

    type: Literal["upload", "uri", "library"]

    filename: Optional[str] = None

    content_type: Optional[str] = None

    uri: str

    sha256: str = Field(
        min_length=64,
        max_length=66,
    )


class TensorRef(BaseModel):
    """
    Reference to the generated animation tensor.
    """

    model_config = ConfigDict(from_attributes=True)

    representation: Literal["quaternion", "rot6d"]

    fps: int = Field(
        ge=1,
        le=240,
    )

    frame_count: int = Field(
        ge=1,
    )

    joint_count: int = Field(
        ge=1,
    )

    features: List[str] = Field(
        default_factory=list,
    )

    uri: str

    sha256: str = Field(
        min_length=64,
        max_length=66,
    )


class PreviewRef(BaseModel):
    """
    Reference to a generated animation preview.
    """

    model_config = ConfigDict(from_attributes=True)

    uri: str

    sha256: str = Field(
        min_length=64,
        max_length=66,
    )


class SkeletonInfo(BaseModel):
    """
    Skeleton and retargeting information.
    """

    model_config = ConfigDict(from_attributes=True)

    skeleton_id: str

    retarget_profile: Optional[str] = None

    joint_map_uri: Optional[str] = None


# ============================================================
# Upload
# ============================================================


class MotionUploadRequest(BaseModel):
    """
    Upload a raw FBX/BVH animation.

    The institution_id is used to resolve the authenticated institution.
    """

    filename: str = Field(
        min_length=1,
        max_length=512,
    )

    content_base64: str = Field(
        min_length=1,
    )

    content_type: Literal["model/fbx"] = "model/fbx"

    institution_id: str

    institution_wallet: str = Field(
        pattern=r"^0x[a-fA-F0-9]{40}$",
    )

    skeleton_id: str = Field(
        default="mixamo_24j_v1",
        min_length=1,
        max_length=128,
    )

    retarget_profile: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    tensor_config: "TensorGenerationConfig" = Field(
        default_factory=lambda: TensorGenerationConfig(),
    )

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("filename cannot be empty")

        return value


# ============================================================
# Tensor Generation
# ============================================================


class TensorGenerationConfig(BaseModel):
    """
    Controls generation of the canonical motion tensor.
    """

    representation: Literal[
        "quaternion",
        "rot6d",
    ] = "quaternion"

    fps: int = Field(
        default=30,
        ge=1,
        le=240,
    )

    extract_features: List[str] = Field(
        default_factory=lambda: [
            "joint_rot_quat",
            "foot_contacts",
            "root_vel_xy",
            "root_height_z",
        ],
    )


# ============================================================
# Motion Asset Response
# ============================================================


class MotionAssetResponse(BaseModel):
    """
    Complete representation of an ingested animation.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    motion_id: str

    created_at: int

    institution_id: str

    institution_wallet: str = Field(
        pattern=r"^0x[a-fA-F0-9]{40}$",
    )

    source: SourceRef

    tensor: TensorRef

    preview: PreviewRef

    skeleton: SkeletonInfo


class MotionInspectionResponse(BaseModel):
    """Verified metadata emitted by the installed FBX parser."""

    filename: str
    source_sha256: str = Field(min_length=66, max_length=66)
    format: Literal["fbx"]
    parser: Literal["pyufbx"]
    frame_count: int = Field(ge=1)
    joint_count: int = Field(ge=1)
    source_fps: float = Field(gt=0)
    joint_names: List[str] = Field(min_length=1)
    metadata: Dict[str, object]


# ============================================================
# Blend
# ============================================================


class BlendSegment(BaseModel):
    """
    Temporal segment used during motion blending.
    """

    label: str = Field(
        min_length=1,
        max_length=128,
    )

    start_frame: int = Field(
        ge=0,
    )

    end_frame: int = Field(
        ge=0,
    )

    @field_validator("end_frame")
    @classmethod
    def validate_frame_range(
        cls,
        value: int,
    ) -> int:
        return value


class BlendPlan(BaseModel):
    """
    Strategy used to blend animations.
    """

    type: Literal[
        "single_shot_temporal_conditioning",
        "two_stage",
        "custom",
    ]

    segments: List[BlendSegment] = Field(
        default_factory=list,
    )


class MotionBlendInput(BaseModel):
    """
    One animation supplied to a blend request.

    motion_id refers to an already-ingested MotionAsset.
    """

    motion_id: str

    role: Optional[str] = None


class MotionBlendRequestCreate(BaseModel):
    """
    Request to blend previously ingested animations.
    """

    institution_id: str

    institution_wallet: str = Field(
        pattern=r"^0x[a-fA-F0-9]{40}$",
    )

    inputs: List[MotionBlendInput] = Field(
        min_length=1,
    )

    blend_plan: BlendPlan

    npc_context: Dict[str, object] = Field(
        default_factory=dict,
    )

    policy: Dict[str, object] = Field(
        default_factory=dict,
    )


class MotionBlendRequestResponse(BaseModel):
    """
    Persisted blend request response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    request_id: str

    created_at: int

    institution_id: str

    institution_wallet: str

    inputs: List[MotionBlendInput]

    blend_plan: BlendPlan

    npc_context: Dict[str, object]

    policy: Dict[str, object]


# ============================================================
# Canonical Pack
# ============================================================


class MotionCanonicalPackResponse(BaseModel):
    """
    Canonical processing manifest produced from a motion asset.
    """

    pack_version: Literal[
        "MotionCanonicalPack/v1"
    ]

    request_id: str

    institution_id: str

    institution_wallet: str = Field(
        pattern=r"^0x[a-fA-F0-9]{40}$",
    )

    raw_ref: SourceRef

    tensor_ref: TensorRef

    skeleton: SkeletonInfo

    versions: Dict[str, str] = Field(
        default_factory=dict,
    )

    gemini: Dict[str, object] = Field(
        default_factory=dict,
    )

    policy: Dict[str, object] = Field(
        default_factory=dict,
    )


# ============================================================
# Derivation
# ============================================================


class MotionDerivationResponse(BaseModel):
    """
    Describes how one animation was derived from another.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    parent_motion_id: str

    child_motion_id: str

    derivation_type: str

    derivation_depth: int = Field(
        ge=1,
    )

    created_at: int


# ============================================================
# Motion Asset With Provenance
# ============================================================


class MotionAssetV2Response(BaseModel):
    """
    Extended motion response including derivation/provenance data.
    """

    motion_id: str

    created_at: int

    institution_id: str

    institution_wallet: str = Field(
        pattern=r"^0x[a-fA-F0-9]{40}$",
    )

    source: SourceRef

    tensor: TensorRef

    preview: PreviewRef

    skeleton: SkeletonInfo

    parent_motion_ids: List[str] = Field(
        default_factory=list,
    )

    derivation_depth: int = Field(
        ge=0,
    )

    royalty_chain: Optional[dict] = None

    uniqueness_attestation: Optional[dict] = None

    derivative_detection: Optional[dict] = None
