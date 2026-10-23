import json

from app.agent.orchestrator import run_assessment
from app.agent.providers.fake import FakeProvider
from app.schemas.assessment import AssessmentInput, CriterionInput

EVIDENCE = "The landing page is live at the staging URL. It has a contact form and loads in 1.2 seconds."

def make_input(evidence=EVIDENCE):
    return AssessmentInput(
        milestone_id=1, evidence_revision=1, evidence_text=evidence,
        criteria=[CriterionInput(id=1, text="Contact form exists"),
                  CriterionInput(id=2, text="Mobile responsive")],
    )

def reply(v1="supported", q1="It has a contact form", v2="not_supported", q2=None):
    return json.dumps({"verdicts": [
        {"criterion_id": 1, "verdict": v1, "quote": q1, "reasoning": "found", "requested_revision": None},
        {"criterion_id": 2, "verdict": v2, "quote": q2, "reasoning": "not shown",
         "requested_revision": "Show mobile screenshots"},
    ]})

def test_happy_path_computes_summary_in_code():
    r = run_assessment(make_input(), FakeProvider([reply()]))
    assert r.trace.outcome == "ok"
    assert r.assessment.all_supported is False
    assert r.assessment.blockers == ["Criterion 2: Show mobile screenshots"]

def test_all_supported():
    p = FakeProvider([reply(v2="supported", q2="loads in 1.2 seconds")])
    r = run_assessment(make_input(), p)
    assert r.assessment.all_supported is True and r.assessment.blockers == []

def test_malformed_then_valid_retries_once():
    p = FakeProvider(["not json", reply()])
    r = run_assessment(make_input(), p)
    assert r.trace.outcome == "ok" and r.trace.attempts == 2

def test_always_malformed_gives_no_assessment():
    r = run_assessment(make_input(), FakeProvider(["nope", "still nope"]))
    assert r.assessment is None and r.trace.outcome == "invalid_output"

def test_fabricated_quote_is_rejected():
    r = run_assessment(make_input(), FakeProvider([reply(q1="invented sentence"), reply(q1="invented again")]))
    assert r.assessment is None

def test_supported_without_quote_is_rejected():
    r = run_assessment(make_input(), FakeProvider([reply(q1=None), reply(q1=None)]))
    assert r.assessment is None

def test_empty_evidence_never_calls_model():
    p = FakeProvider([])
    r = run_assessment(make_input(evidence="   "), p)
    assert r.trace.outcome == "empty_evidence" and p.calls == []

def test_provider_error_is_reported():
    r = run_assessment(make_input(), FakeProvider([TimeoutError("slow")]))
    assert r.assessment is None and r.trace.outcome == "provider_error"