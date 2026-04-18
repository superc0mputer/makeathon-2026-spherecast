import json
import urllib.request
import urllib.parse
from typing import Optional

class MintecClient:
    """Client for Mocked Mintec Pricing API"""
    def __init__(self, mintec_api_url: str = "http://127.0.0.1:8000/api/v1/prices"):
        self.mintec_api_url = mintec_api_url

    def fetch_price(self, ingredient_name: str) -> Optional[float]:
        try:
            safe_name = urllib.parse.quote(ingredient_name)
            url = f"{self.mintec_api_url}/{safe_name}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    return data.get("price_per_kg")
        except Exception as e:
            print(f"Failed to fetch {ingredient_name} pricing from Mock API: {e}")
        return None
