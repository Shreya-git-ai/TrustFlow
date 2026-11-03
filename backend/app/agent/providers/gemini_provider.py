import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

RETRY_CODES = {500, 502, 503, 504}
DEFAULT_RETRY_DELAYS = (1.0, 3.0)  # 2 retries: wait ~1s, then ~3s


def _is_transient(e: Exception) -> bool:
    code = getattr(e, "code", None)
    if isinstance(code, int):
        return code in RETRY_CODES
    text = str(e)
    return any(s in text for s in ("500", "502", "503", "504", "UNAVAILABLE", "timed out", "timeout"))


def _is_daily_quota(e: Exception) -> bool:
    text = str(e).lower()
    return (
        "429" in text
        or "resource_exhausted" in text
        or "quota" in text
        or getattr(e, "code", None) == 429
    )


def _default_retry_delays() -> tuple[float, ...]:
    # Eval runs that must send exactly one request per case set this to 1.
    if os.getenv("TRUSTFLOW_DISABLE_RETRY") == "1":
        return ()
    return DEFAULT_RETRY_DELAYS


class GeminiProvider:
    """Gemini provider: bounded retry with backoff on transient 5xx, then one fallback model."""

    # Class-level default: instances created without __init__ (e.g. in tests) do not retry.
    retry_delays: tuple[float, ...] = ()

    def __init__(self, model: str | None = None, retry_delays: tuple[float, ...] | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (check your .env)")
        self.model = model or os.getenv("TRUSTFLOW_MODEL")
        if not self.model:
            raise RuntimeError("TRUSTFLOW_MODEL is not set (check your .env)")
        self.fallback_model = os.getenv("TRUSTFLOW_FALLBACK_MODEL") or None
        self.retry_delays = _default_retry_delays() if retry_delays is None else retry_delays
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

    def _call_with_retry(self, model: str, system: str, user: str, timeout_s: float) -> str:
        """Retry only transient 5xx/timeouts. Quota (429) and 4xx fail immediately."""
        for attempt in range(len(self.retry_delays) + 1):
            try:
                return self._call(model, system, user, timeout_s)
            except Exception as e:
                if (
                    attempt >= len(self.retry_delays)
                    or not _is_transient(e)
                    or _is_daily_quota(e)
                ):
                    raise
                time.sleep(self.retry_delays[attempt])
        raise RuntimeError("unreachable")  # loop always returns or raises

    def complete_json(self, system: str, user: str, timeout_s: float = 30.0) -> str:
        try:
            return self._call_with_retry(self.model, system, user, timeout_s)
        except Exception as e:
            if self.fallback_model and _is_transient(e) and not _is_daily_quota(e):
                self.name = f"gemini:{self.fallback_model}"
                return self._call(self.fallback_model, system, user, timeout_s)
            raise