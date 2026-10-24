import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

RETRY_CODES = {429, 500, 502, 503, 504}


def _is_transient(e: Exception) -> bool:
    code = getattr(e, "code", None)
    if isinstance(code, int):
        return code in RETRY_CODES
    text = str(e)
    return any(s in text for s in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "timed out", "timeout"))


def _is_daily_quota(e: Exception) -> bool:
    text = str(e).lower()
    return "quota" in text and any(marker in text for marker in ("per day", "daily", "requests/day", "limit: 0"))


class GeminiProvider:
    """Gemini provider with one bounded fallback attempt for transient errors."""

    def __init__(self, model: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (check your .env)")
        self.model = model or os.getenv("TRUSTFLOW_MODEL")
        if not self.model:
            raise RuntimeError("TRUSTFLOW_MODEL is not set (check your .env)")
        self.fallback_model = os.getenv("TRUSTFLOW_FALLBACK_MODEL") or None
        self.client = genai.Client(api_key=api_key)
        self.name = f"gemini:{self.model}"

    def _call(self, model: str, system: str, user: str, timeout_s: float) -> str:
        response = self.client.models.generate_content(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),  # ms
            ),
        )
        return response.text or ""

    def complete_json(self, system: str, user: str, timeout_s: float = 30.0) -> str:
        try:
            return self._call(self.model, system, user, timeout_s)
        except Exception as e:
            if self.fallback_model and _is_transient(e) and not _is_daily_quota(e):
                self.name = f"gemini:{self.fallback_model}"
                return self._call(self.fallback_model, system, user, timeout_s)
            raise

    # keeps smoke_gemini.py working
    complete = complete_json
