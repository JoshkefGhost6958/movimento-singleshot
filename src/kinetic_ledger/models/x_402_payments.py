from typing import List, Optional, Literal, Dict
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator


class MintMessage(BaseModel):
    to: str
    pack_hash: str
    nonce: int
    expiry: int
    policy_digest: str

class MintAuthorization(BaseModel):
    chain_id: int
    verifying_contract: str
    message: MintMessage
    signature: str

class Metering(BaseModel):
    unit: Literal["seconds_generated", "frames_generated", "agent_steps"]
    quantity: float = Field(ge=0)
    unit_price_usdc: str
    total_usdc: str

class X402(BaseModel):
    payment_proof: str
    facilitator_receipt_id: str
    verified: bool

class Settlement(BaseModel):
    chain: str
    token: str
    tx_hash: str

class PayoutItem(BaseModel):
    to: str
    amount_usdc: str
    label: str

class UsageMeterEvent(BaseModel):
    usage_id: str
    created_at: int
    user_wallet: str
    attestation_pack_hash: str
    product: str
    metering: Metering
    x402: X402
    settlement: Settlement
    payout_split: List[PayoutItem]

class PayoutSplit(BaseModel):
    creator: float
    oracle: float
    platform: float
    ops: float

    @field_validator("creator", "oracle", "platform", "ops")
    @classmethod
    def _bounds(cls, v: float):
        if not (0.0 <= v <= 1.0):
            raise ValueError("payout percentages must be in [0,1]")
        return v

    @model_validator(mode="after")
    def _sum_to_one(self):
        total = self.creator + self.oracle + self.platform + self.ops
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"payout percentages must sum to 1.0, got {total}")
        return self

class EthicsModifiers(BaseModel):
    multipliers: Dict[str, float] = {}
    caps: Dict[str, float] = {}

    @field_validator("multipliers")
    @classmethod
    def _mult_bounds(cls, v: Dict[str, float]):
        for k, val in v.items():
            if not (0.0 <= val <= 2.0):
                raise ValueError(f"multiplier {k} out of bounds [0,2]")
        return v

    @field_validator("caps")
    @classmethod
    def _cap_bounds(cls, v: Dict[str, float]):
        for k, val in v.items():
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"cap {k} out of bounds [0,1]")
        return v


# =============================================================================
# Global Payment Constants
# =============================================================================

# Royalty decay factor: each parent level receives this fraction of child's creator share
ROYALTY_DECAY_FACTOR: float = 0.5

# Maximum depth for royalty chain traversal (prevent infinite loops)
MAX_ROYALTY_CHAIN_DEPTH: int = 10

# Gas sponsorship budget replenish threshold (40% of treasury)
GAS_SPONSOR_REPLENISH_THRESHOLD: float = 0.40

# Minimum USDC balance to trigger auto-replenish
GAS_SPONSOR_MIN_BALANCE_USDC: str = "100.00"

# Default payout percentages (basis points for on-chain, decimals for Python)
DEFAULT_CREATOR_SHARE_BPS: int = 7000  # 70%
DEFAULT_ORACLE_SHARE_BPS: int = 1000   # 10%
DEFAULT_PLATFORM_SHARE_BPS: int = 1500 # 15%
DEFAULT_OPS_SHARE_BPS: int = 500       # 5%




class WalletBalanceResponse(BaseModel):
    """Wallet balance query response."""
    
    wallet_id: str
    address: str
    total_usdc: str
    native_balance: str = "0.00"  # Native token (USDC on Arc)
    updated_at: int


# =============================================================================
# Royalty Chain Models
# =============================================================================


class RoyaltyNode(BaseModel):
    """
    Node in royalty chain - represents a single payout recipient.
    
    For infinite royalty chains, each motion can have a parent,
    and payouts flow recursively through the chain.
    """
    
    wallet: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    share_bps: int = Field(ge=0, le=10000, description="Share in basis points")
    role: Literal["creator", "oracle", "platform", "ops", "parent_creator"]
    depth: int = Field(ge=0, default=0, description="0=direct creator, 1+=ancestors")
    motion_id: Optional[str] = None  # Source motion for parent creators


