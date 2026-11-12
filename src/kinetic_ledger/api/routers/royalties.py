"""HTTP routes for this API domain."""

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ...utils.logging import set_correlation_id
from .commerce_runtime import *  # noqa: F401,F403

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/api/v2/royalties/preview")
async def preview_royalty_distribution(
    request: RoyaltyPreviewRequest,
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Preview royalty distribution for a motion with derivative chain.
    
    Calculates the recursive payout distribution using:
    - ROYALTY_DECAY_FACTOR: 50% per level
    - MAX_ROYALTY_CHAIN_DEPTH: 10 levels
    """
    if not HAS_V2_SERVICES:
        raise HTTPException(status_code=501, detail="V2 services not available")
    
    if x_correlation_id:
        set_correlation_id(x_correlation_id)
    
    logger.info(f"[API] POST /api/v2/royalties/preview: {request.base_amount} USDC")
    
    try:
        service = get_payment_service()
        
        # Build a simple royalty chain for preview
        # In production, this would fetch from the registry
        nodes = []
        for i, parent_id in enumerate(request.parent_motion_ids[:MAX_ROYALTY_CHAIN_DEPTH]):
            royalty_rate = 0.10 * (ROYALTY_DECAY_FACTOR ** i)  # 10% base, decayed
            nodes.append({
                "motion_id": parent_id,
                "wallet_address": f"0x{'0' * 39}{i + 1}",  # Placeholder
                "royalty_percentage": royalty_rate,
                "depth": i,
            })
        
        # Calculate payouts
        payouts = []
        total_royalties = 0
        
        for i, node in enumerate(nodes):
            amount = request.base_amount * node["royalty_percentage"]
            if amount >= 0.01:  # Minimum $0.01
                payouts.append({
                    "motion_id": node["motion_id"],
                    "wallet_address": node["wallet_address"],
                    "amount_usdc": round(amount, 6),
                    "depth": i,
                    "percentage": round(node["royalty_percentage"] * 100, 2),
                })
                total_royalties += amount
        
        creator_amount = request.base_amount - total_royalties
        
        return {
            "motion_id": request.motion_id,
            "base_amount": request.base_amount,
            "royalty_payouts": payouts,
            "total_royalties": round(total_royalties, 6),
            "creator_amount": round(creator_amount, 6),
            "chain_depth": len(payouts),
            "decay_factor": ROYALTY_DECAY_FACTOR,
            "max_depth": MAX_ROYALTY_CHAIN_DEPTH,
        }
    except Exception as e:
        logger.error(f"Royalty preview failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v2/derivatives/check")
async def check_derivative_content(
    request: DerivativeCheckRequest,
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Check if motion content is a derivative of existing registered motions.
    
    Uses KNN similarity search to find potential parent motions.
    """
    if not HAS_V2_SERVICES:
        raise HTTPException(status_code=501, detail="V2 services not available")
    
    if x_correlation_id:
        set_correlation_id(x_correlation_id)
    
    logger.info("[API] POST /api/v2/derivatives/check")
    
    try:
        attestor = get_oracle_attestor()
        result = await attestor.detect_derivative(
            motion_data_uri=request.motion_data_uri,
            threshold=request.threshold,
        )
        
        return {
            "is_derivative": result.is_derivative,
            "similarity_score": result.similarity_score,
            "parent_motion_id": result.parent_motion_id,
            "parent_creator": result.parent_creator,
            "recommended_royalty": result.recommended_royalty,
            "confidence": result.confidence,
        }
    except Exception as e:
        logger.error(f"Derivative check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
