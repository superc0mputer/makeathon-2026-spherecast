from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from src.models.substitution.nutritional_profile import NutritionalProfile

class FullIngredientProfile(BaseModel):
    """
    Represents the unified context for a single ingredient,
    combining its PubChem chemical footprint and its USDA FDC nutritional footprint.
    """
    chemical_properties: Dict[str, Any] = Field(default_factory=dict)
    nutritional_properties: Optional[NutritionalProfile] = None
