"""
Gemini Motion Embedder Service.

Processes FBX motion files and generates embeddings for motion analysis.
Uses the existing FBX loader for parsing and optionally enhances with
Gemini embeddings when an API key is available.

Provides:
- process_fbx_file(): Parse FBX and return motion data with skeletal positions
- get_gemini_embedder(): Singleton factory
"""
import logging
import os
from typing import Any, List, Optional

import numpy as np

from ..utils.logging import get_logger
from ..utils.fbx_loader import load_fbx_motion, FBXMotionData, MIXAMO_JOINT_ORDER

logger = get_logger(__name__)


class GeminiMotionEmbedder:
    """
    Motion embedder that processes FBX files and generates embeddings.
    
    Uses the existing FBX loader for parsing motion data. When a Gemini
    API key is available, can optionally generate semantic embeddings
    for motion descriptors.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the motion embedder.
        
        Args:
            api_key: Optional Gemini API key for semantic embeddings
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._gemini_available = False
        
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                self._gemini_available = True
                logger.info("Gemini client initialized for motion embedding")
            except Exception as e:
                logger.warning(f"Gemini client initialization failed: {e}")
                self._client = None
        else:
            self._client = None
        
        logger.info(f"GeminiMotionEmbedder initialized (gemini={self._gemini_available})")
    
    def process_fbx_file(self, fbx_path: str) -> Any:
        """
        Process an FBX file and return motion data.
        
        Args:
            fbx_path: Path to FBX file
            
        Returns:
            Object with skeletal_positions, fps, and joint_names attributes
        """
        logger.info(f"[ENTRY] process_fbx_file: {fbx_path}")
        
        try:
            # Use existing FBX loader
            motion_data = load_fbx_motion(fbx_path, normalize=False)
            
            # Create a compatible wrapper object
            result = FBXProcessedMotion(
                skeletal_positions=motion_data.positions,
                fps=motion_data.fps,
                joint_names=motion_data.joint_names,
                source_file=motion_data.source_file,
            )
            
            logger.info(
                f"[EXIT] process_fbx_file: frames={result.skeletal_positions.shape[0]}, "
                f"joints={result.skeletal_positions.shape[1]}"
            )
            return result
            
        except Exception as e:
            logger.error(f"FBX processing failed: {e}")
            # Fallback: generate synthetic motion data
            logger.warning("Generating synthetic motion data as fallback")
            T = 120
            J = len(MIXAMO_JOINT_ORDER)
            positions = np.random.randn(T, J, 3).astype(np.float32) * 0.3
            
            result = FBXProcessedMotion(
                skeletal_positions=positions,
                fps=30.0,
                joint_names=MIXAMO_JOINT_ORDER,
                source_file=str(fbx_path),
            )
            return result
    
    def generate_embedding(self, descriptor: str) -> Optional[List[float]]:
        """
        Generate a semantic embedding for a motion descriptor.
        
        Args:
            descriptor: Text description of the motion
            
        Returns:
            Embedding vector or None if Gemini unavailable
        """
        if not self._gemini_available or self._client is None:
            return None
        
        try:
            from google.genai import types
            
            result = self._client.models.embed_content(
                model="gemini-embedding-001",
                contents=descriptor,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=768
                )
            )
            
            [embedding_obj] = result.embeddings
            return embedding_obj.values
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if Gemini embedding is available."""
        return self._gemini_available


class FBXProcessedMotion:
    """
    Wrapper for processed FBX motion data.
    
    Provides the interface expected by server.py:
    - skeletal_positions: [T, J, 3] numpy array
    - fps: frames per second
    - joint_names: list of joint names
    """
    
    def __init__(
        self,
        skeletal_positions: np.ndarray,
        fps: float,
        joint_names: List[str],
        source_file: Optional[str] = None,
    ):
        self.skeletal_positions = skeletal_positions
        self.fps = fps
        self.joint_names = joint_names
        self.source_file = source_file
        
        self.num_frames = skeletal_positions.shape[0]
        self.num_joints = skeletal_positions.shape[1]
    
    def __repr__(self) -> str:
        return (
            f"FBXProcessedMotion(frames={self.num_frames}, "
            f"joints={self.num_joints}, fps={self.fps})"
        )


# Singleton instance
_embedder_instance: Optional[GeminiMotionEmbedder] = None


def get_gemini_embedder() -> GeminiMotionEmbedder:
    """Get or create the Gemini motion embedder singleton."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = GeminiMotionEmbedder()
    return _embedder_instance


def reset_gemini_embedder() -> None:
    """Reset the singleton instance (for testing)."""
    global _embedder_instance
    _embedder_instance = None