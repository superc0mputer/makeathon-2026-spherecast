import json
import os
import sqlite3
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
from models.supplier import SupplierRecord
from services.geolocation import NominatimGeocoder, enrich_suppliers_with_geodata

class SupplyChainEnricher:
    def __init__(self, db_path: str = "db.sqlite", mintec_api_url: str = "http://127.0.0.1:8000/api/v1/prices"):
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(base_path, db_path)
        self.mintec_api_url = mintec_api_url
        self.geocoder = NominatimGeocoder()

    def _get_suppliers_for_ingredient(self, ingredient_name: str) -> List[Dict[str, Any]]:
        """
        Queries the actual db.sqlite database to find suppliers for the ingredient.
        It searches the Product SKU for a match, then joins with Supplier_Product and Supplier.
        """
        # Format for LIKE query (e.g. 'calcium citrate' -> '%calcium%citrate%')
        search_term = "%" + "%".join(ingredient_name.lower().split()) + "%"
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Find products matching the name, and their corresponding suppliers
            query = """
                SELECT DISTINCT s.Id as id, s.Name as supplier_name
                FROM Product p
                JOIN Supplier_Product sp ON p.Id = sp.ProductId
                JOIN Supplier s ON sp.SupplierId = s.Id
                WHERE p.Type = 'raw-material'
                  AND LOWER(p.SKU) LIKE ?
            """
            cursor.execute(query, (search_term,))
            rows = cursor.fetchall()
            conn.close()
            
            return [{"supplier_id": row["id"], "name": row["supplier_name"]} for row in rows]
        except Exception as e:
            print(f"Error querying db.sqlite: {e}")
            return []

    def _fetch_price_from_mintec(self, ingredient_name: str):
        """
        Uses Python's built-in urllib to query our actual running FastAPI Mintec Mock 
        API. Fails over silently so the pipeline doesn't break if the API isn't booted.
        """
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

    def enrich_substitutes(self, llm_response: Dict[str, Any], company_coords: tuple[float, float] = (48.1351, 11.5820)) -> Dict[str, Any]:
        """
        Takes the LLM JSON response and enriches each substitute with
        real Suppliers from db.sqlite, HTTP requested mocked pricing, 
        and geolocated routing distances via Nominatim.
        """
        enriched_results = []
        
        substitutes = llm_response.get("substitutes", [])
        
        for substitute in substitutes:
            name = substitute.get("substitute_name")
            
            # 1. Get real suppliers from db.sqlite
            real_suppliers_raw = self._get_suppliers_for_ingredient(name)
            real_suppliers = []
            
            if real_suppliers_raw:
                supplier_records = []
                for s in real_suppliers_raw:
                    supplier_records.append(
                        SupplierRecord(
                            supplier_id=s["supplier_id"],
                            name=s["name"],
                            stocked_ingredients=[name]
                        )
                    )
                
                # Use teammate's function to enrich with geolocation routing API!
                supplier_records = enrich_suppliers_with_geodata(
                    suppliers=supplier_records,
                    company_location=company_coords,
                    geocoder=self.geocoder
                )
                
                # Convert back to dict for generic JSON pipeline
                real_suppliers = [r.to_dict() for r in supplier_records]
            
            # 2. Add pricing via the Mintec Mock REST API
            price = self._fetch_price_from_mintec(name)
            
            enriched_substitute = {
                **substitute,
                "price_per_kg": price,
                "suppliers": real_suppliers
            }
            enriched_results.append(enriched_substitute)
            
        return {"substitutes": enriched_results}
