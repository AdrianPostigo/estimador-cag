from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.llm_service import estimate_project_from_transcription

router = APIRouter(
    prefix="/api/v1",
    tags=["Estimations"],
)


class EstimationRequest(BaseModel):
    transcription: str = Field(
        ...,
        min_length=20,
        description="Transcripción de la reunión con el cliente",
    )


class EstimationResponse(BaseModel):
    estimation: str
    model: str
    provider: str
    timestamp: str


@router.post("/estimate", response_model=EstimationResponse)
def estimate_project(request: EstimationRequest) -> EstimationResponse:
    try:
        estimation = estimate_project_from_transcription(
            meeting_transcription=request.transcription
        )

        return EstimationResponse(
            estimation=estimation,
            model="claude-sonnet-4-5",
            provider="anthropic",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating estimation: {str(error)}",
        ) from error