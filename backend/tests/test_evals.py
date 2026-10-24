import unittest

from app.agent.evals.eval_cases import CASES
from app.agent.evals.run_evals import OracleProvider, evaluate


class AssessmentEvalTests(unittest.TestCase):
    def test_case_names_are_unique(self):
        names = [case["name"] for case in CASES]
        self.assertEqual(len(names), len(set(names)))

    def test_proofs_appear_in_evidence(self):
        for case in CASES:
            with self.subTest(case=case["name"]):
                for quote in case["proof"].values():
                    self.assertIn(quote, case["evidence"])

    def test_oracle_passes_every_case(self):
        for case in CASES:
            with self.subTest(case=case["name"]):
                result = evaluate(case, OracleProvider(case))
                self.assertTrue(result["ok"], result["detail"])


if __name__ == "__main__":
    unittest.main()
