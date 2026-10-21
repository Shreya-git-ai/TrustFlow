"""Thin FastAPI layer over the assessment orchestrator.

Raghav's backend can either include this router or call POST /agent/assess over HTTP.
"""
import asyncio
import time
from typing import Callable

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.agent.guards import enforce_guards
from app.schemas.assessment import AssessmentInput, AssessmentResult, RunTrace
from functools import lru_cache

AGENT_TIMEOUT_S = 60

router = APIRouter(prefix="/agent", tags=["agent"])

# (milestone_id, evidence_revision) -> AssessmentResult. Only "ok" results are cached.
_cache: dict[tuple[int, int], AssessmentResult] = {}

Assessor = Callable[[AssessmentInput], AssessmentResult]


from functools import lru_cache


@lru_cache(maxsize=1)
def _provider():
    from app.agent.providers.gemini_provider import GeminiProvider  # CHECK: class name
    return GeminiProvider()  # CHECK: constructor args (model, api key etc.)


def get_assessor() -> Assessor:
    from app.agent.orchestrator import run_assessment

    provider = _provider()
    return lambda inp: run_assessment(inp, provider)


def _failure(outcome: str, error: str, started: float) -> AssessmentResult:
    trace = RunTrace(
        model="unknown",
        prompt_version="unknown",
        attempts=0,
        duration_ms=int((time.monotonic() - started) * 1000),
        outcome=outcome,
        error=error,
    )
    return AssessmentResult(assessment=None, trace=trace)


@router.post("/assess", response_model=AssessmentResult)
async def assess_endpoint(
    inp: AssessmentInput, assessor: Assessor = Depends(get_assessor)
) -> AssessmentResult:
    key = (inp.milestone_id, inp.evidence_revision)
    if key in _cache:
        return _cache[key]

    started = time.monotonic()
    try:
        result = await asyncio.wait_for(run_in_threadpool(assessor, inp), AGENT_TIMEOUT_S)
    except asyncio.TimeoutError:
        return _failure("provider_error", f"agent timed out after {AGENT_TIMEOUT_S}s", started)
    except Exception as exc:  # never leak a 500 to the backend
        return _failure("provider_error", f"{type(exc).__name__}: {exc}", started)

    result = enforce_guards(inp, result)
    if result.trace.outcome == "ok":
        _cache[key] = result
    return result


@router.get("/health")
def health() -> dict:
    return {"ok": True}
