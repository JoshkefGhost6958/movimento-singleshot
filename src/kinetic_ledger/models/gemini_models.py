from typing import List, Optional, Literal, Dict
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator



class ModelDescriptor(BaseModel):
    provider: str
    name: str
    version: str

class GeminiInputs(BaseModel):
    preview_uri: str
    metadata_ref: Optional[str] = None

class GeminiOutputs(BaseModel):
    style_labels: List[str]
    transition_window: Dict[str, int]
    npc_tags: List[str]
    safety_flags: List[str]
    summary: Optional[str] = None

class GeminiAnalysis(BaseModel):
    analysis_id: str
    request_id: str
    created_at: int
    model: ModelDescriptor
    inputs: GeminiInputs
    outputs: GeminiOutputs


# Machine learning and finetuning 
class FeatureSpace(BaseModel):
    embedding_dim: int = Field(ge=1)
    embedding_model_id: str
    distance: Literal["euclidean", "cosine", "manhattan"]

class KNNNeighbor(BaseModel):
    motion_id: str
    dist: float = Field(ge=0)

class KNNResult(BaseModel):
    k: int = Field(ge=1)
    neighbors: List[KNNNeighbor]
    min_dist: float = Field(ge=0)

class RkCNNResult(BaseModel):
    k: int = Field(ge=1)
    ensemble_size: int = Field(ge=1)
    subspace_dim: int = Field(ge=1)
    vote_margin: float = Field(ge=0, le=1)
    separation_score: float = Field(ge=0, le=1)

class Decision(BaseModel):
    novelty_threshold: float = Field(ge=0, le=1)
    result: Literal["MINT", "REJECT", "REVIEW"]
    reason: Optional[str] = None

class SimilarityCheck(BaseModel):
    similarity_id: str
    analysis_id: str
    created_at: int
    feature_space: FeatureSpace
    knn: KNNResult
    rkcnn: RkCNNResult
    decision: Decision
