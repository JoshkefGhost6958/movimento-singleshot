"""
Gemini Motion Analyzer Service.

Analyzes motion pairs using Gemini multimodal vision to recommend
optimal blend parameters. Provides structured analysis of motion
characteristics, compatibility, and quality predictions.

Features:
- Motion pair analysis with Gemini vision (when API key available)
- Rule-based fallback analysis without API key
- Structured output schemas for analysis results
"""
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Structured Output Models
# =============================================================================


class MotionCharacteristics(BaseModel):
    """Characteristics of a single motion sequence."""
    
    motion_type: str = Field(
        default="unknown",
        description="Detected motion type (e.g., 'locomotion', 'dance', 'combat')"
    )
    tempo: str = Field(
        default="medium",
        description="Motion tempo (slow, medium, fast)"
    )
    energy: str = Field(
        default="medium",
        description="Energy level (low, medium, high)"
    )
    dominant_joints: List[str] = Field(
        default_factory=list,
        description="Joints most involved in the motion"
    )
    description: str = Field(
        default="",
        description="Textual description of the motion"
    )


class MotionCompatibility(BaseModel):
    """Compatibility assessment between two motions."""
    
    overall_score: float = Field(
        ge=0.0, le=1.0,
        description="Overall compatibility score (0-1)"
    )
    rhythm_compatibility: float = Field(
        ge=0.0, le=1.0,
        description="Rhythm/tempo compatibility"
    )
    spatial_compatibility: float = Field(
        ge=0.0, le=1.0,
        description="Spatial overlap and use of space"
    )
    reasoning: str = Field(
        default="",
        description="Explanation of compatibility assessment"
    )


class RecommendedParameters(BaseModel):
    """Optimal blend parameters recommended by analysis."""
    
    transition_frames: int = Field(
        ge=1, le=120,
        description="Recommended number of frames for transition"
    )
    omega_curve_type: str = Field(
        default="smoothstep",
        description="Recommended blending curve type"
    )
    crosshatch_offset: int = Field(
        ge=0,
        description="Recommended crosshatch offset in frames"
    )
    blend_strength: float = Field(
        ge=0.0, le=1.0, default=0.5,
        description="Recommended blend strength"
    )


class QualityPrediction(BaseModel):
    """Predicted quality metrics for the blend."""
    
    predicted_coverage: float = Field(
        ge=0.0, le=1.0,
        description="Predicted coverage score"
    )
    predicted_diversity: float = Field(
        ge=0.0,
        description="Predicted diversity score"
    )
    predicted_smoothness: float = Field(
        ge=0.0, le=1.0,
        description="Predicted smoothness score"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in predictions"
    )
    potential_issues: List[str] = Field(
        default_factory=list,
        description="Potential issues to watch for"
    )


class MotionPairAnalysis(BaseModel):
    """Complete analysis of a motion pair for blending."""
    
    motion_a_characteristics: MotionCharacteristics
    motion_b_characteristics: MotionCharacteristics
    compatibility: MotionCompatibility
    recommended_parameters: RecommendedParameters
    quality_prediction: QualityPrediction
    overall_recommendation: str


# =============================================================================
# Gemini Motion Analyzer Service
# =============================================================================


