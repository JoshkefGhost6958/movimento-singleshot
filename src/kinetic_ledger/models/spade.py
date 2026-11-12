from typing import List, Optional, Literal, Dict
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# SPADE Hierarchical Motion Blending Models
# =============================================================================


class HierarchyLevel(str, Enum):
    """
    Motion hierarchy levels for SPADE conditioning.
    
    Based on academic research showing Level 1 (COARSE) conditioning
    yields optimal FID/coverage trade-off for motion blending.
    """
    COARSE = "coarse"    # Level 1: Root, pelvis - SPADE applied here (optimal)
    MID = "mid"          # Level 2: Spine, major limbs
    FINE = "fine"        # Level 3: Hands, feet, head
    DETAIL = "detail"    # Level 4: Fingers, facial


class JointHierarchyMapping(BaseModel):
    """
    Mapping of joint names to hierarchy levels.
    
    Default uses Mixamo 24-joint skeleton with research-based
    hierarchy assignments for optimal SPADE conditioning.
    """
    coarse_joints: List[str] = Field(
        default=["Hips", "Spine"],
        description="Level 1 joints - SPADE conditioning applied"
    )
    mid_joints: List[str] = Field(
        default=["Spine1", "Spine2", "LeftUpLeg", "RightUpLeg", 
                 "LeftArm", "RightArm"],
        description="Level 2 joints - standard temporal conditioning"
    )
    fine_joints: List[str] = Field(
        default=["Neck", "Head", "LeftLeg", "RightLeg", 
                 "LeftForeArm", "RightForeArm", "LeftFoot", "RightFoot"],
        description="Level 3 joints - standard temporal conditioning"
    )
    detail_joints: List[str] = Field(
        default=["LeftHand", "RightHand", "LeftToeBase", "RightToeBase",
                 "LeftShoulder", "RightShoulder"],
        description="Level 4 joints - standard temporal conditioning"
    )


class SPADEConfig(BaseModel):
    """
    Configuration for SPADE (Spatially-Adaptive Denormalization) layer.
    
    Research findings:
    - Level 1 (COARSE) SPADE yields best FID/coverage trade-off
    - Captures coarse motion features critical for overall structure
    - Trainable γ/β parameters for style-adaptive modulation
    """
    
    # Which hierarchy level to apply SPADE (1 = COARSE is optimal)
    spade_level: HierarchyLevel = Field(
        default=HierarchyLevel.COARSE,
        description="Hierarchy level for SPADE conditioning (COARSE recommended)"
    )
    
    # Neural network dimensions
    input_dim: int = Field(default=768, ge=1, description="Input embedding dimension")
    style_channels: int = Field(default=128, ge=1, description="Style conditioning channels")
    motion_channels: int = Field(default=256, ge=1, description="Motion feature channels")
    
    # Modulation parameters (trainable γ/β)
    gamma_init: float = Field(default=1.0, description="Scale parameter initialization")
    beta_init: float = Field(default=0.0, description="Bias parameter initialization")
    
    # Transition parameters
    transition_sharpness: float = Field(
        default=5.0, gt=0, 
        description="Controls blend boundary sharpness (sigmoid temperature)"
    )
    
    # Joint hierarchy
    joint_hierarchy: JointHierarchyMapping = Field(
        default_factory=JointHierarchyMapping,
        description="Joint-to-level mapping"
    )
    
    # Training config
    learning_rate: float = Field(default=1e-4, gt=0)
    weight_decay: float = Field(default=1e-5, ge=0)
    
    @model_validator(mode="after")
    def _validate_dims(self) -> "SPADEConfig":
        """Validate dimension relationships."""
        if self.style_channels > self.input_dim:
            raise ValueError(
                f"style_channels ({self.style_channels}) must be <= input_dim ({self.input_dim})"
            )
        return self


