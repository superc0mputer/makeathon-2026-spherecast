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
from src.services.mintec_service import SupplyChainEnricher
from src.services.fdc_service import fetch_fdc_profiles
from src.models.substitution.nutritional_profile import NutritionalProfile
from src.models.logistics_context import LogisticsContext, SourcedMaterial, SupplierDetails
from src.models.biochemical_context import BiochemicalContext
from src.models.substitution.full_ingredient_profile import FullIngredientProfile

def main():
    print("=====================================================")
    print("🔄 SMART INGREDIENT SUBSTITUTION - E2E PIPELINE RUN")
    print("=====================================================")
    
    # Configuration & Inputs
    api_key = os.environ.get("GEMINI_API_KEY")
    vertex_project = os.environ.get("VERTEX_PROJECT_ID")
    vertex_location = os.environ.get("VERTEX_LOCATION", "us-central1")
    fdc_api_key = os.environ.get("FDC_API_KEY")
    
    # Properly construct path to db.sqlite in the project root
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_path, "db/db.sqlite")
    
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
    # PHASE 2: Feasibility & Initial Filtering (Whole Formula Context)
    # ---------------------------------------------------------
    print(f"\n[Phase 2A] Resolving Chemical & Nutritional Profiles for Whole Formula...")
    
    def get_full_profile(name) -> FullIngredientProfile:
        pubchem = enrich_ingredient(name)
        fdc_data = fetch_fdc_profiles(target=name, candidates=[], api_key=fdc_api_key)
        nutritional_data = fdc_data.get("target", {}).get(name, {})
        
        return FullIngredientProfile(
            chemical_properties=pubchem.to_llm_dict(),
            nutritional_properties=NutritionalProfile(**nutritional_data) if nutritional_data else None
        )

    print(f"   ... Fetching target profile for {target_name}")
    target_profile = get_full_profile(target_name)

    bom_profiles_dict = {}
    for ing in bom_ingredients:
        print(f"   ... Fetching BOM profile for {ing}")
        bom_profiles_dict[ing] = get_full_profile(ing)

    candidate_profiles_dict = {}
    for cand in candidate_names:
        print(f"   ... Fetching Candidate profile for {cand}")
        candidate_profiles_dict[cand] = get_full_profile(cand)

    print("✅ Full Context Profiles Retrieved.")

    # Instantiate the formal Pydantic payload
    biochemical_context = BiochemicalContext(
        target_ingredient=target_name,
        product_cluster="Vitamins & Minerals",
        target_profile=target_profile,
        bom_profiles=bom_profiles_dict,
        candidate_profiles=candidate_profiles_dict
    )

    print("\n[Phase 2B] Running LLM Contextual Validation with Cross-Reactions...")
    
    if api_key or vertex_project:
        llm_client = IngredientLLMClient(api_key=api_key, project_id=vertex_project, location=vertex_location)
        llm_shortlist = llm_client.get_substitutes(biochemical_context)
    else:
        llm_shortlist = {"error": "GEMINI_API_KEY or VERTEX_PROJECT_ID environment variable not set. Using mock LLM client."}
    
    if "error" in llm_shortlist:
        print(f"⚠️ LLM Call failed (Check GEMINI_API_KEY / Vertex Quotas): {llm_shortlist['error']}")
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
    print("\n[Phase 4] LLM Multi-Criteria Decision Engine (Evaluating Price/Distance)...")
    
    # Strictly Type the contextual mapping
    try:
        sourced_materials = []
        for sub in enriched_data.get('substitutes', []):
            supplier_details = []
            for sup in sub.get('suppliers', []):
                supplier_details.append(SupplierDetails(
                    supplier_id=sup.get('supplier_id', 0),
                    name=sup.get('name', 'Unknown'),
                    match_confidence=sup.get('match_confidence'),
                    lat=sup.get('lat'),
                    lng=sup.get('lng'),
                    distance_km=sup.get('distance_km'),
                    stocked_ingredients=sup.get('stocked_ingredients', []),
                ))
                
            en_sub = SourcedMaterial(
                substitute_name=sub.get('substitute_name', 'Unknown'),
                confidence_score=sub.get('confidence_score', 0),
                reasoning=sub.get('reasoning', ''),
                price_per_kg=sub.get('price_per_kg'),
                suppliers=supplier_details
            )
            sourced_materials.append(en_sub)

        logistics_context = LogisticsContext(
            target_ingredient=target_name,
            company_coords=list(company_coords),
            bom_ingredients=bom_ingredients,
            preference_weights=preference_weights,
            candidates=sourced_materials
        )
    except Exception as e:
        print(f"❌ Failed to construct strictly typed Phase 4 Payload: {e}")
        return
        
    if api_key or vertex_project:
        final_recs = llm_client.get_top_3_recommendations(context=logistics_context)
    else:
        final_recs = {"error": "GEMINI_API_KEY or VERTEX_PROJECT_ID environment variable not set. Cannot run final LLM step."}
    
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