import argparse
import json
import sys

from app.agent.evals.eval_cases import CASES
from app.agent.orchestrator import run_assessment
from app.schemas.assessment import AssessmentInput, CriterionInput


class OracleProvider:
    """Always answers correctly. Used to test the eval cases and runner without a real model."""

    name = "oracle"

    def __init__(self, case):
        self.case = case

    def complete_json(self, system: str, user: str, timeout_s: float = 30.0) -> str:
        verdicts = []
        for cid, accepted in self.case["expected"].items():
            verdict = accepted[0]
            quote = self.case["proof"].get(cid) if verdict == "supported" else None
            verdicts.append(
                {
                    "criterion_id": cid,
                    "verdict": verdict,
                    "quote": quote,
                    "reasoning": "oracle",
                    "requested_revision": None if verdict == "supported" else "Provide evidence",
                }
            )
        return json.dumps({"verdicts": verdicts})


def to_input(case) -> AssessmentInput:
    return AssessmentInput(
        milestone_id=1,
        evidence_revision=1,
        criteria=[CriterionInput(id=i, text=t) for i, t in case["criteria"]],
        evidence_text=case["evidence"],
    )


def evaluate(case, provider) -> dict:
    result = run_assessment(to_input(case), provider)
    if result.assessment is None:
        return {"name": case["name"], "ok": False, "detail": f"no assessment ({result.trace.outcome}: {result.trace.error})"}
    problems = []
    for v in result.assessment.verdicts:
        accepted = case["expected"][v.criterion_id]
        if v.verdict.value not in accepted:
            problems.append(f"criterion {v.criterion_id}: got {v.verdict.value}, accepted {accepted}")
    return {"name": case["name"], "ok": not problems, "detail": "; ".join(problems)}


def get_provider(name: str, case):
    if name == "oracle":
        return OracleProvider(case)
    raise SystemExit(f"Provider '{name}' is not added yet. Add it in agent/providers/ and register it in get_provider().")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="oracle")
    args = parser.parse_args()

    results = [evaluate(c, get_provider(args.provider, c)) for c in CASES]
    for r in results:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['name']}  {r['detail']}")
    passed = sum(r["ok"] for r in results)
    print(f"\n{passed}/{len(results)} cases passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()