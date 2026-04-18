import os
from typing import Dict, Any, List
import json
from pydantic import BaseModel
from google import genai
from google.genai import types

from src.models.recommendation_record import FinalDecisionResponse

class SubstituteItem(BaseModel):
    substitute_name: str
    confidence_score: int
    reasoning: str

class SubstituteResponse(BaseModel):
    substitutes: list[SubstituteItem]

class IngredientLLMClient:
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.5-flash"):
        """
        Initializes the client using Google AI Studio API Key.
        """
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def load_prompt_template(self, prompt_path: str = "prompts/substitution_v1.prompt.txt") -> str:
        """Loads the version-controlled prompt template from disk."""
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        full_path = os.path.join(base_path, prompt_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_substitutes(
        self, 
        target: str, 
        cluster: str, 
        bom: List[str], 
        pubchem_components: str, 
        fdc_nutritional_profile: str, 
        candidates: List[str]
    ) -> Dict[str, Any]:
        """
        Injects real values into the prompt template and calls Gemini,
        asserting the output is strict JSON. Filters from the provided candidates list.
        """
        template = self.load_prompt_template()
        
        # Inject context variables
        prompt = template.replace("{{target_ingredient}}", target)
        prompt = prompt.replace("{{product_cluster}}", cluster)
        prompt = prompt.replace("{{bom_ingredients}}", ", ".join(bom))
        prompt = prompt.replace("{{pubchem_components}}", pubchem_components)
        prompt = prompt.replace("{{fdc_nutritional_profile}}", fdc_nutritional_profile)
        prompt = prompt.replace("{{candidate_substitutes}}", ", ".join(candidates))

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=SubstituteResponse,
                    system_instruction="You are a Professional Food Science and Chemical Engineering Analyst."
                )
            )
            raw_response = response.text.strip()
            if raw_response.startswith("```json"):
                raw_response = raw_response.replace("```json", "", 1)
                if raw_response.endswith("```"):
                    raw_response = raw_response[:-3]
            
            return json.loads(raw_response.strip())
        except Exception as e:
            print(f"Error calling Gemini via genai: {e}")
            return {"error": str(e)}

    def get_top_3_recommendations(
        self,
        target_ingredient: str,
        bom_ingredients: List[str],
        company_coords: tuple[float, float],
        preference_weights: Dict[str, str],
        enriched_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes Step 8 (Phase 4): The Decision Engine.
        Uses the Gemini model to evaluate fully enriched JSON metrics (dist, price, confidence) 
        and strict returns the final Top 3 combinations.
        """
        template = self.load_prompt_template("prompts/recommendation_v1.prompt.txt")
        
        prompt = template.replace("{{target_ingredient}}", target_ingredient)
        prompt = prompt.replace("{{bom_ingredients}}", ", ".join(bom_ingredients))
        prompt = prompt.replace("{{company_coords}}", f"{company_coords[0]}, {company_coords[1]}")
        prompt = prompt.replace("{{preference_weights}}", json.dumps(preference_weights))
        prompt = prompt.replace("{{enriched_data}}", json.dumps(enriched_data, indent=2))
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2, # Low temperature since evaluation needs rigor
                    response_mime_type="application/json",
                    response_schema=FinalDecisionResponse,
                    system_instruction="You are a strict Data Scientist ranking supply chain constraints."
                )
            )
            raw_response = response.text.strip()
            if raw_response.startswith("```json"):
                raw_response = raw_response.replace("```json", "", 1)
                if raw_response.endswith("```"):
                    raw_response = raw_response[:-3]
            
            return json.loads(raw_response.strip())
        except Exception as e:
            print(f"Error executing Recommendation LLM call: {e}")
            return {"error": str(e)}

