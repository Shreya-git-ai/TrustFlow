from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.agent.orchestrator import run_assessment
from app.agent.providers.gemini_provider import GeminiProvider
from app.integrations.zapier import send_event
from app.schemas.assessment import AssessmentInput, AssessmentResult

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.post("", response_model=AssessmentResult)
def assess_evidence(
    request: AssessmentInput, background_tasks: BackgroundTasks
) -> AssessmentResult:
    """Assess evidence against milestone criteria. This does not approve payment."""
    try:
        provider = GeminiProvider()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    result = run_assessment(request, provider)
    if result.trace.outcome == "provider_error":
        raise HTTPException(
            status_code=502,
            detail={"message": "Assessment provider failed", "trace": result.trace.model_dump()},
        )
    background_tasks.add_task(
        send_event,
        "assessment.completed",
        {
            "milestone_id": request.milestone_id,
            "evidence_revision": request.evidence_revision,
            "outcome": result.trace.outcome,
            "all_supported": (
                result.assessment.all_supported if result.assessment else False
            ),
            "blocker_count": len(result.assessment.blockers)
            if result.assessment
            else 0,
        },
    )
    return result
