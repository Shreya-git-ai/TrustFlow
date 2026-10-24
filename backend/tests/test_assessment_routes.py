import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.agent.providers.fake import FakeProvider
from app.main import app


class AssessmentRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_assessment_route_returns_verified_result(self):
        provider = FakeProvider([
            '{"verdicts":[{"criterion_id":1,"verdict":"supported",'
            '"quote":"Checkout is complete.","reasoning":"Evidence states it is complete.",'
            '"requested_revision":null}]}'
        ])
        payload = {
            "milestone_id": 7,
            "evidence_revision": 2,
            "criteria": [{"id": 1, "text": "Checkout is complete"}],
            "evidence_text": "Checkout is complete.",
        }

        with patch("app.routers.assessments.GeminiProvider", return_value=provider), patch(
            "app.routers.assessments.send_event"
        ):
            response = self.client.post("/assessments", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["assessment"]["milestone_id"], 7)
        self.assertTrue(body["assessment"]["all_supported"])
        self.assertEqual(body["trace"]["outcome"], "ok")

    def test_assessment_route_reports_missing_gemini_configuration(self):
        with patch(
            "app.routers.assessments.GeminiProvider",
            side_effect=RuntimeError("GEMINI_API_KEY is not set (check your .env)"),
        ):
            response = self.client.post(
                "/assessments",
                json={
                    "milestone_id": 1,
                    "evidence_revision": 1,
                    "criteria": [{"id": 1, "text": "Evidence exists"}],
                    "evidence_text": "Evidence exists.",
                },
            )

        self.assertEqual(response.status_code, 503)

    def test_assessment_route_maps_provider_failure_to_502(self):
        provider = FakeProvider([TimeoutError("provider timeout")])
        payload = {
            "milestone_id": 1,
            "evidence_revision": 1,
            "criteria": [{"id": 1, "text": "Evidence exists"}],
            "evidence_text": "Evidence exists.",
        }

        with patch("app.routers.assessments.GeminiProvider", return_value=provider):
            response = self.client.post("/assessments", json=payload)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["message"], "Assessment provider failed")

    def test_assessment_route_rejects_empty_criteria(self):
        response = self.client.post(
            "/assessments",
            json={
                "milestone_id": 1,
                "evidence_revision": 1,
                "criteria": [],
                "evidence_text": "Evidence exists.",
            },
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
