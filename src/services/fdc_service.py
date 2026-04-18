import requests
from typing import Dict, Any, List
from src.services.cache_service import get_fdc, set_fdc

class FDCService:
    def __init__(self, api_key: str = None):
        # Fallback to DEMO_KEY if no key is provided, which works but has strict rate limits
        self.api_key = api_key or "DEMO_KEY"
        self.base_url = "https://api.nal.usda.gov/fdc/v1"

    def get_nutritional_profile(self, ingredient_name: str, max_age_days: int = None) -> Dict[str, Any]:
        """
        Search FoodData Central for an ingredient and return a simplified nutritional profile.
        Checks local SQLite cache first.
        """
        cached_data = get_fdc(ingredient_name, max_age_days=max_age_days)
        if cached_data:
            return cached_data

        url = f"{self.base_url}/foods/search"
        params = {
            "query": ingredient_name,
            "pageSize": 1,
            "api_key": self.api_key,
            "dataType": "Foundation,SR Legacy,Branded" # Focus on primary data types
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("foods"):
                result = {"status": "not_found", "message": f"No FDC data found for {ingredient_name}"}
                set_fdc(ingredient_name, result)
                return result
            
            food_item = data["foods"][0]
            nutrients = food_item.get("foodNutrients", [])
            
            # Extract key nutrients to keep LLM context concise
            profile = {
                "fdc_id": food_item.get("fdcId"),
                "description": food_item.get("description", ""),
                "category": food_item.get("foodCategory", "Unknown"),
                "nutrients": {}
            }
            
            # Important macros, vitamins, and minerals
            for n in nutrients:
                name = n.get("nutrientName", "")
                amount = n.get("value")
                unit = n.get("unitName", "")
                
                # Filter out zeroes to save tokens, format nicely
                if amount and amount > 0:
                    profile["nutrients"][name] = f"{amount} {unit}"
                    
            result = {"status": "resolved", "profile": profile}
            set_fdc(ingredient_name, result)
            return result
            
        except Exception as e:
            result = {"status": "error", "message": str(e)}
            # If it's a 400 client error (like 404), cache it so we don't spam the API
            if isinstance(e, requests.exceptions.HTTPError) and 400 <= e.response.status_code < 500:
                result["status"] = "not_found"
                set_fdc(ingredient_name, result)
            return result

def fetch_fdc_profiles(target: str, candidates: List[str], api_key: str = None) -> Dict[str, Any]:
    """Helper to fetch target and candidate profiles in one go for the LLM."""
    service = FDCService(api_key)
    
    profiles = {
        "target": {target: service.get_nutritional_profile(target)},
        "candidates": {}
    }
    
    for cand in candidates:
        profiles["candidates"][cand] = service.get_nutritional_profile(cand)
        
    return profiles
