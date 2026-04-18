import requests
import time
from typing import Any, cast

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
REQUEST_TIMEOUT = 10
USER_AGENT = "makeathon-2026-spherecast/0.1 (supplier geocoding prototype)"

class NominatimClient:
    """Client for OpenStreetMap Nominatim Geocoding API"""
    
    @staticmethod
    def search_supplier(supplier_name: str) -> list[dict[str, Any]]:
        response = requests.get(
            NOMINATIM_SEARCH_URL,
            params={
                "q": supplier_name,
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return cast(list[dict[str, Any]], response.json())
