from pydantic import BaseModel, Field

class RecommendedSupplier(BaseModel):
    supplier_id: int
    name: str
    price_per_kg: float = Field(description="The price per kg offered by this supplier")
    distance_km: float = Field(description="The requested transit distance to the company headquarters in km")

class Recommendation(BaseModel):
    rank: int = Field(description="1, 2, or 3 representing the final decision ranking")
    substitute_name: str
    confidence_score: int = Field(description="The original LLM substitutability confidence score")
    recommended_supplier: RecommendedSupplier
    reasoning_summary: str = Field(description="A brief LLM-generated summary of why it was chosen, highlighting price, distance, and confidence score")

class FinalDecisionResponse(BaseModel):
    top_3_recommendations: list[Recommendation]