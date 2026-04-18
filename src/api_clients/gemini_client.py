import json
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import Type

class GeminiClient:
    """Client for Google Gemini LLM API"""
    def __init__(self, api_key: str = None, model_name: str = "gemini-2.5-flash", project_id: str = None, location: str = "us-central1"):
        # Always use Vertex AI backend so calls can use Google Cloud billing.
        client_kwargs = {"vertexai": True, "location": location}
        if project_id:
            client_kwargs["project"] = project_id
        if api_key:
            client_kwargs["api_key"] = api_key

        if not project_id and not api_key:
            raise ValueError(
                "Missing authentication. Provide project_id (ADC flow) or api_key (Vertex API key flow)."
            )

        self.client = genai.Client(**client_kwargs)
        self.model_name = model_name

    def generate_json_structured_content(
        self, 
        prompt: str, 
        response_schema: Type[BaseModel], 
        system_instruction: str, 
        temperature: float = 0.2
    ) -> str:
        """Call the Gemini API demanding strict JSON parsing against a Pydantic schema."""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=response_schema,
                system_instruction=system_instruction
            )
        )
        
        raw_response = (response.text or "").strip()
        # Clean markdown wrappers if present
        if raw_response.startswith("```json"):
            raw_response = raw_response.replace("```json", "", 1)
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3]
                
        return raw_response.strip()
