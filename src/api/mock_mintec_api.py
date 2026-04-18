from fastapi import FastAPI, HTTPException
import json
import os
from typing import Dict, Any

app = FastAPI(
    title="Mintec Mock Pricing API",
    description="A small API to act as the Mintec pricing engine for our Hackathon backend."
)

def load_prices() -> Dict[str, Any]:
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(base_path, "src", "data", "mock_pricing_db.json")
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Load it once into memory when the server boots
PRICING_DB = load_prices()

@app.get("/api/v1/prices/{ingredient_name}")
def get_ingredient_price(ingredient_name: str):
    """
    Retrieve the price per kg of a given ingredient name.
    Does a fuzzy lower-case match across the generated JSON.
    """
    search_term = ingredient_name.lower().strip()
    
    # Exact match lower
    for key, data in PRICING_DB.items():
        if key.lower().strip() == search_term:
            return {"ingredient": key, "price_per_kg": data.get("price_per_kg")}
            
    # Fuzzy match logic if not found exactly (eg 'Calcium Citrate' into 'organic calcium citrate')
    for key, data in PRICING_DB.items():
        if search_term in key.lower() or key.lower() in search_term:
            return {"ingredient": key, "price_per_kg": data.get("price_per_kg"), "note": "Fuzzy Matched"}
            
    raise HTTPException(status_code=404, detail=f"Price not found for '{ingredient_name}'")

# You can run this locally using:
# uvicorn src.api.mock_mintec_api:app --reload --port 8000