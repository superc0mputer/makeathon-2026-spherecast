import requests
from typing import Dict, Any

REQUEST_TIMEOUT = 10

class FDCClient:
    """Client for USDA FoodData Central API"""
    def __init__(self, api_key: str = None):
        self.api_key = api_key or "FDC_KEY"
        self.base_url = "https://api.nal.usda.gov/fdc/v1"

    def search_food(self, query: str) -> Dict[str, Any]:
        url = f"{self.base_url}/foods/search"
        params = {
            "query": query,
            "pageSize": 1,
            "api_key": self.api_key,
            "dataType": "Foundation,SR Legacy,Branded"
        }
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
