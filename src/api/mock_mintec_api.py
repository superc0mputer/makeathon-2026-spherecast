from fastapi import FastAPI, HTTPException
import json
import os
import sys

# Ensure imports work from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.services.cache_service import get_mintec

app = FastAPI(
    title="Mintec Mock Pricing API",
    description="A small API to act as the Mintec pricing engine for our Hackathon backend."
)

@app.get("/api/v1/prices/{ingredient_name}")
def get_ingredient_price(ingredient_name: str):
    """
    Retrieve the price per kg of a given ingredient name.
    Queries the central cache.sqlite which models the global Mintec database.
    """
    price_info = get_mintec(ingredient_name)
    if price_info:
        return price_info
            
    raise HTTPException(status_code=404, detail=f"Price not found for '{ingredient_name}'")

# You can run this locally using:
# uvicorn src.api.mock_mintec_api:app --reload --port 8000
