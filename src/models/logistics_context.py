from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class SupplierDetails(BaseModel):
    """Details for a specific supplier of an ingredient."""
    supplier_id: int
    name: str
    match_confidence: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    distance_km: Optional[float] = None
    stocked_ingredients: List[str] = Field(default_factory=list)

class SourcedMaterial(BaseModel):
    """A chemical substitute from Phase 2 enriched with Phase 3 supply chain metrics."""
    substitute_name: str
    confidence_score: int
    reasoning: str
    price_per_kg: Optional[float] = None
    suppliers: List[SupplierDetails] = Field(default_factory=list)

class LogisticsContext(BaseModel):
    """
    The strictly typed data model injected into the Phase 4 LLM Prompt to determine
    the optimal supply chain sourcing for the verified chemical substitutes.
    """
    target_ingredient: str
    company_coords: List[float]
    bom_ingredients: List[str]
    preference_weights: Dict[str, str]
    current_supplier: Optional[str] = None
    candidates: List[SourcedMaterial]
