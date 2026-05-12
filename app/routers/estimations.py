from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.prompts.loader import render_estimation_prompt
from app.services.llm_service import MODEL_NAME, PROVIDER, estimate_project, stream_project_estimation

router = APIRouter(
    tags=["Estimations"],
)


class EstimationRequest(BaseModel):
    project_description: str = Field(
        ...,
        min_length=20,
        description="Descripción o transcripción del proyecto del cliente",
    )
    output_format: str = Field(
        default="markdown",
        description="Formato de salida esperado: markdown o plain_text",
    )
    detail_level: str = Field(
        default="medium",
        description="Nivel de detalle: low, medium o high",
    )


class EstimationResponse(BaseModel):
    estimation: str
    model: str
    provider: str
    prompt_version: str
    timestamp: str


@router.post("/estimate", response_model=EstimationResponse)
def estimate_project_endpoint(request: EstimationRequest) -> EstimationResponse:
    prompt_version = "v1"

    try:
        system_prompt, user_prompt = render_estimation_prompt(
            request=request,
            version="v1",
        )

        estimation = estimate_project(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        return EstimationResponse(
            estimation=estimation,
            model=MODEL_NAME,
            provider=PROVIDER,
            prompt_version=prompt_version,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating estimation: {str(error)}",
        ) from error


@router.post("/estimate/stream")
def estimate_project_stream_endpoint(request: EstimationRequest) -> StreamingResponse:
    system_prompt, user_prompt = render_estimation_prompt(request=request, version="v1")

    return StreamingResponse(
        stream_project_estimation(system_prompt=system_prompt, user_prompt=user_prompt),
        media_type="text/plain",
        headers={
            "X-Model": MODEL_NAME,
            "X-Provider": PROVIDER,
            "X-Prompt-Version": "v1",
        },
    )