class RoyaltyObligation(BaseModel):
    """
    Royalty obligation for derivative motions.
    
    When a motion is detected as derivative of another,
    this records the royalty owed to the original creator.
    """
    
    original_pack_hash: str = Field(pattern=r"^0x[a-fA-F0-9]{64}$")
    original_creator: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    original_motion_id: str
    royalty_percentage: float = Field(ge=0, le=1, default=0.10)
    derivation_score: float = Field(ge=0, le=1, description="Similarity score")


class RoyaltyChain(BaseModel):
    """
    Infinite-depth royalty chain for derivative motions.
    
    Supports recursive parent references for unlimited derivation depth.
    Payout calculation uses ROYALTY_DECAY_FACTOR per level.
    """
    
    motion_id: str
    nodes: List[RoyaltyNode]
    parent_motion_id: Optional[str] = None
    parent_chain: Optional["RoyaltyChain"] = None  # Recursive reference
    total_depth: int = Field(ge=0, default=0)
    
    @model_validator(mode="after")
    def _validate_total_shares(self) -> "RoyaltyChain":
        """Validate that non-parent shares sum to 10000 bps."""
        # Only validate direct nodes (not recursive parent shares)
        direct_nodes = [n for n in self.nodes if n.depth == 0]
        total = sum(n.share_bps for n in direct_nodes)
        if direct_nodes and total != 10000:
            raise ValueError(f"Direct shares must sum to 10000 bps, got {total}")
        return self


# Enable forward reference for recursive model
RoyaltyChain.model_rebuild()


class DerivativeDetectionResult(BaseModel):
    """Result of derivative/reuse detection analysis."""
    
    is_derivative: bool
    source_motion_id: Optional[str] = None
    source_pack_hash: Optional[str] = None
    similarity_score: float = Field(ge=0, le=1)
    detection_method: Literal["knn", "rkcnn", "gemini_vision", "combined"]
    royalty_obligations: List[RoyaltyObligation] = []
    reasoning: Optional[str] = None


# =============================================================================
# Uniqueness Attestation Models
# =============================================================================


class UniquenessAttestation(BaseModel):
    """
    Structured output schema for Gemini uniqueness attestation.
    
    Used with Gemini's structured output feature to get verifiable
    uniqueness assessments for blend artifacts.
    """
    
    blend_hash: str = Field(pattern=r"^0x[a-fA-F0-9]{64}$")
    is_unique: bool
    uniqueness_score: float = Field(ge=0, le=1)
    similar_motions: List[str] = []  # Motion IDs of similar existing motions
    visual_novelty_score: float = Field(ge=0, le=1)
    style_originality: str
    reasoning: str
    timestamp: int
    oracle_model: str = "gemini-2.5-pro"
    signature: Optional[str] = None
    
    def with_signature(self, sig: str) -> "UniquenessAttestation":
        """Return copy with signature attached."""
        return self.model_copy(update={"signature": sig})


# =============================================================================
# Payment Automation Models
# =============================================================================


class PaymentTriggerEvent(BaseModel):
    """Event triggered when on-chain mint is confirmed."""
    
    event_id: str
    pack_hash: str = Field(pattern=r"^0x[a-fA-F0-9]{64}$")
    motion_id: str
    tx_hash: str = Field(pattern=r"^0x[a-fA-F0-9]{64}$")
    creator_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    payout_amount_usdc: str
    royalty_chain: Optional[RoyaltyChain] = None
    triggered_at: int
    status: Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"] = "PENDING"


class GaslessReceipt(BaseModel):
    """Receipt for gasless transaction execution."""
    
    receipt_id: str
    original_tx_hash: str
    sponsor_address: str = Field(pattern=r"^0x[a-fA-F0-9]{40}$")
    paymaster_tx_hash: Optional[str] = None
    gas_sponsored_usdc: str
    eip7702_used: bool = True
    created_at: int

    
class RecursivePayoutResult(BaseModel):
    """Result of recursive payout calculation."""
    
    motion_id: str
    total_usdc: str
    payouts: List[PayoutItem]
    chain_depth: int
    decay_factor_used: float = ROYALTY_DECAY_FACTOR
    gas_estimate_usdc: str = "0.00"

class PolicyConfig(BaseModel):
    allowed_use: Literal["npc_generation"]
    safety_level: Literal["low", "standard", "high"] = "standard"
    base_rate: float = Field(ge=0)
    unit: Literal["USD/s", "ETH/s", "USD/h", "ETH/h"]
    max_seconds: int = Field(ge=0)
    payout_split: PayoutSplit
    ethics_modifiers: Optional[EthicsModifiers] = None
