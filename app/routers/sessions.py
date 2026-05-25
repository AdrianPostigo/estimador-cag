from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import PROVIDER
from app.prompts.loader import render_estimation_prompt
from app.schemas import (
    DetailLevel,
    EstimationRequest,
    EstimationResponse,
    OutputFormat,
    ProjectType,
    TierInfo,
    ACBInfo,
)
from app.services.attachments import extract_text
from app.services.actor_critic_boss import estimate_with_acb
from app.services.metadata import update_metadata
from app.services.tier_scoring import score_input, get_model_for_tier
from app.sessions import Session, create_session, get_session

router = APIRouter(tags=["Sessions"])


class CreateSessionResponse(BaseModel):
    session_id: str


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session_endpoint() -> CreateSessionResponse:
    session: Session = create_session()
    return CreateSessionResponse(session_id=session.session_id)


@router.post("/sessions/{session_id}/estimate", response_model=EstimationResponse)
def session_estimate(
    session_id: str,
    description: str = Form(...),
    project_type: ProjectType = Form(...),
    detail_level: DetailLevel = Form(...),
    output_format: OutputFormat = Form(...),
    attachment: UploadFile | None = File(None),
) -> EstimationResponse:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    request = EstimationRequest(
        description=description,
        project_type=project_type,
        detail_level=detail_level,
        output_format=output_format,
    )

    user_content = description
    if attachment is not None:
        raw = attachment.file.read()
        att_text = extract_text(attachment.filename or "file", raw)
        user_content += f"\n\n--- adjunto: {attachment.filename} ---\n{att_text}"

    system_prompt, _ = render_estimation_prompt(
        request=request,
        version="v1",
        project_metadata=session.metadata if session.history.turn_count > 0 else None,
    )

    # Score input and select model dynamically
    tier_scoring = score_input(description)
    tier = tier_scoring["tier"]
    model_name = get_model_for_tier(tier)

    messages = session.history.to_messages_list(system_prompt)
    messages.append({"role": "user", "content": user_content})

    try:
        output, raw_output, acb_info = estimate_with_acb(
            messages=messages,
            metadata=session.metadata,
            description=description,
            model_name=model_name,
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating estimation: {str(error)}",
        ) from error

    session.history.add_turn(user_content, raw_output)
    session.metadata = update_metadata(session.metadata, output, description)

    tier_info = TierInfo(
        tier=tier,
        score=tier_scoring["score"],
        model_selected=model_name,
        keywords_detected=tier_scoring["keywords_found"],
        reason=tier_scoring["reason"],
    )

    return EstimationResponse(
        output=output,
        prompt_version="v1",
        model=model_name,
        provider=PROVIDER,
        project_metadata=session.metadata,
        tier_info=tier_info,
        acb_info=acb_info,
    )
