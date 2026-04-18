from pydantic import BaseModel, Field
from typing import Dict, Optional

class NutritionalProfileDetails(BaseModel):
    """Details specific to a resolved food item."""
    fdc_id: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None
    nutrients: Dict[str, str] = Field(default_factory=dict)

class NutritionalProfile(BaseModel):
    """
    Strictly typed representation of USDA FoodData Central nutritional information.
    """
    status: str
    message: Optional[str] = None
    profile: Optional[NutritionalProfileDetails] = None