class GeminiMotionAnalyzer:
    """
    Analyzes motion pairs for optimal blend parameters.
    
    Uses Gemini vision for multimodal analysis when API key is available.
    Falls back to rule-based analysis using motion statistics.
    """
    
    def __init__(self, api_key: Optional[str] = None, frame_sample_rate: int = 5):
        """
        Initialize the motion analyzer.
        
        Args:
            api_key: Optional Gemini API key
            frame_sample_rate: Sample rate for frame extraction
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.frame_sample_rate = frame_sample_rate
        self._client = None
        
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                logger.info("Gemini client initialized for motion analysis")
            except Exception as e:
                logger.warning(f"Gemini client initialization failed: {e}")
                self._client = None
        
        logger.info(f"GeminiMotionAnalyzer initialized (gemini={self._client is not None})")
    
    def analyze_motion_pair(
        self,
        motion_a_frames: List[Any],
        motion_b_frames: List[Any],
        motion_a_name: str = "motion_a",
        motion_b_name: str = "motion_b",
    ) -> MotionPairAnalysis:
        """
        Analyze a pair of motions for blending compatibility.
        
        Args:
            motion_a_frames: Rendered frames from motion A
            motion_b_frames: Rendered frames from motion B
            motion_a_name: Name/label of motion A
            motion_b_name: Name/label of motion B
        
        Returns:
            MotionPairAnalysis with characteristics, compatibility,
            recommended parameters, and quality predictions.
        """
        logger.info(
            f"[ENTRY] analyze_motion_pair: "
            f"a={motion_a_name} ({len(motion_a_frames)} frames), "
            f"b={motion_b_name} ({len(motion_b_frames)} frames)"
        )
        
        # Try Gemini analysis if available
        if self._client is not None:
            try:
                result = self._analyze_with_gemini(
                    motion_a_frames, motion_b_frames,
                    motion_a_name, motion_b_name,
                )
                return result
            except Exception as e:
                logger.warning(f"Gemini analysis failed, using fallback: {e}")
        
        # Rule-based fallback
        result = self._analyze_rule_based(
            motion_a_frames, motion_b_frames,
            motion_a_name, motion_b_name,
        )
        
        logger.info(f"[EXIT] analyze_motion_pair: compatibility={result.compatibility.overall_score:.2f}")
        return result
    
    def _analyze_with_gemini(
        self,
        motion_a_frames: List[Any],
        motion_b_frames: List[Any],
        motion_a_name: str,
        motion_b_name: str,
    ) -> MotionPairAnalysis:
        """
        Analyze motion pair using Gemini multimodal vision.
        
        Args:
            motion_a_frames: Rendered frames from motion A
            motion_b_frames: Rendered frames from motion B
            motion_a_name: Name of motion A
            motion_b_name: Name of motion B
        
        Returns:
            MotionPairAnalysis with Gemini-based assessments
        """
        from google.genai import types
        
        # Build prompt for analysis
        prompt = self._build_analysis_prompt(motion_a_name, motion_b_name)
        
        # Build content with image frames
        contents = [prompt]
        
        # Add sample frames from each motion (max 3 each)
        for frames, label in [
            (motion_a_frames, "Motion A"),
            (motion_b_frames, "Motion B"),
        ]:
            sample_indices = list(range(0, len(frames), max(1, len(frames) // 3)))[:3]
            for idx in sample_indices:
                frame = frames[idx]
                if hasattr(frame, 'tobytes'):
                    # numpy array - convert to image part
                    import io
                    from PIL import Image
                    img = Image.fromarray(frame.astype('uint8'))
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    buf.seek(0)
                    contents.append(
                        types.Part.from_bytes(
                            data=buf.getvalue(),
                            mime_type="image/png",
                        )
                    )
                elif hasattr(frame, 'save'):
                    # PIL Image
                    import io
                    buf = io.BytesIO()
                    frame.save(buf, format='PNG')
                    buf.seek(0)
                    contents.append(
                        types.Part.from_bytes(
                            data=buf.getvalue(),
                            mime_type="image/png",
                        )
                    )
        
        # Call Gemini
        response = self._client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=contents,
        )
        
        # Parse response (best effort - fall back to heuristic values)
        text = response.text or ""
        
        # Extract basic characteristics from text analysis
        compatibility_score = 0.7  # Default
        if "incompatible" in text.lower() or "poor" in text.lower():
            compatibility_score = 0.3
        elif "excellent" in text.lower() or "very compatible" in text.lower():
            compatibility_score = 0.9
        
        # Use text-derived parameters
        transition_frames = 30
        if "long" in text.lower() or "slow" in text.lower():
            transition_frames = 45
        elif "quick" in text.lower() or "fast" in text.lower():
            transition_frames = 20
        
        return MotionPairAnalysis(
            motion_a_characteristics=MotionCharacteristics(
                motion_type=self._detect_motion_type(motion_a_name),
                description=f"Motion A ({motion_a_name})",
            ),
            motion_b_characteristics=MotionCharacteristics(
                motion_type=self._detect_motion_type(motion_b_name),
                description=f"Motion B ({motion_b_name})",
            ),
            compatibility=MotionCompatibility(
                overall_score=compatibility_score,
                rhythm_compatibility=compatibility_score,
                spatial_compatibility=compatibility_score,
                reasoning=text[:500] if text else "Gemini analysis",
            ),
            recommended_parameters=RecommendedParameters(
                transition_frames=transition_frames,
                omega_curve_type="smoothstep",
                crosshatch_offset=transition_frames // 2,
                blend_strength=0.5,
            ),
            quality_prediction=QualityPrediction(
                predicted_coverage=0.75 + (compatibility_score * 0.2),
                predicted_diversity=max(1.0, compatibility_score * 3.0),
                predicted_smoothness=0.7 + (compatibility_score * 0.25),
                confidence=0.6,
                potential_issues=[],
            ),
            overall_recommendation=(
                text[:300] if text 
                else f"Recommended smooth transition of {transition_frames} frames"
            ),
        )
    
    def _analyze_rule_based(
        self,
        motion_a_frames: List[Any],
        motion_b_frames: List[Any],
        motion_a_name: str,
        motion_b_name: str,
    ) -> MotionPairAnalysis:
        """
        Rule-based motion pair analysis (fallback).
        
        Uses frame statistics to estimate compatibility:
        - Frame count ratio → compatibility
        - Name-based motion type detection
        - Heuristic transition parameters
        """
        num_a = len(motion_a_frames)
        num_b = len(motion_b_frames)
        
        # Compute frame count based compatibility
        if num_a > 0 and num_b > 0:
            ratio = min(num_a, num_b) / max(num_a, num_b)
            compatibility_score = 0.5 + (ratio * 0.4)  # 0.5 to 0.9
        else:
            compatibility_score = 0.7
        
        # Detect motion types from names
        type_a = self._detect_motion_type(motion_a_name)
        type_b = self._detect_motion_type(motion_b_name)
        
        # Adjust compatibility based on motion type similarity
        if type_a == type_b:
            compatibility_score = max(0.7, compatibility_score)
        
        # Determine transition frames based on motion complexity
        avg_frames = (num_a + num_b) // 2 if (num_a + num_b) > 0 else 60
        transition_frames = max(15, min(60, avg_frames // 4))
        
        return MotionPairAnalysis(
            motion_a_characteristics=MotionCharacteristics(
                motion_type=type_a,
                description=f"Motion A ({motion_a_name}): {num_a} frames",
            ),
            motion_b_characteristics=MotionCharacteristics(
                motion_type=type_b,
                description=f"Motion B ({motion_b_name}): {num_b} frames",
            ),
            compatibility=MotionCompatibility(
                overall_score=compatibility_score,
                rhythm_compatibility=compatibility_score,
                spatial_compatibility=max(0.5, compatibility_score - 0.1),
                reasoning=(
                    f"Rule-based analysis: {type_a} → {type_b}, "
                    f"frame ratio compatibility {compatibility_score:.2f}"
                ),
            ),
            recommended_parameters=RecommendedParameters(
                transition_frames=transition_frames,
                omega_curve_type="smoothstep",
                crosshatch_offset=transition_frames // 2,
                blend_strength=0.5,
            ),
            quality_prediction=QualityPrediction(
                predicted_coverage=0.7 + (compatibility_score * 0.2),
                predicted_diversity=max(1.0, transition_frames / 10),
                predicted_smoothness=0.65 + (compatibility_score * 0.3),
                confidence=0.5,
                potential_issues=["Rule-based analysis - use Gemini for higher confidence"],
            ),
            overall_recommendation=(
                f"Recommended {transition_frames}-frame smoothstep transition "
                f"between {motion_a_name} and {motion_b_name}"
            ),
        )
    
    def _detect_motion_type(self, name: str) -> str:
        """Detect motion type from name keywords."""
        name_lower = name.lower()
        
        dance_keywords = ["dance", "dancing", "breakdance", "salsa", "swing", "hip hop", "charleston"]
        combat_keywords = ["capoeira", "punch", "kick", "fight", "combat", "martial"]
        locomotion_keywords = ["walk", "run", "jump", "crouch", "idle", "stand"]
        acrobatic_keywords = ["freeze", "flip", "acrobat", "spin"]
        
        if any(k in name_lower for k in dance_keywords):
            return "dance"
        if any(k in name_lower for k in combat_keywords):
            return "combat"
        if any(k in name_lower for k in locomotion_keywords):
            return "locomotion"
        if any(k in name_lower for k in acrobatic_keywords):
            return "acrobatic"
        
        return "generic"
    
    def _build_analysis_prompt(self, motion_a_name: str, motion_b_name: str) -> str:
        """Build the analysis prompt for Gemini."""
        return f"""Analyze these two motion sequences for blending compatibility.

