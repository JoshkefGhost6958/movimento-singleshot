"""Typed HTTP routes for verified FBX motion ingestion."""

from fastapi import APIRouter, HTTPException, status

from ...schemas.motions import MotionAssetResponse, MotionInspectionResponse, MotionUploadRequest
from ...services.motion_ingest import inspect_upload, ingest_upload

router = APIRouter(prefix="/motion", tags=["motion"])


@router.post("/inspect", response_model=MotionInspectionResponse)
def inspect_motion(request: MotionUploadRequest) -> MotionInspectionResponse:
    """Parse and validate an FBX without writing artifacts."""
    try:
        return inspect_upload(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/ingest", response_model=MotionAssetResponse, status_code=status.HTTP_201_CREATED)
def ingest_motion(request: MotionUploadRequest) -> MotionAssetResponse:
    """Parse a real FBX and persist its source, tensor, and parse manifest."""
    try:
        return ingest_upload(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
