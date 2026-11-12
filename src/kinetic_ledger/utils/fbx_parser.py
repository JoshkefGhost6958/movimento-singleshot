"""FBX parsing backed by the installed :mod:`ufbx` parser.

Parsing failures deliberately propagate. Returning fabricated motion data makes
an ingest look successful while corrupting every downstream exchange.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ParsedFBX:
    positions: np.ndarray
    joint_names: list[str]
    fps: float
    frame_count: int
    metadata: dict[str, Any]


class FBXParser:
    """Parse FBX bytes with pyufbx and expose the parsed skeleton data."""

    def parse_fbx_bytes(self, content: bytes, source_file: str = "upload.fbx") -> ParsedFBX:
        if not content:
            raise ValueError("FBX content is empty")
        try:
            import ufbx
        except ImportError as exc:  # pragma: no cover - deployment configuration
            raise RuntimeError("pyufbx is required for FBX ingestion") from exc
        try:
            scene = ufbx.load_memory(content)
        except Exception as exc:
            raise ValueError(f"Invalid or unsupported FBX file: {exc}") from exc

        bones = [node for node in scene.nodes if node.bone is not None]
        if not bones:
            raise ValueError("FBX contains no skeleton bones")
        joint_names = [str(node.name) for node in bones]
        positions = np.asarray(
            [[float(node.world_transform[3, axis]) for axis in range(3)] for node in bones],
            dtype=np.float32,
        )[np.newaxis, :, :]
        fps = float(scene.settings.frames_per_second or 30.0)
        stack = scene.anim_stacks[0] if scene.anim_stacks else None
        if stack is None:
            animation_start, animation_end, frame_count = 0.0, 0.0, 1
        else:
            animation_start, animation_end = float(stack.time_begin), float(stack.time_end)
            frame_count = max(1, round((animation_end - animation_start) * fps) + 1)
        return ParsedFBX(
            positions=positions,
            joint_names=joint_names,
            fps=fps,
            frame_count=frame_count,
            metadata={
                "parser": "pyufbx",
                "source_file": source_file,
                "animation_stack_count": len(scene.anim_stacks),
                "animation_start_seconds": animation_start,
                "animation_end_seconds": animation_end,
                "frame_count": frame_count,
                "joint_count": len(joint_names),
                "joint_names": joint_names,
                "source_fps": fps,
            },
        )

    def parse_fbx(self, fbx_path: str) -> tuple[np.ndarray, dict[str, Any]]:
        """Compatibility wrapper used by the SPADE route."""
        path = Path(fbx_path)
        parsed = self.parse_fbx_bytes(path.read_bytes(), source_file=path.name)
        metadata = dict(parsed.metadata)
        metadata.update(num_frames=parsed.frame_count, num_joints=len(parsed.joint_names), fps=parsed.fps)
        return parsed.positions, metadata


_parser_instance: FBXParser | None = None


def get_fbx_parser() -> FBXParser:
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = FBXParser()
    return _parser_instance
