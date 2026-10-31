import json
import unittest

from app.agent.orchestrator import run_assessment
from app.agent.providers.fake import FakeProvider
from app.schemas.assessment import AssessmentInput, CriterionInput


EVIDENCE = "The landing page is live at the staging URL. It has a contact form and loads in 1.2 seconds."


def make_input(evidence=EVIDENCE):
    return AssessmentInput(
        milestone_id=1,
        evidence_revision=1,
        evidence_text=evidence,
        criteria=[
            CriterionInput(id=1, text="Contact form exists"),
            CriterionInput(id=2, text="Mobile responsive"),
        ],
    )


def reply(v1="supported", q1="It has a contact form", v2="not_supported", q2=None):
    return json.dumps(
        {
            "verdicts": [
                {
                    "criterion_id": 1,
                    "verdict": v1,
                    "quote": q1,
                    "reasoning": "found",
                    "requested_revision": None,
                },
                {
                    "criterion_id": 2,
                    "verdict": v2,
                    "quote": q2,
                    "reasoning": "not shown",
                    "requested_revision": "Show mobile screenshots",
                },
            ]
        }
    )


class AgentOrchestratorTests(unittest.TestCase):
    def test_happy_path_computes_summary_in_code(self):
        result = run_assessment(make_input(), FakeProvider([reply()]))
        self.assertEqual(result.trace.outcome, "ok")
        self.assertFalse(result.assessment.all_supported)
        self.assertEqual(
            result.assessment.blockers, ["Criterion 2: Show mobile screenshots"]
        )

    def test_all_supported(self):
        provider = FakeProvider([reply(v2="supported", q2="loads in 1.2 seconds")])
        result = run_assessment(make_input(), provider)
        self.assertTrue(result.assessment.all_supported)
        self.assertEqual(result.assessment.blockers, [])

    def test_malformed_then_valid_retries_once(self):
        result = run_assessment(make_input(), FakeProvider(["not json", reply()]))
        self.assertEqual(result.trace.outcome, "ok")
        self.assertEqual(result.trace.attempts, 2)

    def test_always_malformed_gives_no_assessment(self):
        result = run_assessment(make_input(), FakeProvider(["nope", "still nope"]))
        self.assertIsNone(result.assessment)
        self.assertEqual(result.trace.outcome, "invalid_output")

    def test_fabricated_quote_is_rejected(self):
        result = run_assessment(
            make_input(),
            FakeProvider(
                [reply(q1="invented sentence"), reply(q1="invented again")]
            ),
        )
        self.assertIsNone(result.assessment)

    def test_supported_without_quote_is_rejected(self):
        result = run_assessment(
            make_input(), FakeProvider([reply(q1=None), reply(q1=None)])
        )
        self.assertIsNone(result.assessment)

    def test_empty_evidence_never_calls_model(self):
        provider = FakeProvider([])
        result = run_assessment(make_input(evidence="   "), provider)
        self.assertEqual(result.trace.outcome, "empty_evidence")
        self.assertEqual(provider.calls, [])

    def test_provider_error_is_reported(self):
        result = run_assessment(make_input(), FakeProvider([TimeoutError("slow")]))
        self.assertIsNone(result.assessment)
        self.assertEqual(result.trace.outcome, "provider_error")

    def test_attachment_and_link_claims_cannot_support_met(self):
        cases = [
            ("Attached file: report.pdf", "Attached file: report.pdf"),
            ("See attached report", "See attached report"),
            ("Attached file: source-code.zip", "source-code.zip"),
            (
                "Attached file shows 100% test coverage",
                "Attached file shows 100% test coverage",
            ),
            ("https://example.test/coverage", "https://example.test/coverage"),
            ("See link for 100% test coverage", "See link for 100% test coverage"),
        ]
        for evidence, quote in cases:
            with self.subTest(evidence=evidence):
                inp = AssessmentInput(
                    milestone_id="1",
                    evidence_revision=1,
                    criteria=[CriterionInput(id=1, text="Unit tests pass")],
                    evidence_text=evidence,
                )
                raw = json.dumps({"verdicts": [{
                    "criterion_id": 1,
                    "verdict": "met",
                    "quote": quote,
                    "reasoning": "The cited text supports passing tests.",
                }]})
                result = run_assessment(inp, FakeProvider([raw]))
                self.assertEqual(result.trace.outcome, "ok")
                self.assertEqual(result.assessment.verdicts[0].verdict.value, "unable_to_verify")
                self.assertIn("attachment or link", result.assessment.verdicts[0].reasoning)
                self.assertFalse(result.assessment.all_supported)

    def test_substantive_evidence_remains_met_with_attachment_reference(self):
        inp = AssessmentInput(
            milestone_id="1",
            evidence_revision=1,
            criteria=[CriterionInput(id=1, text="Unit tests pass")],
            evidence_text="All unit tests pass. See attached report.",
        )
        raw = json.dumps({"verdicts": [{
            "criterion_id": 1,
            "verdict": "met",
            "quote": "All unit tests pass.",
            "reasoning": "The evidence directly states that tests pass.",
        }]})
        result = run_assessment(inp, FakeProvider([raw]))
        self.assertEqual(result.assessment.verdicts[0].verdict.value, "met")
        self.assertTrue(result.assessment.all_supported)


if __name__ == "__main__":
    unittest.main()
