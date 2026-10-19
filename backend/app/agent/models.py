from pydantic import BaseModel

from app.schemas.assessment import CriterionVerdict


class ModelOutput(BaseModel):
    """What the model is allowed to return. Summary fields are computed by code."""

    verdicts: list[CriterionVerdict]