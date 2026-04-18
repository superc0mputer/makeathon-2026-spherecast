import os
from typing import Dict, Any, List
import json
from pydantic import BaseModel

from src.models.recommendation_record import FinalDecisionResponse
from src.models.biochemical_context import BiochemicalContext
from src.models.logistics_context import LogisticsContext
from src.api_clients.gemini_client import GeminiClient

class SubstituteItem(BaseModel):
    substitute_name: str
    confidence_score: int
    reasoning: str

class SubstituteResponse(BaseModel):
    substitutes: list[SubstituteItem]

class IngredientLLMClient:
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.5-flash", project_id: str = None, location: str = "us-central1"):
        """
        Initializes the LLM orchestrated client.
        """
        self.client = GeminiClient(api_key=api_key, model_name=model_name, project_id=project_id, location=location)

    def load_prompt_template(self, prompt_path: str = "prompts/substitution_v1.prompt.txt") -> str:
        """Loads the version-controlled prompt template from disk."""
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        full_path = os.path.join(base_path, prompt_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_substitutes(self, context: BiochemicalContext) -> Dict[str, Any]:
        """
        Injects real values into the prompt template and calls Gemini,
        asserting the output is strict JSON. Evaluates against Chemical Profiles and overall BOM interactions.
        """
        template = self.load_prompt_template()
        
        # Inject context variables
        prompt = template.replace("{{target_ingredient}}", context.target_ingredient)
        prompt = prompt.replace("{{product_cluster}}", context.product_cluster)
        prompt = prompt.replace("{{optimization_priority}}", context.optimization_priority)
        prompt = prompt.replace("{{target_profile}}", context.target_profile.model_dump_json(indent=2))
        
        # model_dump_json doesn't exist on Dict, so we dump mapping
        bom_profiles_json = json.dumps({k: v.model_dump() for k, v in context.bom_profiles.items()}, indent=2)
        candidate_profiles_json = json.dumps({k: v.model_dump() for k, v in context.candidate_profiles.items()}, indent=2)

        prompt = prompt.replace("{{candidate_profiles}}", candidate_profiles_json)
        prompt = prompt.replace("{{bom_profiles}}", bom_profiles_json)

        try:
            raw_response = self.client.generate_json_structured_content(
                prompt=prompt,
                response_schema=SubstituteResponse,
                system_instruction="You are a Professional Food Science and Chemical Engineering Analyst.",
                temperature=0.2
            )
            return json.loads(raw_response)
        except Exception as e:
            print(f"Error calling Gemini via genai: {e}")
            return {"error": str(e)}

    def get_top_3_recommendations(
        self,
        context: LogisticsContext
    ) -> Dict[str, Any]:
        """
        Executes Step 8 (Phase 4): The Decision Engine.
        Uses the Gemini model to evaluate fully enriched JSON metrics (dist, price, confidence) 
        and strictly returns the final Top 3 combinations based purely on Logistics and Supply Chain Optimization.
        """
        template = self.load_prompt_template("prompts/recommendation_v1.prompt.txt")
        
        prompt = template.replace("{{target_ingredient}}", context.target_ingredient)
        prompt = prompt.replace("{{company_coords}}", f"{context.company_coords[0]}, {context.company_coords[1]}")
        prompt = prompt.replace("{{bom_ingredients}}", json.dumps(context.bom_ingredients))
        prompt = prompt.replace("{{preference_weights}}", json.dumps(context.preference_weights))
        
        # Serialize the validated Pydantic substitutes directly into the prompt
        sub_dump = [sub.model_dump() for sub in context.candidates]
        prompt = prompt.replace("{{substitutes}}", json.dumps(sub_dump, indent=2))
        
        try:
            raw_response = self.client.generate_json_structured_content(
                prompt=prompt,
                response_schema=FinalDecisionResponse,
                system_instruction="You are a strict Data Scientist ranking supply chain constraints. Never evaluate chemistry.",
                temperature=0.2
            )
            return json.loads(raw_response)
        except Exception as e:
            print(f"Error executing Recommendation LLM call: {e}")
            return {"error": str(e)}
