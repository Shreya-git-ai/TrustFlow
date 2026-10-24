from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent import api as agent_api
from app.schemas.assessment import (
    Assessment,
    AssessmentResult,
    CriterionVerdict,
    RunTrace,
)


def make_client():
    calls = {"n": 0}

    def fake_assessor(inp):
        calls["n"] += 1
        a = Assessment(
            milestone_id=inp.milestone_id,
            evidence_revision=inp.evidence_revision,
            verdicts=[
                CriterionVerdict(
                    criterion_id=1,
                    verdict="supported",
                    quote=inp.evidence_text,
                    reasoning="ok",
                    requested_revision=None,
                )
            ],
            all_supported=True,
            blockers=[],
        )
        trace = RunTrace(
            model="fake", prompt_version="t", attempts=1, duration_ms=1, outcome="ok", error=None
        )
        return AssessmentResult(assessment=a, trace=trace)

    app = FastAPI()
    app.include_router(agent_api.router)
    app.dependency_overrides[agent_api.get_assessor] = lambda: fake_assessor
    agent_api._cache.clear()
    agent_api._locks.clear()
    return TestClient(app), calls


def payload(text="Landing page is live.", revision=1, milestone="m-1"):
    return {
        "milestone_id": milestone,
        "evidence_revision": revision,
        "criteria": [{"id": 1, "text": "Page is live"}],
        "evidence_text": text,
        "evidence_links": [],
    }


def test_same_key_same_content_is_cached():
    client, calls = make_client()
    assert client.post("/agent/assess", json=payload()).status_code == 200
    assert client.post("/agent/assess", json=payload()).status_code == 200
    assert calls["n"] == 1


def test_same_revision_different_content_conflicts():
    client, calls = make_client()
    assert client.post("/agent/assess", json=payload("Landing page is live.")).status_code == 200
    r = client.post("/agent/assess", json=payload("Totally different evidence."))
    assert r.status_code == 409
    assert calls["n"] == 1


def test_new_revision_runs_again():
    client, calls = make_client()
    client.post("/agent/assess", json=payload("Landing page is live.", revision=1))
    r = client.post("/agent/assess", json=payload("Landing page is live now.", revision=2))
    assert r.status_code == 200
    assert calls["n"] == 2
