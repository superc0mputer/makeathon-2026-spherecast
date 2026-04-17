import os
import sys
import json
import warnings

# Suppress all those noisy FutureWarning and UserWarning from Google SDKs
warnings.filterwarnings("ignore")

# Add project root to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.llm_client import IngredientLLMClient

def test_ingredients():
    """
    Test the Phase 2, Step 3 LLM Prompt substitution logic using 3 representative ingredients.
    This checks whether the LLM handles BOM context, chemical matching, and strict JSON rendering.
    """
    # Use simple API key instead of complex Vertex billing 
    api_key = os.environ.get("GEMINI_API_KEY", "your-api-key-here")
    
    print("\n--- Testing Ingredient Substitution LLM ---")
    
    # Mocks based on the product cluster and BOM requirements
    test_cases = [
        {
            "target": "Sugar",
            "cluster": "Baked Goods (Sponge Cake)",
            "bom": ["All-purpose flour", "Eggs", "Butter", "Vanilla extract", "Baking powder"],
            "pubchem_components": "Sucrose; C12H22O11; provides sweetness, caramelization, moisture retention, and structural bulking; melting point ~186°C.",
            "candidates": ["Allulose", "Erythritol", "Table Salt (Sodium Chloride)", "Sand"] 
        },
        {
            "target": "Palm Oil",
            "cluster": "Chocolate Confectionery",
            "bom": ["Cocoa Powder", "Milk Powder", "Lecithin", "Sugar"],
            "pubchem_components": "High saturated fat content (palmitic acid); semi-solid at room temperature; neutral flavor; provides mouthfeel and snap; melting point ~35°C.",
            "candidates": ["Shea Butter", "Motor Oil", "Sal Fat", "Water"]
        },
        {
            "target": "Guar Gum",
            "cluster": "Almond Milk Alternative",
            "bom": ["Filtered Water", "Almond Paste", "Sea Salt", "Calcium Carbonate"],
            "pubchem_components": "Galactomannan polysaccharide; high viscosity thickener and emulsifier; highly soluble in cold water; pH independent stabilization.",
            "candidates": ["Xanthan Gum", "Locust Bean Gum", "Baking Soda"]
        }
    ]

    try:
        client = IngredientLLMClient(api_key=api_key if api_key != "your-api-key-here" else None)
        
        for i, test in enumerate(test_cases, 1):
            print(f"\n[Test Case {i}] Finding substitutes for: {test['target']}")
            print(f"Context: Cluster='{test['cluster']}', BOM={test['bom']}")
            print(f"Provided Candidates: {test['candidates']}")
            
            result = client.get_substitutes(
                target=test["target"],
                cluster=test["cluster"],
                bom=test["bom"],
                pubchem_components=test["pubchem_components"],
                candidates=test["candidates"]
            )
            
            if "error" in result:
                print(f"❌ LLM Call Failed. Check your Vertex AI permissions or quota. Error: {result['error']}")
                continue
                
            # Verify required JSON scheme structure
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
        print("Please ensure you have `google-cloud-aiplatform` installed and `gcloud auth application-default login` executed.")

if __name__ == "__main__":
    test_ingredients()
