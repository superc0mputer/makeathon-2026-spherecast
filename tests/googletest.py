import sys
from google import genai


client = genai.Client(
    vertexai=True,
    project="agnes-ui",
    location="us-central1",
)

resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Reply with exactly: OK",
)

# Some SDK responses can have empty resp.text; check candidate parts too.
text = (resp.text or "").strip()
if not text and getattr(resp, "candidates", None):
    parts = getattr(resp.candidates[0].content, "parts", []) or []
    text = " ".join(
        part.text.strip() for part in parts if hasattr(part, "text") and part.text
    ).strip()

ok = text.upper().startswith("OK")

if ok:
    print("OK")
    sys.exit(0)

print("FAILED")
print("text:", repr(resp.text))
print("extracted_text:", repr(text))
print("candidates:", repr(getattr(resp, "candidates", None)))
print("prompt_feedback:", repr(getattr(resp, "prompt_feedback", None)))
sys.exit(1)
