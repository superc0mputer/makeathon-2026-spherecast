import os
import json
import sys
import warnings
from dotenv import load_dotenv

# Suppress sklearn mathematical calculation warnings for cleaner output
warnings.filterwarnings("ignore", category=RuntimeWarning, module="sklearn.utils.extmath")

# Load environment variables from .env file securely
load_dotenv()

# Ensure local src/ imports work when running from CLI
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.clustering_service import load_data, calculate_target_substitutes
from src.services.supplier_db_service import ingredient_name_from_sku
from src.services.pubchem_service import enrich_ingredient
from src.services.llm_service import IngredientLLMClient
from src.services.enrichment_service import SupplyChainEnricher

def main():
    print("=====================================================")
    print("🔄 SMART INGREDIENT SUBSTITUTION - E2E PIPELINE RUN")
    print("=====================================================")
    
    # Configuration & Inputs
    api_key = os.environ.get("GEMINI_API_KEY")
    
    # Properly construct path to db.sqlite in the project root
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_path, "db.sqlite")
    
    # Inputs mimicking frontend UI parameters
    target_sku = "RM-C14-b-vitamins-6b1105ff" 
    target_name = ingredient_name_from_sku(target_sku)
    company_coords = (48.1351, 11.5820) # Munich
    bom_ingredients = ["Magnesium Stearate", "Cellulose", "Guar Gum"]
    preference_weights = {"price": "High Priority", "distance": "Medium Priority"}

    # ---------------------------------------------------------
    # PHASE 1: Discovery & Chemical Profiling (Clustering)
    # ---------------------------------------------------------
    print(f"\n[Phase 1] Extracting Substitute Candidates for: {target_name} ({target_sku})")
    try:
        components = load_data(db_path)
        cluster_result = calculate_target_substitutes(components, target_sku)
        candidate_skus = [sub['sku'] for sub in cluster_result.get('substitutes', [])[:5]] # Take top 5
        candidate_names = [ingredient_name_from_sku(sku) for sku in candidate_skus]
        print(f"✅ Found {len(candidate_names)} high-confidence contextual candidates: {candidate_names}")
    except Exception as e:
        print(f"❌ Phase 1 Failed: {e}")
        return

    # ---------------------------------------------------------
    # PHASE 2: Feasibility & Initial Filtering
    # ---------------------------------------------------------
    print(f"\n[Phase 2A] Querying PubChem API for Chemical Properties of {target_name}...")
    pubchem_profile = enrich_ingredient(target_name)
    pubchem_info = json.dumps(pubchem_profile.to_llm_dict(), indent=2)
    print(f"✅ PubChem Profile retrieved with status: {pubchem_profile.status}")

    print("\n[Phase 2B] Running LLM Contextual Validation...")
    
    if api_key:
        llm_client = IngredientLLMClient(api_key=api_key)
        llm_shortlist = llm_client.get_substitutes(
            target=target_name,
            cluster="Vitamins & Minerals",
            bom=bom_ingredients,
            pubchem_components=pubchem_info,
            candidates=candidate_names
        )
    else:
        llm_shortlist = {"error": "GEMINI_API_KEY environment variable not set. Using mock LLM client."}
    
    if "error" in llm_shortlist:
        print(f"⚠️ LLM Call failed (Likely missing GEMINI_API_KEY): {llm_shortlist['error']}")
        print("⚠️ Injecting Mock LLM Shortlist to keep pipeline advancing...")
        llm_shortlist = {
            "substitutes": [
                {
                    "substitute_name": candidate_names[0] if candidate_names else "Cellulose",
                    "confidence_score": 85,
                    "reasoning": "Mocked LLM reasoning for continuity."
                },
                {
                    "substitute_name": candidate_names[1] if len(candidate_names) > 1 else "Unknown RM",
                    "confidence_score": 70,
                    "reasoning": "Mocked LLM reasoning 2."
                }
            ]
        }
    else:
        print("✅ LLM Shortlist successfully generated.")

    print("\n--- First LLM Response (Phase 2B Shortlist) ---")
    print(json.dumps(llm_shortlist, indent=2))
    print("------------------------------------------------\n")

    # ---------------------------------------------------------
    # PHASE 3: Logistics & Sourcing Enrichment
    # ---------------------------------------------------------
    print("\n[Phase 3] Matching SQLite Suppliers + Mintec API Prices + Nominatim Geocoding...")
    enricher = SupplyChainEnricher(db_path=db_path)
    enriched_data = enricher.enrich_substitutes(llm_shortlist, company_coords)
    print(f"✅ Extracted full Supply Chain matrix for {len(enriched_data.get('substitutes', []))} substitutes.")

    # ---------------------------------------------------------
    # PHASE 4: The Decision Engine
    # ---------------------------------------------------------
    print("\n[Phase 4] LLM Multi-Criteria Decision Engine (Evaluating Price/Distance/Chemicals)...")
    
    if api_key:
        final_recs = llm_client.get_top_3_recommendations(
            target_ingredient=target_name,
            bom_ingredients=bom_ingredients,
            company_coords=company_coords,
            preference_weights=preference_weights,
            enriched_data=enriched_data
        )
    else:
        final_recs = {"error": "GEMINI_API_KEY environment variable not set. Cannot run final LLM step."}
    
    if "error" in final_recs:
        print(f"⚠️ Final Engine LLM Call failed: {final_recs['error']}")
        print("Displaying raw Phase 3 JSON output instead:\n")
        print(json.dumps(enriched_data, indent=2))
    else:
        print("\n🏆 ================= FINAL TOP 3 RECOMMENDATIONS ================= 🏆")
        print(json.dumps(final_recs, indent=2))
        print("🏆 =============================================================== 🏆")

if __name__ == "__main__":
    main()