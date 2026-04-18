import json
import sys
import os
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.mintec_service import SupplyChainEnricher

@patch('urllib.request.urlopen')
def test_supply_chain_enrichment(mock_urlopen):
    '''
    Tests the Phase 3 (Steps 5 & 6) enrichment pipeline using 
    a mocked HTTP API call.
    '''
    # Set up the mock response for the HTTP GET call
    mock_response = MagicMock()
    mock_response.status = 200
    def custom_read():
        # Check what the test requested, return none for 'Unknown Random Ingredient'
        req_url = mock_urlopen.call_args[0][0].full_url
        if "Unknown" in req_url:
            raise Exception("404 HTTP MOCK Error")
        
        return json.dumps({"ingredient": "Mock", "price_per_kg": 46.01}).encode('utf-8')

    mock_response.read.side_effect = custom_read
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    # 1. Load the mock LLM output that acts like Step 4 finished
    with open("tests/mock_llm_response.json", "r") as f:
        llm_response = json.load(f)
        
    # 2. Instantiate the enricher
    enricher = SupplyChainEnricher(db_path="db/db.sqlite")
    
    # 3. Enrich the data with Supplier and Price info
    enriched_data = enricher.enrich_substitutes(llm_response)
    
    # 4. Assertions on expected results
    subs = enriched_data["substitutes"]
    
    assert len(subs) == 3, "Should still have 3 substitutes after enrichment"
    
    pea_protein = subs[0]
    assert pea_protein["substitute_name"] == "Calcium Citrate"
    assert pea_protein["price_per_kg"] is not None # Price fetched from mock_database
    assert len(pea_protein["suppliers"]) >= 1      # Suppliers fetched securely from SQLite
    
    # Test Geolocation integration from Teammate's Step 7 code
    first_supplier = pea_protein["suppliers"][0]
    assert "distance_km" in first_supplier 
    assert "lat" in first_supplier
    assert "lng" in first_supplier

    soy_protein = subs[1]
    assert soy_protein["substitute_name"] == "Cellulose"
    assert soy_protein["price_per_kg"] is not None
    assert len(soy_protein["suppliers"]) >= 1
    
    unknown = subs[2]
    assert unknown["substitute_name"] == "Unknown Random Ingredient"
    assert unknown["price_per_kg"] is None
    assert len(unknown["suppliers"]) == 0

if __name__ == "__main__":
    test_supply_chain_enrichment()
    print("All supply chain enrichment tests passed!")
