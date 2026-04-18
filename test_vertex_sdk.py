import os
from google import genai
client = genai.Client(vertexai=True, location="us-central1")
print("Unified GenAI SDK Vertex initialization successful!")
