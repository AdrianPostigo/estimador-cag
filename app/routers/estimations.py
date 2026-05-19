from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import MODEL_NAME, PROVIDER
from app.prompts.loader import render_estimation_prompt
from app.schemas import EstimationRequest, EstimationResponse
from app.services.guardrails import parse_and_validate
from app.services.llm_service import estimate_project, stream_project_estimation

router = APIRouter(
    tags=["Estimations"],
)


@router.post("/estimate", response_model=EstimationResponse)
def estimate_project_endpoint(request: EstimationRequest) -> EstimationResponse:
    try:
        system_prompt, user_prompt = render_estimation_prompt(request=request, version="v1")
        raw = estimate_project(system_prompt=system_prompt, user_prompt=user_prompt)

        guardrail = parse_and_validate(raw)
        if not guardrail.passed:
            raise HTTPException(
                status_code=422,
                detail={"error": "guardrail_failed", "violations": guardrail.violations},
            )

        return EstimationResponse(
            output=guardrail.output,
            prompt_version="v1",
            model=MODEL_NAME,
            provider=PROVIDER,
        )

    except HTTPException:
        raise
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
