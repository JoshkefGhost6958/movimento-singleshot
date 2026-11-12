"""
Motion Frame Renderer Utility.

Renders motion position data into 2D skeleton frames for visualization
and Gemini multimodal analysis. Uses numpy for projection - no external
rendering dependencies required.

Features:
- render_frames_from_positions(): Convert [T, J, D] positions to RGB frames
- create_standard_skeleton_hierarchy(): Build joint tree for Mixamo skeletons
- Skeleton stick-figure rendering with joint connections
"""
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .logging import get_logger

logger = get_logger(__name__)


# Standard Mixamo joint hierarchy (parent index for each joint)
MIXAMO_SKELETON_HIERARCHY: Dict[str, int] = {
    "Hips": -1,          # Root
    "Spine": 0,          # Hips
    "Spine1": 1,         # Spine
    "Spine2": 2,         # Spine1
    "Neck": 3,           # Spine2
    "Head": 4,           # Neck
    "LeftShoulder": 3,   # Spine2
    "LeftArm": 6,        # LeftShoulder
    "LeftForeArm": 7,    # LeftArm
    "LeftHand": 8,       # LeftForeArm
    "RightShoulder": 3,  # Spine2
    "RightArm": 10,      # RightShoulder
    "RightForeArm": 11,  # RightArm
    "RightHand": 12,     # RightForeArm
    "LeftUpLeg": 0,      # Hips
    "LeftLeg": 14,       # LeftUpLeg
    "LeftFoot": 15,      # LeftLeg
    "LeftToeBase": 16,   # LeftFoot
    "RightUpLeg": 0,     # Hips
    "RightLeg": 18,      # RightUpLeg
    "RightFoot": 19,     # RightLeg
    "RightToeBase": 20,  # RightFoot
    "LeftEye": 5,        # Head
    "RightEye": 5,       # Head
}


def create_standard_skeleton_hierarchy(num_joints: int) -> Dict[str, Any]:
    """
    Create a standard skeleton hierarchy for rendering.
    
    Args:
        num_joints: Number of joints in the skeleton
        
    Returns:
        Dict with 'joint_names' and 'parent_indices' for rendering
    """
    # Use standard Mixamo joint names if count matches
    standard_names = list(MIXAMO_SKELETON_HIERARCHY.keys())
    
    if num_joints <= len(standard_names):
        joint_names = standard_names[:num_joints]
    else:
        # Generate generic joint names
        joint_names = [f"Joint{i}" for i in range(num_joints)]
    
    # Build parent indices
    parent_indices = []
    for i, name in enumerate(joint_names):
        if name in MIXAMO_SKELETON_HIERARCHY:
            parent = MIXAMO_SKELETON_HIERARCHY[name]
            parent_indices.append(parent)  # -1 for root, index for others
        else:
            # Connect to previous joint or root
            parent_indices.append(-1 if i == 0 else 0)
    
    return {
        "joint_names": joint_names,
        "parent_indices": parent_indices,
        "num_joints": num_joints,
    }


