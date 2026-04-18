import json
import pytest
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.llm_service import IngredientLLMClient
from src.models.logistics_context import LogisticsContext, SourcedMaterial, SupplierDetails

@pytest.fixture
def mock_enriched_data():
    return {
        "substitutes": [
            {
                "substitute_name": "Calcium Citrate",
                "confidence_score": 94,
                "reasoning": "Excellent chemical replacement option.",
                "price_per_kg": 46.01,
                "suppliers": [
                    {
                        "supplier_id": 14,
                        "name": "Global Botanicals",
                        "distance_km": 154.2,
                        "lat": 48.1,
                        "lng": 11.2,
                        "address": "Munich Logistics Hub",
                        "match_confidence": "high"
                    }
                ]
            },
            {
                "substitute_name": "Magnesium Silicate",
                "confidence_score": 88,
                "reasoning": "Secondary structural option.",
                "price_per_kg": 22.02,
                "suppliers": [
                    {
                        "supplier_id": 5,
                        "name": "Acme Supplier",
                        "distance_km": 8700.5, # Very far away
                        "lat": 30.1,
                        "lng": -90.2,
                        "address": "Overseas",
                        "match_confidence": "high"
                    }
                ]
            }
        ]
    }

@patch('google.genai.Client')
def test_recommendation_engine(mock_client_class, mock_enriched_data):
    """
    Tests Phase 4 (Step 8): The Decision Engine 
    Evaluates whether the prompt and strict Pydantic parsing resolves cleanly
    """
    # 1. Setup Mock Gemini Response wrapping our specific Pydantic schema
    mock_llm_output = {
        "top_3_recommendations": [
            {
                "rank": 1,
                "substitute_name": "Calcium Citrate",
                "confidence_score": 94,
                "recommended_supplier": {
                    "supplier_id": 14,
                    "name": "Global Botanicals",
                    "price_per_kg": 46.01,
                    "distance_km": 154.2
                },
                "reasoning_summary": "Selected due to high chemical confidence and very low distance (154km), offsetting the higher price of $46.01."
            }
        ]
    }
    
    mock_instance = mock_client_class.return_value
    mock_generate = MagicMock()
    mock_generate.text = json.dumps(mock_llm_output)
    mock_instance.models.generate_content.return_value = mock_generate

    # 2. Setup the Client
    client = IngredientLLMClient(api_key="TEST_KEY")
    
    # 3. Simulate UI Preferences input hitting Step 8
    target = "Vitamin D"
    bom = ["Cellulose", "Guar Gum"]
    coords = (48.1351, 11.5820)
    preferences = {
        "distance": "Highest Priority, source locally",
        "price": "Medium Priority"
    }
    
    sourced_materials = []
    for sub in mock_enriched_data["substitutes"]:
        sups = [SupplierDetails(**s) for s in sub["suppliers"]]
        sm = SourcedMaterial(
            substitute_name=sub["substitute_name"],
            confidence_score=sub["confidence_score"],
            reasoning=sub["reasoning"],
            price_per_kg=sub["price_per_kg"],
            suppliers=sups
        )
        sourced_materials.append(sm)

    context = LogisticsContext(
        target_ingredient=target,
        bom_ingredients=bom,
        company_coords=list(coords),
        preference_weights=preferences,
        candidates=sourced_materials
    )

    response = client.get_top_3_recommendations(context=context)
    
    # 4. Assert Pydantic Structure returned perfectly
    assert "top_3_recommendations" in response
    recs = response["top_3_recommendations"]
    assert len(recs) == 1
    
    top = recs[0]
    assert top["rank"] == 1
    assert top["substitute_name"] == "Calcium Citrate"
    
    # Assert Nested supplier properties exist
    sup = top["recommended_supplier"]
    assert sup["supplier_id"] == 14
    assert sup["name"] == "Global Botanicals"
    assert "distance" in top["reasoning_summary"]