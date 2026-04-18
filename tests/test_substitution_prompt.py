import os
import sys
import json
import warnings

# Suppress all those noisy FutureWarning and UserWarning from Google SDKs
warnings.filterwarnings("ignore")

# Add project root to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.llm_service import IngredientLLMClient
from src.models.biochemical_context import BiochemicalContext
from src.models.substitution.full_ingredient_profile import FullIngredientProfile

def test_ingredients():
    """
    Test the Phase 2, Step 3 LLM Prompt substitution logic using 3 representative ingredients.
    This checks whether the LLM handles BOM context, chemical matching, and strict JSON rendering.
    """
    vertex_project = os.environ.get("VERTEX_PROJECT_ID")
    vertex_location = os.environ.get("VERTEX_LOCATION", "us-central1")
    
    print("\n--- Testing Ingredient Substitution LLM ---")
    
    if not vertex_project:
        print("\n[ERROR] Missing VERTEX_PROJECT_ID. Example:")
        print("export VERTEX_PROJECT_ID=agnes-ui")
        return

    # Keep this to one case so test stays cheap.
    test_case = {
        "target": "Sodium Benzoate",
        "cluster": "Beverage Concentrate",
        "bom": ["Citric Acid", "Water", "Flavor Base"],
        "candidates": ["Potassium Sorbate", "Calcium Propionate", "Sodium Acetate"],
    }

    def mk_profile(name: str, formula: str, role: str) -> FullIngredientProfile:
        return FullIngredientProfile(
            chemical_properties={
                "name": name,
                "molecular_formula": formula,
                "functional_role": role,
            }
        )

    try:
        client = IngredientLLMClient(
            project_id=vertex_project,
            location=vertex_location,
        )

        context = BiochemicalContext(
            target_ingredient=test_case["target"],
            product_cluster=test_case["cluster"],
            target_profile=mk_profile(
                "Sodium Benzoate",
                "C7H5NaO2",
                "Preservative",
            ),
            bom_profiles={
                "Citric Acid": mk_profile("Citric Acid", "C6H8O7", "Acidulant"),
                "Water": mk_profile("Water", "H2O", "Solvent"),
                "Flavor Base": mk_profile("Flavor Base", "Mixture", "Flavor"),
            },
            candidate_profiles={
                "Potassium Sorbate": mk_profile("Potassium Sorbate", "C6H7KO2", "Preservative"),
                "Calcium Propionate": mk_profile("Calcium Propionate", "C6H10CaO4", "Preservative"),
                "Sodium Acetate": mk_profile("Sodium Acetate", "C2H3NaO2", "Buffer"),
            },
        )

        print(f"\n[Test Case] Finding substitutes for: {test_case['target']}")
        print(f"Context: Cluster='{test_case['cluster']}', BOM={test_case['bom']}")
        print(f"Provided Candidates: {test_case['candidates']}")

        result = client.get_substitutes(context=context)

        if "error" in result:
            print(f"❌ LLM Call Failed. Check Vertex setup/quota. Error: {result['error']}")
            return

        if "substitutes" in result and isinstance(result["substitutes"], list):
            print("✅ Successfully generated JSON structure!")
            for sub in result["substitutes"]:
                name = sub.get("substitute_name", "Unknown")
                confidence = sub.get("confidence_score", "N/A")
                reasoning = sub.get("reasoning", "No reasoning provided")
                print(f"  -> {name} [Confidence: {confidence}%]")
                print(f"     Reasoning: {reasoning}")
        else:
            print("❌ Invalid output structure from LLM.")
            print(json.dumps(result, indent=2))
                
    except Exception as e:
        print(f"\n[ERROR] Initializing client failed: {e}")
        print("Please ensure `VERTEX_PROJECT_ID` is set and `gcloud auth application-default login` is completed.")

if __name__ == "__main__":
    test_ingredients()
