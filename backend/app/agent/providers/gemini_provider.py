import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

RETRY_CODES = {429, 500, 502, 503, 504}
TRIES_PER_MODEL = 2


def _is_transient(e: Exception) -> bool:
    code = getattr(e, "code", None)
    if isinstance(code, int):
        return code in RETRY_CODES
    text = str(e)
    return any(s in text for s in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "timed out", "timeout"))


def _is_daily_quota(e: Exception) -> bool:
    # A daily quota does not come back with a retry, so do not wait on it.
    return "PerDay" in str(e)


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

    def _call_with_retries(self, model: str, system: str, user: str, timeout_s: float) -> str:
        last: Exception | None = None
        for attempt in range(1, TRIES_PER_MODEL + 1):
            try:
                return self._call(model, system, user, timeout_s)
            except Exception as e:
                if not _is_transient(e) or _is_daily_quota(e):
                    raise
                last = e
                if attempt < TRIES_PER_MODEL:
                    time.sleep(min(2 ** attempt, 20) + random.random())
        raise last  # type: ignore[misc]

    def complete_json(self, system: str, user: str, timeout_s: float = 30.0) -> str:
        try:
            return self._call(self.model, system, user, timeout_s)
        except Exception as e:
            if self.fallback_model and _is_transient(e):
                self.name = f"gemini:{self.fallback_model}"
                return self._call(self.fallback_model, system, user, timeout_s)
            raise

    # keeps smoke_gemini.py working
    complete = complete_json
