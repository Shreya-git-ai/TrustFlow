"""Legacy adapter retained for isolated router tests; never mount in the product app.

Production assessments run through the authenticated, PostgreSQL-backed milestone
workflow router. This module’s process-local cache is not authoritative.

Idempotency rules:
- same (milestone_id, evidence_revision) + same content  -> cached result
- same (milestone_id, evidence_revision) + different content -> 409 Conflict
- only "ok" results are cached; failures are always retried
"""
import asyncio
import hashlib
import json
import time
from functools import lru_cache
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.agent.guards import enforce_guards
from app.schemas.assessment import AssessmentInput, AssessmentResult, RunTrace

AGENT_TIMEOUT_S = 60

router = APIRouter(prefix="/agent", tags=["agent"])

CacheKey = tuple[str, int]

# (milestone_id, evidence_revision) -> (content_hash, AssessmentResult)
_cache: dict[CacheKey, tuple[str, AssessmentResult]] = {}
# one lock per key so two simultaneous identical requests make only one model call
_locks: dict[CacheKey, asyncio.Lock] = {}

Assessor = Callable[[AssessmentInput], AssessmentResult]


@lru_cache(maxsize=1)
def _provider():
    from app.agent.providers.gemini_provider import GeminiProvider

    return GeminiProvider()


def get_assessor() -> Assessor:
    from app.agent.orchestrator import run_assessment

    provider = _provider()
    return lambda inp: run_assessment(inp, provider)


def _content_hash(inp: AssessmentInput) -> str:
    """Hash of everything the model sees, so changed evidence can't reuse an old verdict."""
    canonical = json.dumps(inp.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _conflict(inp: AssessmentInput) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail=(
            f"evidence_revision {inp.evidence_revision} for milestone {inp.milestone_id} "
            "was already assessed with different content; submit it as a new revision"
        ),
    )


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
    key: CacheKey = (inp.milestone_id, inp.evidence_revision)
    digest = _content_hash(inp)

    async with _locks.setdefault(key, asyncio.Lock()):
        cached = _cache.get(key)
        if cached is not None:
            cached_digest, cached_result = cached
            if cached_digest != digest:
                raise _conflict(inp)
            return cached_result

        started = time.monotonic()
        try:
            result = await asyncio.wait_for(run_in_threadpool(assessor, inp), AGENT_TIMEOUT_S)
        except asyncio.TimeoutError:
            return _failure("provider_error", f"agent timed out after {AGENT_TIMEOUT_S}s", started)
        except Exception as exc:  # never leak a 500 to the backend
            return _failure("provider_error", f"{type(exc).__name__}: {exc}", started)

        result = enforce_guards(inp, result)
        if result.trace.outcome == "ok":
            _cache[key] = (digest, result)
        return result


@router.get("/health")
def health() -> dict:
    return {"ok": True}
