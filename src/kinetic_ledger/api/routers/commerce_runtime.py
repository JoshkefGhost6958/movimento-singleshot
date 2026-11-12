"""Shared dependencies for Circle, payment, royalty, and gasless routes."""

import logging
from typing import Any, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# API V2: Circle Wallets, x402 Payments, and Royalty Chain Endpoints
# ============================================================================

# Import new services (optional - may not be installed)
try:
    from ...services.circle_wallets import CircleWalletsService, CircleWalletsConfig
    from ...services.x402_facilitator import X402FacilitatorService, X402FacilitatorConfig
    from ...services.payment_automation import PaymentAutomationService, PaymentAutomationConfig
    from ...services.gasless_executor import GaslessExecutor, GaslessExecutorConfig
    from ...services.gemini_oracle_attestor import GeminiOracleAttestor, GeminiOracleConfig
    from ...schemas.models import (
        RoyaltyChain,
        RoyaltyNode,
        PaymentTriggerEvent,
        RecursivePayoutResult,
        CircleWallet,
        CircleTransfer,
        DerivativeDetectionResult,
        ROYALTY_DECAY_FACTOR,
        MAX_ROYALTY_CHAIN_DEPTH,
        GAS_SPONSOR_REPLENISH_THRESHOLD,
    )
    HAS_V2_SERVICES = True
except ImportError as e:
    logger.warning(f"V2 services not available: {e}")
    HAS_V2_SERVICES = False


# V2 Service instances (lazy initialization)
_circle_service: Optional[Any] = None
_x402_service: Optional[Any] = None
_payment_service: Optional[Any] = None
_gasless_executor: Optional[Any] = None
_oracle_attestor: Optional[Any] = None


def get_circle_service():
    """Get or create Circle Wallets service instance."""
    global _circle_service
    if _circle_service is None and HAS_V2_SERVICES:
        config = CircleWalletsConfig()
        _circle_service = CircleWalletsService(config)
    return _circle_service


def get_x402_service():
    """Get or create x402 Facilitator service instance."""
    global _x402_service
    if _x402_service is None and HAS_V2_SERVICES:
        config = X402FacilitatorConfig()
        _x402_service = X402FacilitatorService(config)
    return _x402_service


def get_payment_service():
    """Get or create Payment Automation service instance."""
    global _payment_service
    if _payment_service is None and HAS_V2_SERVICES:
        config = PaymentAutomationConfig()
        _payment_service = PaymentAutomationService(config)
    return _payment_service


def get_gasless_executor():
    """Get or create Gasless Executor instance."""
    global _gasless_executor
    if _gasless_executor is None and HAS_V2_SERVICES:
        config = GaslessExecutorConfig()
        _gasless_executor = GaslessExecutor(config)
    return _gasless_executor


def get_oracle_attestor():
    """Get or create Gemini Oracle Attestor instance."""
    global _oracle_attestor
    if _oracle_attestor is None and HAS_V2_SERVICES:
        config = GeminiOracleConfig()
        _oracle_attestor = GeminiOracleAttestor(config)
    return _oracle_attestor


# ---- Request/Response Models for V2 API ----

class CreateWalletRequest(BaseModel):
    """Request to create a new Circle wallet."""
    idempotency_key: Optional[str] = None
    wallet_set_id: Optional[str] = None


class TransferUsdcRequest(BaseModel):
    """Request to transfer USDC between wallets."""
    from_wallet_id: str
    to_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    amount_usdc: str
    idempotency_key: Optional[str] = None


class X402SettlementRequest(BaseModel):
    """Request to settle an x402 payment."""
    x402_header: str
    expected_amount: Optional[str] = None


class RoyaltyPreviewRequest(BaseModel):
    """Request to preview royalty distribution."""
    motion_id: str
    base_amount: float = Field(ge=0.01)
    parent_motion_ids: List[str] = []


class DerivativeCheckRequest(BaseModel):
    """Request to check for derivative content."""
    motion_data_uri: str
    threshold: float = Field(default=0.85, ge=0.0, le=1.0)


class GaslessTransferRequest(BaseModel):
    """Request to execute a gasless USDC transfer."""
    to_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    amount_usdc: float = Field(ge=0.01)


# ---- V2 API Endpoints ----