class SPADEBlendRequest(BaseModel):
    """
    Request for SPADE-enhanced motion blending.
    
    Uses hierarchical SPADE conditioning with trainable γ/β parameters
    for style-adaptive motion blending.
    """
    
    request_id: str
    motion_ids: List[str] = Field(
        min_length=2, max_length=8,
        description="Source motion IDs to blend (2-8 motions)"
    )
    motion_paths: Optional[List[str]] = Field(
        default=None,
        description="Optional FBX file paths (alternative to motion_ids)"
    )
    weights: List[float] = Field(
        description="Blend weights for duration allocation (must sum to 1.0)"
    )
    style_labels: List[List[str]] = Field(
        description="Style labels for each motion (e.g., [['capoeira'], ['breakdance']])"
    )
    
    # SPADE configuration
    hierarchy_level: int = Field(
        default=1, ge=1, le=4,
        description="Hierarchy level for SPADE conditioning (1=COARSE optimal)"
    )
    transition_frames: int = Field(
        default=30, ge=1, le=120,
        description="Frames for blend transition"
    )
    
    # Advanced options
    use_trainable_params: bool = Field(
        default=True,
        description="Use trainable γ/β parameters (requires PyTorch)"
    )
    checkpoint_path: Optional[str] = Field(
        default=None,
        description="Path to load pretrained SPADE weights"
    )
    
    @field_validator("weights")
    @classmethod
    def _validate_weights_sum(cls, v: List[float]) -> List[float]:
        """Validate weights sum to 1.0."""
        total = sum(v)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"weights must sum to 1.0, got {total}")
        if any(w < 0 for w in v):
            raise ValueError("weights must be non-negative")
        return v
    
    @model_validator(mode="after")
    def _validate_lengths(self) -> "SPADEBlendRequest":
        """Validate array lengths match."""
        n_motions = len(self.motion_ids) if self.motion_ids else 0
        n_paths = len(self.motion_paths) if self.motion_paths else 0
        n_weights = len(self.weights)
        n_styles = len(self.style_labels)
        
        # Determine expected count
        expected = n_motions if n_motions > 0 else n_paths
        
        if expected == 0:
            raise ValueError("Either motion_ids or motion_paths must be provided")
        
        if n_weights != expected:
            raise ValueError(f"weights length ({n_weights}) must match motions ({expected})")
        
        if n_styles != expected:
            raise ValueError(f"style_labels length ({n_styles}) must match motions ({expected})")
        
        return self


class SPADEMetrics(BaseModel):
    """
    Evaluation metrics for SPADE blending quality.
    
    Includes FID (Fréchet Inception Distance), coverage, diversity,
    and motion-specific smoothness metrics.
    """
    
    # Distribution metrics
    fid_score: float = Field(
        ge=0,
        description="Fréchet Inception Distance (lower is better)"
    )
    coverage: float = Field(
        ge=0, le=1,
        description="Coverage of reference distribution (higher is better)"
    )
    diversity: float = Field(
        ge=0,
        description="Variance in generated motion features (higher is better)"
    )
    
    # Motion quality metrics
    smoothness: float = Field(
        ge=0, le=1,
        description="Motion smoothness (1.0 = perfectly smooth, acceleration-based)"
    )
    foot_sliding: float = Field(
        ge=0,
        description="Foot sliding distance in meters (lower is better)"
    )
    
    # SPADE-specific metrics
    spade_level_used: int = Field(ge=1, le=4)
    transition_quality: float = Field(
        ge=0, le=1,
        description="Blend transition quality (higher is better)"
    )
    
    # Timing
    blend_time_ms: float = Field(ge=0, description="Blend computation time")
    metrics_time_ms: float = Field(ge=0, description="Metrics computation time")


class SPADEBlendResponse(BaseModel):
    """
    Response from SPADE motion blending.
    
    Contains blended motion artifacts, quality metrics,
    and debug information for CI/CD validation.
    """
    
    status: Literal["success", "partial", "error"]
    blend_id: str
    
    # SPADE configuration used
    spade_config: SPADEConfig
    
    # Motion info
    source_motions: List[Dict[str, object]] = Field(
        description="Info about source motions (name, frames, style)"
    )
    total_frames: int = Field(ge=1)
    output_fps: int = Field(default=30, ge=1, le=120)
    
    # Artifacts
    blended_tensor_uri: Optional[str] = Field(
        default=None,
        description="URI to blended motion tensor (NPZ/JSON)"
    )
    preview_uri: Optional[str] = Field(
        default=None,
        description="URI to preview video/keyframes"
    )
    artifact_directory: Optional[str] = None
    
    # Quality metrics
    metrics: Optional[SPADEMetrics] = None
    
    # Debug info
    checkpoint_loaded: bool = False
    trainable_params_count: int = Field(default=0, ge=0)
    device_used: str = Field(default="cpu", description="cpu or cuda")
    
    # Error handling
    error_message: Optional[str] = None
    warnings: List[str] = []
