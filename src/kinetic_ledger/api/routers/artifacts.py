"""HTTP routes for this API domain."""

import asyncio
import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ...schemas.models import *  # noqa: F401,F403
from ...services import MotionUploadRequest, TrustlessAgentConfig, TrustlessAgentLoop
from ...utils.errors import KineticLedgerError, ManualReviewRequiredError, NoveltyRejectionError
from ...utils.logging import set_correlation_id

router = APIRouter()
logger = logging.getLogger(__name__)


class ArtifactGenerateRequest(BaseModel):
    motion_paths: List[str]
    weights: List[float]
    crosshatch_offsets: List[float]
    actual_frame_counts: Optional[List[int]] = None  # Frame counts from UI
    blend_mode: str = "smoothstep"
    transition_frames: int = 30


@router.post("/api/artifacts/generate")
async def generate_transition_artifacts(request: ArtifactGenerateRequest):
    """
    Generate smooth transition artifacts between 2-3 motion sequences.
    
    Uses BlendAnim temporal conditioning with smoothstep (C² continuity) to create
    30-frame transitions between each motion pair. Returns artifact data with
    frame-by-frame positions, omega values, and aggregate metrics.
    
    Args:
        motion_paths: List of FBX file paths for motions
        weights: Blend weights determining duration of each motion
        crosshatch_offsets: Frame offsets (0-1) for each motion's start position
        blend_mode: Temporal blend function (default: "smoothstep")
        transition_frames: Frames per transition (default: 30)
    
    Returns:
        - blend_id: Unique identifier for this artifact set
        - artifacts: Array of transition frame data
        - motion_segments: Info about each motion's contribution
        - aggregate_metrics: Overall blend quality
        - artifact_directory: Path to saved artifacts
    """
    try:
        from ...services.blendanim_service import get_blendanim_service, MotionSequence
        from ...utils.fbx_parser import get_fbx_parser
        
        try:
            from ...services.gemini_motion_embedder import get_gemini_embedder
            GEMINI_AVAILABLE = True
        except ImportError:
            GEMINI_AVAILABLE = False
            logger.warning("Gemini embedder not available, using FBX parser")
        
        import json
        import uuid
        from pathlib import Path
        
        logger.info(f"Artifact generation: {len(request.motion_paths)} motions, weights {request.weights}")
        
        # Validate inputs
        if len(request.motion_paths) < 2 or len(request.motion_paths) > 3:
            raise HTTPException(400, "Need 2-3 motions for artifact generation")
        
        if len(request.motion_paths) != len(request.weights):
            raise HTTPException(400, "motion_paths and weights must have same length")
        
        if len(request.motion_paths) != len(request.crosshatch_offsets):
            raise HTTPException(400, "motion_paths and crosshatch_offsets must have same length")
        
        # Initialize services
        blender = get_blendanim_service()
        fbx_parser = get_fbx_parser()
        
        if GEMINI_AVAILABLE:
            embedder = get_gemini_embedder()
        
        # Load motion sequences
        motions = []
        motion_info = []
        
        for idx, path in enumerate(request.motion_paths):
            # Resolve path
            if path.startswith('/static/models/'):
                # Remove '/static/models/' prefix to get the actual filesystem path
                fbx_path = Path(path.replace('/static/models/', ''))
            elif path.startswith('/static/'):
                fbx_path = Path(f"data/mixamo_anims/fbx/{Path(path).name}")
            else:
                fbx_path = Path(path)
            
            if not fbx_path.exists():
                raise HTTPException(404, f"Motion file not found: {fbx_path}")
            
            # Process FBX file
            if GEMINI_AVAILABLE:
                # Use Gemini for advanced analysis and embeddings
                fbx_data = await embedder.process_fbx_file(str(fbx_path))
                motion = MotionSequence(
                    positions=fbx_data.skeletal_positions,
                    fps=fbx_data.fps,
                    joint_names=fbx_data.joint_names if hasattr(fbx_data, 'joint_names') else None
                )
            else:
                # Use ufbx parser for direct FBX parsing
                positions, metadata = fbx_parser.parse_fbx(str(fbx_path))
                
                motion = MotionSequence(
                    positions=positions,
                    fps=metadata.get('fps', 30),
                    joint_names=metadata.get('joint_names', None)
                )
                
                logger.info(f"Parsed FBX file {fbx_path.name}: {positions.shape}")
            
            # Use actual frame count from UI if provided (more reliable than re-parsing)
            if request.actual_frame_counts and idx < len(request.actual_frame_counts):
                ui_frame_count = request.actual_frame_counts[idx]
                parsed_frame_count = motion.positions.shape[0]
                
                if ui_frame_count != parsed_frame_count:
                    logger.warning(f"⚠️ Frame count mismatch for {fbx_path.name}: UI={ui_frame_count}, Server parsed={parsed_frame_count}")
                    
                    # Trust the UI's frame count (it loaded the real FBX)
                    if ui_frame_count > parsed_frame_count:
                        # UI has more frames - server likely using fallback/synthetic parser
                        # Pad the motion to match UI's count
                        import numpy as np
                        num_joints = motion.positions.shape[1]
                        num_dims = motion.positions.shape[2]
                        padded_positions = np.zeros((ui_frame_count, num_joints, num_dims))
                        padded_positions[:parsed_frame_count] = motion.positions
                        # Repeat last frame for remaining frames
                        padded_positions[parsed_frame_count:] = motion.positions[-1:]
                        
                        motion = MotionSequence(
                            positions=padded_positions,
                            fps=motion.fps,
                            joint_names=motion.joint_names
                        )
                        logger.info(f"📏 Padded to UI frame count: {parsed_frame_count} → {ui_frame_count} frames")
                    else:
                        # UI has fewer frames - slice to match
                        motion = MotionSequence(
                            positions=motion.positions[:ui_frame_count],
                            fps=motion.fps,
                            joint_names=motion.joint_names
                        )
                        logger.info(f"✂️ Sliced to UI frame count: {parsed_frame_count} → {ui_frame_count} frames")
                else:
                    logger.info(f"✅ Frame count matches UI: {ui_frame_count} frames")
            
            motions.append(motion)
            
            motion_info.append({
                "path": str(fbx_path),
                "name": fbx_path.stem,
                "total_frames": motion.positions.shape[0],
                "duration_seconds": motion.positions.shape[0] / motion.fps,
                "fps": motion.fps
            })
        
        # Generate transition artifacts
        artifacts, aggregate_metrics, actual_motion_segments = blender.generate_transition_artifacts(
            motions=motions,
            weights=request.weights,
            crosshatch_offsets=request.crosshatch_offsets,
            transition_frames=request.transition_frames,
            blend_mode=request.blend_mode
        )
        
        logger.info(f"📊 Artifact generation complete: {len(artifacts)} total frames")
        
        # Count frame types for verification
        motion_artifact_count = sum(1 for a in artifacts if a.get("blend_mode") == "motion_segment")
        transition_artifact_count = sum(1 for a in artifacts if a.get("blend_mode") != "motion_segment")
        logger.info(f"  Motion frames: {motion_artifact_count}")
        logger.info(f"  Transition frames: {transition_artifact_count}")
        
        # Enrich motion segments with motion info
        for i, segment in enumerate(actual_motion_segments):
            segment["motion_name"] = motion_info[i]["name"]
            segment["duration_seconds"] = segment["frame_count"] / motions[i].fps
        
        # Create unique blend ID
        blend_id = f"blend-{uuid.uuid4().hex[:12]}"
        
        # Create artifacts directory
        artifacts_dir = Path("artifacts") / blend_id
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Save artifacts to disk and prepare response
        artifact_files = []
        artifacts_response = []  # Full artifact data for client
        for i, artifact in enumerate(artifacts):
            # Convert numpy arrays to lists for JSON serialization
            artifact_data = {
                "frame_index": artifact["frame_index"],
                "omega": artifact["omega"],
                "positions": artifact["positions"].tolist(),  # [J, 3]
                "blend_mode": artifact["blend_mode"],
                "t_normalized": artifact["t_normalized"]
            }
            
            # Add optional segment metadata if present
            if "segment_type" in artifact:
                artifact_data["segment_type"] = artifact["segment_type"]
            if "segment_frame" in artifact:
                artifact_data["segment_frame"] = artifact["segment_frame"]
            
            # Save to file
            artifact_file = artifacts_dir / f"frame-{i:04d}.json"
            with open(artifact_file, 'w') as f:
                json.dump(artifact_data, f, indent=2)
            
            # URL-only reference for file access
            artifact_files.append({
                "frame_index": i,
                "omega": artifact["omega"],
                "t_normalized": artifact["t_normalized"],
                "blend_mode": artifact.get("blend_mode", "transition"),
                "url": f"/api/artifacts/{blend_id}/frame-{i:04d}.json"
            })
            
            # Full data for immediate client use (includes positions)
            artifacts_response.append(artifact_data)
        
        # Save metadata
        metadata = {
            "blend_id": blend_id,
            "created_at": str(Path(artifacts_dir).stat().st_mtime),
            "motions": motion_info,
            "segments": actual_motion_segments,
            "transition_frames": request.transition_frames,
            "blend_mode": request.blend_mode,
            "total_artifacts": len(artifacts),
            "aggregate_metrics": aggregate_metrics.to_dict()
        }
        
        with open(artifacts_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Generated {len(artifacts)} artifacts in {artifacts_dir}")
        
        return {
            "status": "success",
            "blend_id": blend_id,
            "artifacts": artifacts_response,  # Return full artifact data with positions
            "artifact_files": artifact_files,  # Keep file URLs as reference
            "motion_segments": actual_motion_segments,
            "aggregate_metrics": aggregate_metrics.to_dict(),
            "artifact_directory": str(artifacts_dir),
            "total_transitions": len(motions) - 1,
            "transition_frames_each": request.transition_frames,
            "encoding_method": "gemini" if GEMINI_AVAILABLE else "ufbx parser (Gemini unavailable)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Artifact generation failed: {e}", exc_info=True)
        raise HTTPException(500, f"Artifact generation failed: {str(e)}")

@router.get("/api/artifacts/{blend_id}/frame-{frame_num}.json")
async def get_artifact_frame(blend_id: str, frame_num: str):
    """Retrieve a specific artifact frame."""
    try:
        artifacts_dir = Path("artifacts") / blend_id
        frame_file = artifacts_dir / f"frame-{frame_num}.json"
        
        if not frame_file.exists():
            raise HTTPException(404, f"Artifact frame not found: {frame_num}")
        
        with open(frame_file, 'r') as f:
            return json.load(f)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to load artifact: {str(e)}")


@router.get("/api/artifacts/{blend_id}/metadata")
async def get_artifact_metadata(blend_id: str):
    """Retrieve artifact set metadata."""
    try:
        artifacts_dir = Path("artifacts") / blend_id
        metadata_file = artifacts_dir / "metadata.json"
        
        if not metadata_file.exists():
            raise HTTPException(404, f"Artifact metadata not found for: {blend_id}")
        
        with open(metadata_file, 'r') as f:
            return json.load(f)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to load metadata: {str(e)}")


@router.get("/api/artifacts/{blend_id}/joint-dynamics")
async def get_artifact_joint_dynamics(blend_id: str):
    """
    Retrieve joint dynamics data (L2 velocity and acceleration) for visualization.
    
    Returns per-joint velocity and acceleration time series for:
    - Pelvis (root joint)
    - LeftWrist, RightWrist (hands)
    - LeftFoot, RightFoot (feet)
    
    Data format matches reference images with transition boundaries marked.
    """
    logger.info(f"[ENTRY] get_artifact_joint_dynamics: blend_id={blend_id}")
    
    try:
        artifacts_dir = Path("artifacts") / blend_id
        dynamics_file = artifacts_dir / "joint_dynamics.json"
        
        if not dynamics_file.exists():
            logger.warning(f"[EXIT] get_artifact_joint_dynamics: File not found for {blend_id}")
            raise HTTPException(404, f"Joint dynamics not found for: {blend_id}")
        
        with open(dynamics_file, 'r') as f:
            dynamics = json.load(f)
        
        logger.info(
            f"[EXIT] get_artifact_joint_dynamics: blend_id={blend_id}, "
            f"joints={dynamics.get('joint_names', [])}, "
            f"frames={dynamics.get('total_frames', 0)}"
        )
        return dynamics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[EXIT] get_artifact_joint_dynamics: Failed - {e}", exc_info=True)
        raise HTTPException(500, f"Failed to load joint dynamics: {str(e)}")


@router.get("/api/artifacts/list")
async def list_artifacts():
    """
    List all available blend artifacts in the database.
    
    Returns a list of artifact summaries with metadata for UI display.
    """
    logger.info("[ENTRY] list_artifacts")
    
    try:
        artifacts_dir = Path("artifacts")
        if not artifacts_dir.exists():
            logger.info("[EXIT] list_artifacts: No artifacts directory")
            return {"artifacts": [], "total": 0}
        
        artifacts = []
        for blend_dir in sorted(artifacts_dir.iterdir(), reverse=True):
            if blend_dir.is_dir() and blend_dir.name.startswith("spade-"):
                metadata_file = blend_dir / "metadata.json"
                dynamics_file = blend_dir / "joint_dynamics.json"
                
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    # Count frame files
                    frame_count = len(list(blend_dir.glob("frame-*.json")))
                    
                    artifacts.append({
                        "blend_id": blend_dir.name,
                        "spade_level": metadata.get("spade_level", 1),
                        "spade_level_name": metadata.get("spade_level_name", "COARSE"),
                        "total_frames": metadata.get("total_frames", frame_count),
                        "source_motions": [m.get("name", "Unknown") for m in metadata.get("source_motions", [])],
                        "weights": metadata.get("weights", []),
                        "metrics": metadata.get("metrics", {}),
                        "has_joint_dynamics": dynamics_file.exists(),
                        "created_at": metadata_file.stat().st_mtime,
                    })
        
        logger.info(f"[EXIT] list_artifacts: Found {len(artifacts)} artifacts")
        return {"artifacts": artifacts, "total": len(artifacts)}
        
    except Exception as e:
        logger.error(f"[EXIT] list_artifacts: Failed - {e}", exc_info=True)
        raise HTTPException(500, f"Failed to list artifacts: {str(e)}")


class IntelligentArtifactRequest(BaseModel):
    """Request for Gemini-powered intelligent artifact generation."""
    motion_paths: List[str] = Field(description="FBX file paths for 2-3 motions")
    weights: List[float] = Field(description="Blend weights for motion durations")
    crosshatch_offsets: Optional[List[float]] = None
    actual_frame_counts: Optional[List[int]] = None
    use_gemini_analysis: bool = Field(default=True, description="Enable Gemini multimodal analysis")
    frame_sample_rate: int = Field(default=5, description="Sample every Nth frame for analysis")


@router.post("/api/artifacts/generate-intelligent")
async def generate_intelligent_artifacts(request: IntelligentArtifactRequest):
    """
    Generate high-quality artifacts using Gemini multimodal analysis.
    
    This endpoint uses Gemini's video understanding to analyze motion pairs,
    recommend optimal blend parameters, and predict quality before computation.
    
    Workflow:
    1. Load and render motion frames for Gemini analysis
    2. Analyze motion characteristics and compatibility
    3. Generate intelligent blend parameter recommendations
    4. Execute blend with optimized parameters
    5. Return artifacts with Gemini insights
    
    Returns:
        - All standard artifact data
        - gemini_analysis: Structured analysis and recommendations
        - compatibility_score: Motion pair compatibility (0-1)
        - quality_prediction: Predicted blend quality metrics
        - recommended_vs_used_params: Parameter comparison
    """
    try:
        from ...services.gemini_motion_analyzer import GeminiMotionAnalyzer
        from ...services.blendanim_service import get_blendanim_service, MotionSequence
        from ...utils.fbx_parser import get_fbx_parser
        from ...utils.frame_renderer import MotionFrameRenderer, create_standard_skeleton_hierarchy
        
        # Check API key
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key or not request.use_gemini_analysis:
            # Fall back to standard artifact generation
            logger.warning("Gemini not available, falling back to standard generation")
            standard_request = ArtifactGenerateRequest(
                motion_paths=request.motion_paths,
                weights=request.weights,
                crosshatch_offsets=request.crosshatch_offsets or [0.0] * len(request.motion_paths),
                actual_frame_counts=request.actual_frame_counts,
                transition_frames=30
            )
            return await generate_transition_artifacts(standard_request)
        
        logger.info(f"🎬 Intelligent artifact generation: {len(request.motion_paths)} motions")
        
        # Validate inputs - fall back to standard for 3+ motions
        if len(request.motion_paths) > 2:
            logger.warning(f"Gemini analysis currently supports 2 motions, falling back to standard generation for {len(request.motion_paths)} motions")
            standard_request = ArtifactGenerateRequest(
                motion_paths=request.motion_paths,
                weights=request.weights,
                crosshatch_offsets=request.crosshatch_offsets or [0.0] * len(request.motion_paths),
                actual_frame_counts=request.actual_frame_counts,
                transition_frames=30
            )
            return await generate_transition_artifacts(standard_request)
        
        if len(request.motion_paths) < 2:
            raise HTTPException(400, "Need at least 2 motions for blending")
        
        # Initialize services
        blender = get_blendanim_service()
        fbx_parser = get_fbx_parser()
        analyzer = GeminiMotionAnalyzer(
            api_key=gemini_api_key,
            frame_sample_rate=request.frame_sample_rate
        )
        renderer = MotionFrameRenderer(width=640, height=480)
        
        # Load motion sequences and render frames
        motions = []
        motion_frames = []
        motion_info = []
        
        for idx, path in enumerate(request.motion_paths):
            # Resolve path
            if path.startswith('/static/models/'):
                fbx_path = Path(path.replace('/static/models/', ''))
            elif path.startswith('/static/'):
                fbx_path = Path(f"data/mixamo_anims/fbx/{Path(path).name}")
            else:
                fbx_path = Path(path)
            
            if not fbx_path.exists():
                raise HTTPException(404, f"Motion file not found: {fbx_path}")
            
            # Parse FBX
            positions, metadata = fbx_parser.parse_fbx(str(fbx_path))
            motion = MotionSequence(
                positions=positions,
                fps=metadata.get('fps', 30),
                joint_names=metadata.get('joint_names', None)
            )
            motions.append(motion)
            
            # Render frames for Gemini
            logger.info(f"🎨 Rendering frames for {fbx_path.name}...")
            hierarchy = create_standard_skeleton_hierarchy(positions.shape[1])
            frames = renderer.render_frames_from_positions(
                positions,
                skeleton_hierarchy=hierarchy,
                frame_indices=list(range(0, len(positions), request.frame_sample_rate))
            )
            motion_frames.append(frames)
            
            motion_info.append({
                "path": str(fbx_path),
                "name": fbx_path.stem,
                "total_frames": positions.shape[0],
                "fps": motion.fps
            })
            
            logger.info(f"✅ Rendered {len(frames)} frames from {fbx_path.name}")
        
        # Analyze motion pair with Gemini
        logger.info("🤖 Analyzing motions with Gemini...")
        analysis = await analyzer.analyze_motion_pair(
            motion_a_frames=motion_frames[0],
            motion_b_frames=motion_frames[1],
            motion_a_name=motion_info[0]["name"],
            motion_b_name=motion_info[1]["name"]
        )
        
        logger.info(f"✨ Gemini Analysis Complete:")
        logger.info(f"  Compatibility: {analysis.compatibility.overall_score:.2f}")
        logger.info(f"  Recommended transition frames: {analysis.recommended_parameters.transition_frames}")
        logger.info(f"  Recommended omega curve: {analysis.recommended_parameters.omega_curve_type}")
        logger.info(f"  Predicted smoothness: {analysis.quality_prediction.predicted_smoothness:.2f}")
        
        # Use Gemini's recommended parameters
        transition_frames = analysis.recommended_parameters.transition_frames
        blend_mode = analysis.recommended_parameters.omega_curve_type
        
        # Use Gemini's crosshatch offset or default
        if request.crosshatch_offsets:
            crosshatch_offsets = request.crosshatch_offsets
        else:
            crosshatch_offsets = [0.0, analysis.recommended_parameters.crosshatch_offset / motion_info[1]["total_frames"]]
        
        # Generate artifacts with optimized parameters
        logger.info(f"⚙️ Generating artifacts with Gemini-optimized parameters...")
        artifacts, aggregate_metrics, actual_motion_segments = blender.generate_transition_artifacts(
            motions=motions,
            weights=request.weights,
            crosshatch_offsets=crosshatch_offsets,
            transition_frames=transition_frames,
            blend_mode=blend_mode
        )
        
        # Create blend ID
        blend_id = f"intelligent-blend-{uuid.uuid4().hex[:12]}"
        artifacts_dir = Path("artifacts") / blend_id
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Save artifacts
        artifact_files = []
        artifacts_response = []
        for i, artifact in enumerate(artifacts):
            artifact_data = {
                "frame_index": artifact["frame_index"],
                "omega": artifact["omega"],
                "positions": artifact["positions"].tolist(),
                "blend_mode": artifact["blend_mode"],
                "t_normalized": artifact["t_normalized"]
            }
            
            artifact_file = artifacts_dir / f"frame-{i:04d}.json"
            with open(artifact_file, 'w') as f:
                json.dump(artifact_data, f, indent=2)
            
            artifact_files.append({
                "frame_index": i,
                "omega": artifact["omega"],
                "t_normalized": artifact["t_normalized"],
                "blend_mode": artifact.get("blend_mode", "transition"),
                "url": f"/api/artifacts/{blend_id}/frame-{i:04d}.json"

            })
            
            artifacts_response.append(artifact_data)
        
        # Save comprehensive metadata with Gemini analysis
        metadata = {
            "blend_id": blend_id,
            "intelligent_generation": True,
            "created_at": str(Path(artifacts_dir).stat().st_mtime),
            "motions": motion_info,
            "segments": actual_motion_segments,
            "transition_frames": transition_frames,
            "blend_mode": blend_mode,
            "total_artifacts": len(artifacts),
            "aggregate_metrics": aggregate_metrics.to_dict(),
            "gemini_analysis": {
                "motion_a": analysis.motion_a_characteristics.model_dump(),
                "motion_b": analysis.motion_b_characteristics.model_dump(),
                "compatibility": analysis.compatibility.model_dump(),
                "recommended_parameters": analysis.recommended_parameters.model_dump(),
                "quality_prediction": analysis.quality_prediction.model_dump(),
                "overall_recommendation": analysis.overall_recommendation
            }
        }
        
        with open(artifacts_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"🎉 Generated {len(artifacts)} intelligent artifacts in {artifacts_dir}")
        
        return {
            "status": "success",
            "blend_id": blend_id,
            "artifacts": artifacts_response,
            "artifact_files": artifact_files,
            "motion_segments": actual_motion_segments,
            "aggregate_metrics": aggregate_metrics.to_dict(),
            "artifact_directory": str(artifacts_dir),
            "encoding_method": "gemini_intelligent_analysis",
            
            # Gemini insights
            "gemini_analysis": {
                "motion_a_type": analysis.motion_a_characteristics.motion_type,
                "motion_b_type": analysis.motion_b_characteristics.motion_type,
                "compatibility_score": analysis.compatibility.overall_score,
                "compatibility_reasoning": analysis.compatibility.reasoning,
                "recommended_parameters": analysis.recommended_parameters.model_dump(),
                "quality_prediction": {
                    "predicted_coverage": analysis.quality_prediction.predicted_coverage,
                    "predicted_diversity": analysis.quality_prediction.predicted_diversity,
                    "predicted_smoothness": analysis.quality_prediction.predicted_smoothness,
                    "confidence": analysis.quality_prediction.confidence,
                    "potential_issues": analysis.quality_prediction.potential_issues
                },
                "overall_recommendation": analysis.overall_recommendation
            },
            
            # Parameter comparison
            "parameter_optimization": {
                "transition_frames": {
                    "used": transition_frames,
                    "recommended": analysis.recommended_parameters.transition_frames,
                    "source": "gemini"
                },
                "blend_mode": {
                    "used": blend_mode,
                    "recommended": analysis.recommended_parameters.omega_curve_type,
                    "source": "gemini"
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intelligent artifact generation failed: {e}", exc_info=True)
        raise HTTPException(500, f"Intelligent generation failed: {str(e)}")