class MotionFrameRenderer:
    """
    Renders motion frames as 2D skeleton stick figures.
    
    Provides simple orthographic projection of 3D joint positions
    to 2D image frames for visualization and analysis.
    """
    
    def __init__(self, width: int = 640, height: int = 480):
        """
        Initialize the frame renderer.
        
        Args:
            width: Output frame width in pixels
            height: Output frame height in pixels
        """
        self.width = width
        self.height = height
        logger.info(f"MotionFrameRenderer initialized: {width}x{height}")
    
    def render_frames_from_positions(
        self,
        positions: np.ndarray,
        skeleton_hierarchy: Optional[Dict[str, Any]] = None,
        frame_indices: Optional[List[int]] = None,
    ) -> List[np.ndarray]:
        """
        Render motion positions as RGB frame images.
        
        Args:
            positions: Motion positions [T, J, 3]
            skeleton_hierarchy: Skeleton hierarchy dict from create_standard_skeleton_hierarchy()
            frame_indices: Indices of frames to render (default: all)
        
        Returns:
            List of RGB numpy arrays [H, W, 3] for each requested frame
        """
        positions = np.asarray(positions, dtype=np.float32)
        
        if positions.ndim != 3 or positions.shape[2] != 3:
            raise ValueError(f"Expected positions [T, J, 3], got {positions.shape}")
        
        T, J, D = positions.shape
        
        if skeleton_hierarchy is None:
            skeleton_hierarchy = create_standard_skeleton_hierarchy(J)
        
        parent_indices = skeleton_hierarchy.get("parent_indices", [])
        
        if frame_indices is None:
            frame_indices = list(range(T))
        
        # Compute global bounds for scaling
        all_pos = positions.reshape(-1, 3)
        min_vals = all_pos.min(axis=0)
        max_vals = all_pos.max(axis=0)
        
        # Use X (forward) and Y (up) for 2D projection
        x_range = max_vals[0] - min_vals[0]
        y_range = max_vals[2] - min_vals[2]  # Use Z as depth → Y in image
        x_range = max(x_range, 0.1)
        y_range = max(y_range, 0.1)
        
        frames = []
        
        for frame_idx in frame_indices:
            if frame_idx >= T:
                logger.warning(f"Frame index {frame_idx} out of range (T={T})")
                continue
            
            frame = self._render_single_frame(
                positions[frame_idx],
                parent_indices,
                min_vals,
                x_range,
                y_range,
            )
            frames.append(frame)
        
        logger.info(f"Rendered {len(frames)} frames from {T} total")
        return frames
    
    def _render_single_frame(
        self,
        frame_positions: np.ndarray,
        parent_indices: List[int],
        min_vals: np.ndarray,
        x_range: float,
        y_range: float,
    ) -> np.ndarray:
        """
        Render a single frame as RGB image.
        
        Args:
            frame_positions: Joint positions [J, 3]
            parent_indices: Parent index for each joint
            min_vals: Global minimum values
            x_range: X range for scaling
            y_range: Y range for scaling
        
        Returns:
            RGB image as numpy array [H, W, 3]
        """
        # Create black background
        image = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Map 3D positions to 2D screen coordinates
        screen_points = []
        for joint_pos in frame_positions:
            # Project X (forward) → screen X, Z (up) → screen Y
            sx = int((joint_pos[0] - min_vals[0]) / x_range * (self.width - 40) + 20)
            sy = int(self.height - 20 - (joint_pos[2] - min_vals[2]) / y_range * (self.height - 40))
            
            # Clamp to image bounds
            sx = max(0, min(self.width - 1, sx))
            sy = max(0, min(self.height - 1, sy))
            screen_points.append((sx, sy))
        
        # Draw joints as green dots
        joint_color = (0, 255, 0)
        for sx, sy in screen_points:
            self._draw_circle(image, sx, sy, 3, joint_color)
        
        # Draw bone connections as white lines
        bone_color = (255, 255, 255)
        for i, parent_idx in enumerate(parent_indices):
            if parent_idx >= 0 and parent_idx < len(screen_points):
                self._draw_line(
                    image,
                    screen_points[parent_idx][0], screen_points[parent_idx][1],
                    screen_points[i][0], screen_points[i][1],
                    bone_color,
                )
        
        return image
    
    def _draw_circle(
        self,
        image: np.ndarray,
        cx: int,
        cy: int,
        radius: int,
        color: Tuple[int, int, int],
    ) -> None:
        """Draw a filled circle on the image."""
        y, x = np.ogrid[:self.height, :self.width]
        mask = (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2
        image[mask] = color
    
    def _draw_line(
        self,
        image: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: Tuple[int, int, int],
        thickness: int = 2,
    ) -> None:
        """Draw a line on the image using Bresenham's algorithm."""
        x1 = max(0, min(self.width - 1, x1))
        y1 = max(0, min(self.height - 1, y1))
        x2 = max(0, min(self.width - 1, x2))
        y2 = max(0, min(self.height - 1, y2))
        
        dx = abs(x2 - x1)
        dy = -abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx + dy
        
        while True:
            # Draw pixel with thickness
            for ty in range(-thickness // 2, thickness // 2 + 1):
                for tx in range(-thickness // 2, thickness // 2 + 1):
                    px = x1 + tx
                    py = y1 + ty
                    if 0 <= px < self.width and 0 <= py < self.height:
                        image[py, px] = color
            
            if x1 == x2 and y1 == y2:
                break
            
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x1 += sx
            if e2 <= dx:
                err += dx
                y1 += sy


# Singleton instance
_renderer_instance: Optional[MotionFrameRenderer] = None


def get_frame_renderer(width: int = 640, height: int = 480) -> MotionFrameRenderer:
    """Get or create the frame renderer singleton."""
    global _renderer_instance
    if _renderer_instance is None:
        _renderer_instance = MotionFrameRenderer(width=width, height=height)
    return _renderer_instance


def reset_frame_renderer() -> None:
    """Reset the singleton instance (for testing)."""
    global _renderer_instance
    _renderer_instance = None