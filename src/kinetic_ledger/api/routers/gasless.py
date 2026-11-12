"""HTTP routes for this API domain."""

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ...utils.logging import set_correlation_id
from .commerce_runtime import *  # noqa: F401,F403

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/api/v2/gasless/transfer")
async def execute_gasless_transfer(
    request: GaslessTransferRequest,
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Execute a gasless USDC transfer via EIP-7702.
    
    Gas is sponsored by the platform gas budget (40% replenish threshold).
    """
    if not HAS_V2_SERVICES:
        raise HTTPException(status_code=501, detail="V2 services not available")
    
    if x_correlation_id:
        set_correlation_id(x_correlation_id)
    
    logger.info(f"[API] POST /api/v2/gasless/transfer: {request.amount_usdc} USDC")
    
    try:
        executor = get_gasless_executor()
        result = await executor.send_gasless_tx(
            to_address=request.to_address,
            amount_usdc=request.amount_usdc,
        )
        
        return {
            "success": result.success,
            "tx_hash": result.tx_hash,
            "gas_sponsored": result.gas_sponsored,
            "gas_cost_usdc": result.gas_cost_usdc,
        }
    except Exception as e:
        logger.error(f"Gasless transfer failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v2/gasless/budget")
async def get_gas_sponsor_budget(
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Get the current gas sponsor budget status.
    
    Returns current balance and whether replenishment is needed (40% threshold).
    """
    if not HAS_V2_SERVICES:
        raise HTTPException(status_code=501, detail="V2 services not available")
    
    if x_correlation_id:
        set_correlation_id(x_correlation_id)
    
    logger.info("[API] GET /api/v2/gasless/budget")
    
    try:
        executor = get_gasless_executor()
        balance = await executor.get_gas_budget_balance()
        threshold = executor.config.initial_budget * GAS_SPONSOR_REPLENISH_THRESHOLD
        
        return {
            "current_balance": balance,
            "initial_budget": executor.config.initial_budget,
            "threshold": threshold,
            "threshold_percentage": GAS_SPONSOR_REPLENISH_THRESHOLD * 100,
            "needs_replenishment": balance < threshold,
        }
    except Exception as e:
        logger.error(f"Failed to get gas budget: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
