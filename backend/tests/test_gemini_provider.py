import unittest
from unittest.mock import patch

from app.agent.providers.gemini_provider import GeminiProvider


class _ProviderUnavailable(Exception):
    code = 503


class GeminiProviderTests(unittest.TestCase):
    def make_provider(self):
        provider = GeminiProvider.__new__(GeminiProvider)
        provider.model = "primary-model"
        provider.fallback_model = "fallback-model"
        provider.name = "gemini:primary-model"
        return provider

    def test_transient_error_uses_fallback_and_updates_trace_model(self):
        provider = self.make_provider()
        with patch.object(
            provider,
            "_call",
            side_effect=[_ProviderUnavailable("busy"), '{"ok":true}'],
        ) as call:
            result = provider.complete_json("system", "user", timeout_s=7.0)

        self.assertEqual(result, '{"ok":true}')
        self.assertEqual(provider.name, "gemini:fallback-model")
        self.assertEqual(call.call_args_list[0].args, ("primary-model", "system", "user", 7.0))
        self.assertEqual(call.call_args_list[1].args, ("fallback-model", "system", "user", 7.0))

    def test_non_transient_error_does_not_use_fallback(self):
        provider = self.make_provider()
        with patch.object(provider, "_call", side_effect=ValueError("bad request")) as call:
            with self.assertRaisesRegex(ValueError, "bad request"):
                provider.complete_json("system", "user")

        call.assert_called_once_with("primary-model", "system", "user", 30.0)
        self.assertEqual(provider.name, "gemini:primary-model")

    def test_quota_error_does_not_use_fallback(self):
        provider = self.make_provider()
        quota_error = RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
        with patch.object(provider, "_call", side_effect=quota_error) as call:
            with self.assertRaisesRegex(RuntimeError, "RESOURCE_EXHAUSTED"):
                provider.complete_json("system", "user")

        call.assert_called_once_with("primary-model", "system", "user", 30.0)
        self.assertEqual(provider.name, "gemini:primary-model")


if __name__ == "__main__":
    unittest.main()
