from pydantic import BaseModel, Field
from typing import Dict
from src.models.substitution.full_ingredient_profile import FullIngredientProfile

class BiochemicalContext(BaseModel):
    """
    The strictly typed data model injected into the Phase 2 LLM Prompt to determine
    viable ingredient substitutions based on the whole formula context.
    """
    target_ingredient: str
    product_cluster: str
    optimization_priority: str
    target_profile: FullIngredientProfile
    bom_profiles: Dict[str, FullIngredientProfile] = Field(default_factory=dict)
    candidate_profiles: Dict[str, FullIngredientProfile] = Field(default_factory=dict)
