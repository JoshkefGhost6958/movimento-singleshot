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


class PromptAnalyzeRequest(BaseModel):
    """Request to analyze motion prompt."""
    prompt: str
    wallet: Optional[str] = None


@router.post("/api/prompts/analyze")
async def analyze_prompt(request: PromptAnalyzeRequest):
    """
    Analyze natural language prompt for motion blending.
    
    Uses simple keyword parsing (in production: use Gemini AI).
    """
    logger.info(f"Analyzing prompt: {request.prompt}")
    
    prompt_lower = request.prompt.lower()
    
    # Extract motion keywords
    motion_keywords = {
        'walk': ['walk', 'walking'],
        'run': ['run', 'running', 'sprint'],
        'dance': ['dance', 'dancing'],
        'capoeira': ['capoeira'],
        'breakdance': ['breakdance', 'break dance', 'freeze'],
        'jump': ['jump', 'jumping'],
        'idle': ['idle', 'stand', 'standing'],
        'combat': ['fight', 'combat', 'punch', 'kick']
    }
    
    detected_motions = []
    for motion, keywords in motion_keywords.items():
        if any(keyword in prompt_lower for keyword in keywords):
            detected_motions.append(motion)
    
    # Default to capoeira and breakdance if nothing detected
    if not detected_motions:
        detected_motions = ['capoeira', 'breakdance']
    elif len(detected_motions) == 1:
        detected_motions.append('idle')  # Add idle as second motion
    
    # Extract weight if specified
    weights = [0.5, 0.5]  # Default 50/50
    

    # Look for percentage patterns
    import re
    percent_match = re.search(r'(\d+)%', prompt_lower)
    if percent_match:
        percent = int(percent_match.group(1)) / 100
        weights = [1 - percent, percent]
    
    # Estimate complexity based on prompt length
    complexity = min(len(request.prompt) / 50, 2.0)
    
    blend_id = f"blend-{uuid.uuid4().hex[:8]}"
    
    return {
        "blend_id": blend_id,
        "motions": detected_motions[:2],  # Take first two
        "weights": weights,
        "estimated_duration": 5.0 + complexity,
        "complexity": complexity,
        "transition_type": "smooth" if "smooth" in prompt_lower else "quick"
    }
