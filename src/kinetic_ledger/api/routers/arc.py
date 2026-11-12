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

# ===========================
# Arc Network Tokenization
# ===========================

class ArtifactTokenizationRequest(BaseModel):
    """Request to tokenize a blend artifact on Arc Network."""
    artifact_data: Dict[str, Any] = Field(..., description="Complete artifact data from blend generation")
    buyer_address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$", description="Wallet address to receive NFT")
    price_usdc: float = Field(..., ge=0, description="Price in USDC")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


@router.post("/api/arc/tokenize-artifact")
async def tokenize_artifact(request: ArtifactTokenizationRequest):
    """
    Tokenize a blend artifact as an NFT on Arc testnet.
    
    This endpoint:
    1. Creates metadata JSON for the blend artifact
    2. Mints an NFT on Arc Network via NPCMotionRegistry
    3. Assigns ownership to the buyer's wallet
    4. Returns transaction hash and token ID
    
    Args:
        request: Artifact tokenization request with artifact data, buyer address, and price
    
    Returns:
        JSON with token_id, tx_hash, ipfs_uri, and metadata
    """
    try:
        logger.info(f"Tokenizing artifact for buyer: {request.buyer_address}")
        logger.info(f"  Price: {request.price_usdc} USDC")
        logger.info(f"  Artifact frames: {len(request.artifact_data.get('artifacts', []))}")
        
        # For hackathon demo: simulate tokenization (no real blockchain tx)
        # In production: would call ArcNetworkService.mint_motion_pack()
        
        # Generate mock token ID and tx hash
        import hashlib
        import time
        
        token_data = f"{request.buyer_address}{time.time()}{request.price_usdc}"
        token_id = int(hashlib.sha256(token_data.encode()).hexdigest()[:16], 16) % 1000000
        tx_hash = "0x" + hashlib.sha256(f"tx_{token_data}".encode()).hexdigest()
        
        # Create artifact metadata
        artifact_metadata = {
            "name": request.metadata.get("name", "Blend Artifact"),
            "description": f"Motion blend artifact with {len(request.artifact_data.get('artifacts', []))} frames",
            "frames": len(request.artifact_data.get('artifacts', [])),
            "duration_seconds": len(request.artifact_data.get('artifacts', [])) / 30,
            "motion_count": len(request.artifact_data.get('motion_segments', [])),
            "transition_count": request.artifact_data.get('total_transitions', 0),
            "created_at": request.metadata.get("created", ""),
            "creator": request.buyer_address,
            "price_usdc": request.price_usdc,
            "blend_mode": "smoothstep",
            "quality_tier": request.artifact_data.get('aggregate_metrics', {}).get('quality_tier', 'Standard'),
            "attributes": [
                {
                    "trait_type": "Frame Count",
                    "value": len(request.artifact_data.get('artifacts', []))
                },
                {
                    "trait_type": "Motion Sequences",
                    "value": len(request.artifact_data.get('motion_segments', []))
                },
                {
                    "trait_type": "Transitions",
                    "value": request.artifact_data.get('total_transitions', 0)
                },
                {
                    "trait_type": "Quality",
                    "value": request.artifact_data.get('aggregate_metrics', {}).get('quality_tier', 'Standard')
                }
            ]
        }
        
        # Mock IPFS URI (in production: upload to IPFS)
        ipfs_uri = f"ipfs://Qm{hashlib.sha256(token_data.encode()).hexdigest()[:44]}"
        
        logger.info(f"✅ Artifact tokenized successfully")
        logger.info(f"  Token ID: {token_id}")
        logger.info(f"  Transaction: {tx_hash}")
        logger.info(f"  IPFS URI: {ipfs_uri}")
        
        return {
            "success": True,
            "token_id": token_id,
            "tx_hash": tx_hash,
            "ipfs_uri": ipfs_uri,
            "metadata": artifact_metadata,
            "buyer": request.buyer_address,
            "price_usdc": request.price_usdc,
            "chain": "Arc Testnet",
            "chain_id": 52085143,
            "contract_address": os.getenv("NPC_MOTION_REGISTRY_ADDRESS", "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"),
            "message": "Artifact successfully tokenized on Arc testnet! (Demo mode - no real blockchain transaction)"
        }
        
    except Exception as e:
        logger.error(f"Tokenization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Tokenization failed: {str(e)}"
        )
