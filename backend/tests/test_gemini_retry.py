import pytest

import app.agent.providers.gemini_provider as gp


class FakeAPIError(Exception):
    def __init__(self, code: int, msg: str = "err"):
        super().__init__(f"{code} {msg}")
        self.code = code


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("TRUSTFLOW_MODEL", "m1")
    monkeypatch.delenv("TRUSTFLOW_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("TRUSTFLOW_DISABLE_RETRY", raising=False)
    sleeps: list[float] = []
    monkeypatch.setattr(gp.time, "sleep", lambda s: sleeps.append(s))
    p = gp.GeminiProvider()
    p.sleeps = sleeps
    return p


def _script(p, outcomes):
    calls = []

    def fake_call(model, system, user, timeout_s):
        calls.append(model)
        o = outcomes[len(calls) - 1]
        if isinstance(o, Exception):
            raise o
        return o

    p._call = fake_call
    return calls


def test_retries_503_then_succeeds(provider):
    calls = _script(provider, [FakeAPIError(503), FakeAPIError(503), "{}"])
    assert provider.complete_json("s", "u") == "{}"
    assert len(calls) == 3
    assert provider.sleeps == [1.0, 3.0]


def test_400_not_retried(provider):
    calls = _script(provider, [FakeAPIError(400)])
    with pytest.raises(FakeAPIError):
        provider.complete_json("s", "u")
    assert len(calls) == 1


def test_429_not_retried(provider):
    calls = _script(provider, [FakeAPIError(429, "RESOURCE_EXHAUSTED")])
    with pytest.raises(FakeAPIError):
        provider.complete_json("s", "u")
    assert len(calls) == 1


def test_persistent_503_gives_up_after_three_calls(provider):
    calls = _script(provider, [FakeAPIError(503)] * 3)
    with pytest.raises(FakeAPIError):
        provider.complete_json("s", "u")
    assert len(calls) == 3


def test_disable_env_means_single_request(monkeypatch, provider):
    monkeypatch.setenv("TRUSTFLOW_DISABLE_RETRY", "1")
    p = gp.GeminiProvider()
    calls = _script(p, [FakeAPIError(503)])
    with pytest.raises(FakeAPIError):
        p.complete_json("s", "u")
    assert len(calls) == 1