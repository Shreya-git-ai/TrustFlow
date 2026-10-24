import unittest

from fastapi.testclient import TestClient

from app.main import app


class AssessmentRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_legacy_unscoped_assessment_routes_are_not_exposed(self):
        payload = {
            "milestone_id": "milestone-7",
            "evidence_revision": 1,
            "criteria": [{"id": 1, "text": "A report exists"}],
            "evidence_text": "A report exists.",
        }
        self.assertEqual(self.client.post("/assessments", json=payload).status_code, 404)
        self.assertEqual(self.client.post("/agent/assess", json=payload).status_code, 404)

    def test_persisted_assessment_requires_a_session(self):
        response = self.client.post("/milestones/123/assessments", json={})
        self.assertEqual(response.status_code, 401)

    def test_project_data_requires_a_session(self):
        self.assertEqual(self.client.get("/projects").status_code, 401)
        self.assertEqual(self.client.get("/milestones/123").status_code, 401)


if __name__ == "__main__":
    unittest.main()
