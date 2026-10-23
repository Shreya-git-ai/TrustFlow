from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent import api as agent_api
from app.schemas.assessment import (
    Assessment,
    AssessmentInput,
    AssessmentResult,
    CriterionVerdict,
    RunTrace,
    Verdict,
)

EVIDENCE = "Landing page deployed at example.com. Mobile layout tested on three devices."
PAYLOAD = {
    "milestone_id": "1",
    "evidence_revision": 1,
    "criteria": [{"id": 1, "text": "Page is live"}, {"id": 2, "text": "Works on mobile"}],
    "evidence_text": EVIDENCE,
    "evidence_links": [],
}


def _trace(outcome="ok", error=None):
    return RunTrace(model="fake", prompt_version="v1", attempts=1, duration_ms=5,
                    outcome=outcome, error=error)


def _result(inp: AssessmentInput, quotes=("Landing page deployed at example.com.",
                                          "Mobile layout tested on three devices."), ids=None):
    ids = ids or [c.id for c in inp.criteria]
    verdicts = [CriterionVerdict(criterion_id=i, verdict=Verdict.SUPPORTED, quote=q, reasoning="ok")
                for i, q in zip(ids, quotes)]
    a = Assessment(milestone_id=inp.milestone_id, evidence_revision=inp.evidence_revision,
                   verdicts=verdicts, all_supported=True, blockers=[])
    return AssessmentResult(assessment=a, trace=_trace())


def make_client(assessor):
    agent_api._cache.clear()
    app = FastAPI()
    app.include_router(agent_api.router)
    app.dependency_overrides[agent_api.get_assessor] = lambda: assessor
    return TestClient(app)


def test_happy_path():
    client = make_client(_result)
    r = client.post("/agent/assess", json=PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    assert body["trace"]["outcome"] == "ok"
    assert body["assessment"]["all_supported"] is True


def test_idempotent_same_revision_calls_agent_once():
    calls = []

    def assessor(inp):
        calls.append(1)
        return _result(inp)

    client = make_client(assessor)
    client.post("/agent/assess", json=PAYLOAD)
    client.post("/agent/assess", json=PAYLOAD)
    assert len(calls) == 1


def test_new_revision_calls_agent_again():
    calls = []

    def assessor(inp):
        calls.append(1)
        return _result(inp)

    client = make_client(assessor)
    client.post("/agent/assess", json=PAYLOAD)
    client.post("/agent/assess", json={**PAYLOAD, "evidence_revision": 2})
    assert len(calls) == 2


def test_missing_criterion_is_downgraded():
    client = make_client(lambda inp: _result(inp, quotes=("Landing page deployed at example.com.",), ids=[1]))
    body = client.post("/agent/assess", json=PAYLOAD).json()
    assert body["assessment"] is None
    assert body["trace"]["outcome"] == "invalid_output"


def test_fabricated_quote_is_downgraded():
    client = make_client(lambda inp: _result(inp, quotes=("Landing page deployed at example.com.",
                                                          "This sentence is not in the evidence.")))
    body = client.post("/agent/assess", json=PAYLOAD).json()
    assert body["assessment"] is None
    assert body["trace"]["outcome"] == "invalid_output"


def test_provider_exception_returns_provider_error_not_500():
    def boom(inp):
        raise RuntimeError("gemini down")

    client = make_client(boom)
    r = client.post("/agent/assess", json=PAYLOAD)
    assert r.status_code == 200
    assert r.json()["trace"]["outcome"] == "provider_error"


def test_failures_are_not_cached():
    calls = []

    def flaky(inp):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("blip")
        return _result(inp)

    client = make_client(flaky)
    assert client.post("/agent/assess", json=PAYLOAD).json()["trace"]["outcome"] == "provider_error"
    assert client.post("/agent/assess", json=PAYLOAD).json()["trace"]["outcome"] == "ok"
