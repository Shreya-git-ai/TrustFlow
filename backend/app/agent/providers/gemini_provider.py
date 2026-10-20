import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


class GeminiProvider:
    """Real LLM provider. Returns raw JSON text; the verifier validates it."""

    def __init__(self, model: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (check your .env)")
        self.model = model or os.getenv("TRUSTFLOW_MODEL")
        if not self.model:
            raise RuntimeError("TRUSTFLOW_MODEL is not set (check your .env)")
        self.client = genai.Client(api_key=api_key)

    def complete(self, system: str, user: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0,
                response_mime_type="application/json",
            ),
        )
        return response.text or ""