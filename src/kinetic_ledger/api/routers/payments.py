"""HTTP routes for this API domain."""

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ...utils.logging import set_correlation_id
from .commerce_runtime import *  # noqa: F401,F403

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/api/v2/payments/verify")
async def verify_x402_payment(
    x_402_payment: str = Header(..., alias="X-402-Payment"),
    expected_amount: Optional[str] = Header(None, alias="X-Expected-Amount"),
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Verify an x402 payment proof from HTTP header.
    
    Used for pay-per-request API access and motion content purchases.
    """
    if not HAS_V2_SERVICES:
        raise HTTPException(status_code=501, detail="V2 services not available")
    
    if x_correlation_id:
        set_correlation_id(x_correlation_id)
    
    logger.info("[API] POST /api/v2/payments/verify")
    
    try:
        service = get_x402_service()
        result = await service.verify_payment(
            x402_header=x_402_payment,
            expected_amount=expected_amount,
        )
        
        if not result.valid:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "payment_required",
                    "message": result.error_message or "Invalid payment proof",
                    "receipt_id": result.receipt_id,
                },
            )
        
        return {
            "valid": True,
            "receipt_id": result.receipt_id,
            "amount": result.amount,
            "timestamp": result.timestamp,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment verification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v2/payments/settle")
async def settle_x402_payment(
    request: X402SettlementRequest,
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Settle an x402 payment and execute the USDC transfer on-chain.
    """
    if not HAS_V2_SERVICES:
        raise HTTPException(status_code=501, detail="V2 services not available")
    
    if x_correlation_id:
        set_correlation_id(x_correlation_id)
    
    logger.info("[API] POST /api/v2/payments/settle")
    
    try:
        service = get_x402_service()
        result = await service.settle_payment(
            x402_header=request.x402_header,
        )
        
        if not result.success:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "settlement_failed",
                    "message": result.error_message,
                    "tx_hash": result.tx_hash,
                },
            )
        
        return {
            "success": True,
            "tx_hash": result.tx_hash,
            "chain": result.chain,
            "amount": result.amount,
            "timestamp": result.timestamp,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment settlement failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v2/payments/supported")
async def get_supported_payment_methods():
    """
    Get supported x402 payment methods.
    """
    if not HAS_V2_SERVICES:
        raise HTTPException(status_code=501, detail="V2 services not available")
    
    try:
        service = get_x402_service()
        methods = await service.get_supported_methods()
        
        return {
            "methods": [m.model_dump() if hasattr(m, 'model_dump') else m for m in methods],
        }
    except Exception as e:
        logger.error(f"Failed to get payment methods: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/api/v2/config/constants")
async def get_global_constants():
    """
    Get global configuration constants for the payment system.
    """
    if not HAS_V2_SERVICES:
        return {
            "royalty_decay_factor": 0.5,
            "max_royalty_chain_depth": 10,
            "gas_sponsor_replenish_threshold": 0.40,
            "v2_services_available": False,
        }
    
    return {
        "royalty_decay_factor": ROYALTY_DECAY_FACTOR,
        "max_royalty_chain_depth": MAX_ROYALTY_CHAIN_DEPTH,
        "gas_sponsor_replenish_threshold": GAS_SPONSOR_REPLENISH_THRESHOLD,
        "v2_services_available": True,
    }
@router.post("/api/v2/wallets/create")
async def create_circle_wallet(
    request: CreateWalletRequest,
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Create a new Circle Programmable Wallet.
    
    Creates a developer-controlled wallet on the Arc testnet (or mainnet if enabled).
    """
    if not HAS_V2_SERVICES:
        raise HTTPException(status_code=501, detail="V2 services not available")
    
    if x_correlation_id:
        set_correlation_id(x_correlation_id)
    
    logger.info("[API] POST /api/v2/wallets/create")
    
    try:
        service = get_circle_service()
        wallet = await service.create_developer_wallet(
            idempotency_key=request.idempotency_key,
            wallet_set_id=request.wallet_set_id,
        )
        
        return {
            "success": True,
            "wallet": wallet.model_dump() if hasattr(wallet, 'model_dump') else wallet,
        }
    except Exception as e:
        logger.error(f"Wallet creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v2/wallets/{wallet_id}/balance")
async def get_wallet_balance(
    wallet_id: str,
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Get the USDC balance of a Circle wallet.
    """
    if not HAS_V2_SERVICES:
        raise HTTPException(status_code=501, detail="V2 services not available")
    
    if x_correlation_id:
        set_correlation_id(x_correlation_id)
    
    logger.info(f"[API] GET /api/v2/wallets/{wallet_id}/balance")
    
    try:
        service = get_circle_service()
        balance = await service.get_wallet_balance(wallet_id)
        
        return {
            "wallet_id": wallet_id,
            "balance": balance.model_dump() if hasattr(balance, 'model_dump') else balance,
        }
    except Exception as e:
        logger.error(f"Balance fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v2/wallets/{wallet_id}/transactions")
async def get_wallet_transactions(
    wallet_id: str,
    limit: int = 20,
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Get recent transactions for a Circle wallet.
    """
    if not HAS_V2_SERVICES:
        raise HTTPException(status_code=501, detail="V2 services not available")
    
    if x_correlation_id:
        set_correlation_id(x_correlation_id)
    
    logger.info(f"[API] GET /api/v2/wallets/{wallet_id}/transactions")
    
    try:
        service = get_circle_service()
        # Get transaction history
        # Note: This would need to be implemented in the CircleWalletsService
        return {
            "wallet_id": wallet_id,
            "transactions": [],
            "message": "Transaction history not yet implemented",
        }
    except Exception as e:
        logger.error(f"Transaction fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v2/wallets/transfer")
async def transfer_usdc(
    request: TransferUsdcRequest,
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
):
    """
    Transfer USDC between wallets.
    """
    if not HAS_V2_SERVICES:
        raise HTTPException(status_code=501, detail="V2 services not available")
    
    if x_correlation_id:
        set_correlation_id(x_correlation_id)
    
    logger.info(f"[API] POST /api/v2/wallets/transfer: {request.amount_usdc} USDC")
    
    try:
        service = get_circle_service()
        transfer = await service.transfer_usdc(
            from_wallet_id=request.from_wallet_id,
            to_address=request.to_address,
            amount_usdc=request.amount_usdc,
            idempotency_key=request.idempotency_key,
        )
        
        return {
            "success": True,
            "transfer": transfer.model_dump() if hasattr(transfer, 'model_dump') else transfer,
        }
    except Exception as e:
        logger.error(f"Transfer failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
