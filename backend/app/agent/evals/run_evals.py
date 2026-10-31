import argparse
import json
import os
import sys
import time
from pathlib import Path

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
            quote = self.case["proof"].get(cid) if verdict in {"supported", "met"} else None
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
        milestone_id="1",
        evidence_revision=1,
        criteria=[CriterionInput(id=i, text=t) for i, t in case["criteria"]],
        evidence_text=case["evidence"],
        evidence_links=case.get("links", []),
    )


def evaluate(case, provider) -> dict:
    result = run_assessment(to_input(case), provider)
    if result.assessment is None:
        expected = case.get("expected_outcome")
        ok = result.trace.outcome == expected if expected else False
        return {"name": case["name"], "ok": ok, "detail": f"no assessment ({result.trace.outcome}: {result.trace.error})"}
    problems = []
    for v in result.assessment.verdicts:
        accepted = case["expected"][v.criterion_id]
        if v.verdict.value not in accepted:
            problems.append(f"criterion {v.criterion_id}: got {v.verdict.value}, accepted {accepted}")
        if v.verdict.value in {"met", "supported"} and v.criterion_id in case.get("proof", {}):
            if not v.quote or v.quote not in case["evidence"]:
                problems.append(f"criterion {v.criterion_id}: supported without an exact evidence quote")
    detail = "; ".join(problems)
    detail += f" [attempts={result.trace.attempts}, {result.trace.duration_ms}ms]"
    return {"name": case["name"], "ok": not problems, "detail": detail}


def get_provider(name: str, case):
    if name == "oracle":
        return OracleProvider(case)
    if name == "gemini":
        from app.agent.providers.gemini_provider import GeminiProvider
        return GeminiProvider()
    raise SystemExit(f"Provider '{name}' is not added yet. Add it in agent/providers/ and register it in get_provider().")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="oracle")
    parser.add_argument("--delay", type=float, default=0.0, help="seconds to wait between cases (free-tier rate limits)")
    parser.add_argument("--raw-output", help="append raw provider replies as JSONL (keep this file local and ignored)")
    parser.add_argument("--case", action="append", help="run only the named case; may be repeated")
    args = parser.parse_args()

    cases = [case for case in CASES if not args.case or case["name"] in args.case]
    if args.case and {case["name"] for case in cases} != set(args.case):
        raise SystemExit("Unknown case name")
    if args.provider == "gemini":
        # Enforce the task's approved models even if the shell environment differs.
        os.environ["TRUSTFLOW_MODEL"] = "gemini-3.5-flash-lite"
        os.environ["TRUSTFLOW_FALLBACK_MODEL"] = "gemini-3.1-flash-lite"

    results = []
    for i, case in enumerate(cases):
        if i and args.delay:
            time.sleep(args.delay)
        provider = get_provider(args.provider, case)
        raw_replies = []
        if args.raw_output:
            original_complete = provider.complete_json
            calls = 0
            def capture(system, user, timeout_s=30.0):
                nonlocal calls
                if calls:
                    raise RuntimeError("real-provider eval is limited to one request per case")
                calls += 1
                raw = original_complete(system, user, timeout_s)
                raw_replies.append(raw)
                return raw
            provider.complete_json = capture
        result = evaluate(case, provider)
        results.append(result)
        if args.raw_output:
            output = Path(args.raw_output)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"name": case["name"], "raw_replies": raw_replies}, ensure_ascii=False) + "\n")
        if args.provider == "gemini" and not result["ok"] and "provider_error" in result["detail"]:
            print("Stopping after provider error; no further Gemini calls will be made.")
            break

    for r in results:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['name']}  {r['detail']}")
    passed = sum(r["ok"] for r in results)
    print(f"\n{passed}/{len(results)} cases passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
