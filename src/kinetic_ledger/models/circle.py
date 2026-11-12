from typing import List, Optional, Literal, Dict
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Circle Wallet Models
# =============================================================================


class CircleWallet(BaseModel):
    """Circle Programmable Wallet representation."""
    
    wallet_id: str
    address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    blockchain: Literal["ARC", "ETH", "MATIC", "SOL"] = "ARC"
    status: Literal["ACTIVE", "PENDING", "FROZEN"] = "ACTIVE"
    created_at: int
    user_id: Optional[str] = None
    wallet_set_id: Optional[str] = None


class CircleTransfer(BaseModel):
    """USDC transfer record."""
    
    transfer_id: str
    source_wallet_id: str
    destination_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    amount_usdc: str  # Decimal string (e.g., "10.50")
    status: Literal["PENDING", "CONFIRMED", "FAILED"] = "PENDING"
    tx_hash: Optional[str] = None
    chain: str = "ARC"
    created_at: int
    confirmed_at: Optional[int] = None
    error_message: Optional[str] = None
