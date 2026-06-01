from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import PROVIDER
from app.prompts.loader import render_estimation_prompt
from app.schemas import EstimationRequest, EstimationResponse, TierInfo
from app.services.guardrails import parse_and_validate
from app.services.llm_service import estimate_project, stream_project_estimation
from app.services.tier_scoring import score_input, get_model_for_tier

router = APIRouter(
    tags=["Estimations"],
)


@router.post("/estimate", response_model=EstimationResponse)
def estimate_project_endpoint(request: EstimationRequest) -> EstimationResponse:
    try:
        # Score input and select model dynamically
        tier_scoring = score_input(request.description)
        tier = tier_scoring["tier"]
        model_name = get_model_for_tier(tier)

        system_prompt, user_prompt = render_estimation_prompt(request=request, version="v1")
        raw = estimate_project(system_prompt=system_prompt, user_prompt=user_prompt)

        guardrail = parse_and_validate(raw)
        if not guardrail.passed:
            raise HTTPException(
                status_code=422,
                detail={"error": "guardrail_failed", "violations": guardrail.violations},
            )

        tier_info = TierInfo(
            tier=tier,
            score=tier_scoring["score"],
            model_selected=model_name,
            keywords_detected=tier_scoring["keywords_found"],
            reason=tier_scoring["reason"],
        )

        return EstimationResponse(
            output=guardrail.output,
            prompt_version="v1",
            model=model_name,
            provider=PROVIDER,
            tier_info=tier_info,
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
    # Score input and select model dynamically
    tier_scoring = score_input(request.description)
    model_name = get_model_for_tier(tier_scoring["tier"])

    system_prompt, user_prompt = render_estimation_prompt(request=request, version="v1")

    return StreamingResponse(
        stream_project_estimation(system_prompt=system_prompt, user_prompt=user_prompt, model_name=model_name),
        media_type="text/plain",
        headers={
            "X-Model": model_name,
            "X-Provider": PROVIDER,
            "X-Prompt-Version": "v1",
            "X-Tier": str(tier_scoring["tier"]),
            "X-Tier-Score": str(tier_scoring["score"]),
        },
    )