Motion A: {motion_a_name}
Motion B: {motion_b_name}

For each motion, identify:
1. Motion type (dance, combat, locomotion, etc.)
2. Tempo and energy level
3. Dominant joints involved

Then assess:
1. Overall compatibility score (0-1)
2. Rhythm compatibility (0-1)
3. Spatial compatibility (0-1)
4. Recommended transition frame count
5. Predicted blend quality

Provide concise analysis focused on blend optimization."""
    
    def heuristic_analyze(self, positions_a: Any, positions_b: Any) -> Dict[str, Any]:
        """
        Quick heuristic analysis using motion position data.
        
        Args:
            positions_a: Motion A position data
            positions_b: Motion B position data
            
        Returns:
            Dict with basic analysis metrics
        """
        import numpy as np
        
        if hasattr(positions_a, 'skeletal_positions'):
            pa = positions_a.skeletal_positions
        else:
            pa = positions_a
        
        if hasattr(positions_b, 'skeletal_positions'):
            pb = positions_b.skeletal_positions
        else:
            pb = positions_b
        
        # Compute basic statistics
        result = {
            "motion_a": {
                "frames": len(pa),
                "mean_motion": float(np.mean(np.abs(np.diff(pa, axis=0)))) if len(pa) > 1 else 0.0,
            },
            "motion_b": {
                "frames": len(pb),
                "mean_motion": float(np.mean(np.abs(np.diff(pb, axis=0)))) if len(pb) > 1 else 0.0,
            },
        }
        
        return result


# Singleton instance
_analyzer_instance: Optional[GeminiMotionAnalyzer] = None


def get_motion_analyzer() -> GeminiMotionAnalyzer:
    """Get or create the motion analyzer singleton."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = GeminiMotionAnalyzer()
    return _analyzer_instance


def reset_motion_analyzer() -> None:
    """Reset the singleton instance (for testing)."""
    global _analyzer_instance
    _analyzer_instance = None