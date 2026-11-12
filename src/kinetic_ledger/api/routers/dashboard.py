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


@router.get("/api/metrics/info")
def get_metrics_info():
    """Get information about blendanim metrics."""
    return {
        "metrics": {
            "coverage": {
                "description": "Motion space coverage (0-1 scale)",
                "range": [0.0, 1.0],
                "higher_is_better": True,
                "calculation": "30-frame sliding window with cost threshold 2.0"
            },
            "local_diversity": {
                "description": "Short-term variation (15-frame windows)",
                "range": [0.0, "unbounded"],
                "interpretation": "Lower for similar motions, higher for diverse",
                "calculation": "Per-window cost analysis"
            },
            "global_diversity": {
                "description": "Long-term variation via NN-DP alignment",
                "range": [0.0, "unbounded"],
                "higher_is_better": True,
                "calculation": "30-frame dynamic programming alignment"
            },
            "l2_velocity": {
                "description": "Velocity smoothness metric",
                "range": [0.0, "unbounded"],
                "lower_is_better": True,
                "calculation": "L2 norm of frame-to-frame velocity differences"
            },
            "l2_acceleration": {
                "description": "Acceleration smoothness (jerk)",
                "range": [0.0, "unbounded"],
                "lower_is_better": True,
                "calculation": "L2 norm of velocity-to-velocity differences"
            }
        }
    }


@router.get("/api/video/status/{operation_name}")
async def get_video_status(operation_name: str):
    """
    Poll Veo video generation status.
    
    Returns:
        - status: "processing" | "completed" | "failed"
        - progress: 0-100
        - video_uri: Download URI when completed
    """
    from ...services.veo_video_service import get_veo_service
    
    veo_service = get_veo_service()
    if not veo_service.is_available():
        raise HTTPException(503, "Veo service not available")
    
    try:
        correlation_id = operation_name.split("/")[-1]  # Extract ID from operation name
        result = await veo_service.poll_video_status(
            operation_name=operation_name,
            correlation_id=correlation_id
        )
        return result
    except Exception as e:
        logger.error(f"Video status check failed: {e}")
        raise HTTPException(500, str(e))


# =============================================================================
# Previous metrics info endpoint continues below
# =============================================================================

@router.get("/api/metrics/old-info")  # Renamed to avoid conflict
def get_old_metrics_info():
    """Get information about blendanim metrics (old version)."""
    return {
        "metrics": {
            "coverage": {
                "description": "Motion space coverage (0-1 scale)",
                "range": [0.0, 1.0],
                "higher_is_better": True,
                "calculation": "30-frame sliding window with cost threshold 2.0"
            },
            "local_diversity": {
                "description": "Short-term variation (15-frame windows)",
                "range": [0.0, "unbounded"],
                "interpretation": "Lower for similar motions, higher for diverse",
                "calculation": "Per-window cost analysis"
            },
            "global_diversity": {
                "description": "Long-term variation via NN-DP alignment",
                "range": [0.0, "unbounded"],
                "higher_is_better": True,
                "calculation": "30-frame dynamic programming alignment"
            },
            "l2_velocity": {
                "description": "Velocity smoothness metric",
                "range": [0.0, "unbounded"],
                "lower_is_better": True,
                "calculation": "L2 norm of velocity deltas, focus on blend area"
            },
            "l2_acceleration": {
                "description": "Jerk minimization (acceleration smoothness)",
                "range": [0.0, "unbounded"],
                "lower_is_better": True,
                "calculation": "Delta of velocity changes, per-joint analysis"
            }
        },
        "reference": "Aligned with https://github.com/RydlrCS/blendanim",
        "documentation": "/docs/BLEND_METRICS.md"
    }

@router.get("/api/metrics/{blend_id}/timeline")
def get_metrics_timeline(blend_id: str):
    """
    Get frame-by-frame quality metrics timeline for a blend.
    
    Returns detailed metrics data for visualization:
    - Coverage values per 30-frame window
    - Local/Global diversity scores
    - Per-joint L2 velocity and acceleration
    - Quality tier progression
    
    Args:
        blend_id: Unique identifier for the blend
    
    Returns:
        Metrics timeline data for charts
    
    Raises:
        HTTPException: 404 if blend not found
    """
    logger.info(f"[GET /api/metrics/{blend_id}/timeline] Fetching metrics timeline")
    
    # TODO: Retrieve from database/cache
    # For now, return mock data structure
    
    return {
        "blend_id": blend_id,
        "coverage_timeline": [0.82, 0.85, 0.87, 0.89, 0.91, 0.88, 0.86],
        "diversity": {
            "local": 2.45,
            "global": 3.67
        },
        "per_joint_metrics": {
            "Pelvis": {"l2_velocity": 0.045, "l2_acceleration": 0.022},
            "LeftWrist": {"l2_velocity": 0.067, "l2_acceleration": 0.034},
            "RightWrist": {"l2_velocity": 0.063, "l2_acceleration": 0.031},
            "LeftFoot": {"l2_velocity": 0.052, "l2_acceleration": 0.025},
            "RightFoot": {"l2_velocity": 0.054, "l2_acceleration": 0.027}
        },
        "cost_breakdown": {
            "generation_cost": 0.075,
            "quality_premium": 0.025,
            "base_fee": 0.010
        },
        "quality_tier": "high",
        "total_frames": 210,
        "blend_window": [60, 150]
    }
