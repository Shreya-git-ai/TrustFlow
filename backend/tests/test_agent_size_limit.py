from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent import api as agent_api


def test_oversized_evidence_is_rejected_before_model_call():
    calls = {"n": 0}

    def fake_assessor(inp):
        calls["n"] += 1
        raise AssertionError("assessor must not run for oversized evidence")

    app = FastAPI()
    app.include_router(agent_api.router)
    app.dependency_overrides[agent_api.get_assessor] = lambda: fake_assessor
    client = TestClient(app)

    body = {
        "milestone_id": "m-big",
        "evidence_revision": 1,
        "criteria": [{"id": 1, "text": "Page is live"}],
        "evidence_text": "x" * 20_001,
        "evidence_links": [],
    }
    r = client.post("/agent/assess", json=body)
    assert r.status_code == 422
    assert calls["n"] == 0