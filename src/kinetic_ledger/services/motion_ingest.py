"""Local, deterministic motion ingestion using the installed FBX parser."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..schemas.motions import (
    MotionAssetResponse,
    MotionInspectionResponse,
    MotionUploadRequest,
    TensorGenerationConfig,
)
from ..utils.fbx_parser import get_fbx_parser


def _decode(content_base64: str) -> bytes:
    payload = content_base64.split(",", 1)[1] if content_base64.startswith("data:") else content_base64
    try:
        content = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid base64 motion content: {exc}") from exc
    if not content:
        raise ValueError("Motion content is empty")
    return content

def _hash(content: bytes) -> str:
    return f"0x{hashlib.sha256(content).hexdigest()}"

def _uri(path: Path) -> str:
    return path.resolve().as_uri()

def inspect_upload(request: MotionUploadRequest) -> MotionInspectionResponse:
    content = _decode(request.content_base64)
    if request.content_type != "model/fbx" or not request.filename.lower().endswith(".fbx"):
        raise ValueError("Only .fbx files with content type model/fbx are supported")
    parsed = get_fbx_parser().parse_fbx_bytes(content, request.filename)
    return MotionInspectionResponse(
        filename=request.filename, source_sha256=_hash(content), format="fbx",
        parser=parsed.metadata["parser"], frame_count=parsed.frame_count,
        joint_count=len(parsed.joint_names), source_fps=parsed.fps,
        joint_names=parsed.joint_names, metadata=parsed.metadata,
    )

def ingest_upload(request: MotionUploadRequest, artifact_root: str | Path | None = None) -> MotionAssetResponse:
    artifact_root = Path(artifact_root or os.getenv("MOTION_ARTIFACTS_DIR", "artifacts/motions"))
    inspection = inspect_upload(request)
    content = _decode(request.content_base64)
    parsed = get_fbx_parser().parse_fbx_bytes(content, request.filename)
    motion_id = str(uuid.uuid4())
    destination = artifact_root / motion_id
    destination.mkdir(parents=True, exist_ok=False)
    source_path = destination / request.filename
    source_path.write_bytes(content)
    tensor_path = destination / "motion.npz"
    np.savez_compressed(tensor_path, positions=parsed.positions, joint_names=np.asarray(parsed.joint_names), source_fps=np.asarray(parsed.fps), animation_frame_count=np.asarray(parsed.frame_count), representation=np.asarray(request.tensor_config.representation))
    manifest_path = destination / "parse-manifest.json"
    manifest_path.write_text(json.dumps(inspection.metadata, indent=2), encoding="utf-8")
    return MotionAssetResponse(
        motion_id=motion_id, created_at=int(datetime.now(timezone.utc).timestamp()), institution_id=request.institution_id, institution_wallet=request.institution_wallet,
        source={"type": "upload", "filename": request.filename, "content_type": request.content_type, "uri": _uri(source_path), "sha256": _hash(content)},
        tensor={"representation": request.tensor_config.representation, "fps": request.tensor_config.fps, "frame_count": parsed.frame_count, "joint_count": len(parsed.joint_names), "features": request.tensor_config.extract_features, "uri": _uri(tensor_path), "sha256": _hash(tensor_path.read_bytes())},
        preview={"uri": _uri(manifest_path), "sha256": _hash(manifest_path.read_bytes())},
        skeleton={"skeleton_id": request.skeleton_id, "retarget_profile": request.retarget_profile, "joint_map_uri": None},
    )
