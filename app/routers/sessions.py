from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import PROVIDER
from app.schemas import (
    DetailLevel,
    EstimationResponse,
    OutputFormat,
    ProjectType,
    TierInfo,
)
from app.services.attachments import extract_text
from app.services.estimation_service import estimate_conversational
from app.sessions import create_session, get_session, Session

router = APIRouter(tags=["Sessions"])


class CreateSessionResponse(BaseModel):
    session_id: str


class SessionDebugResponse(BaseModel):
    session_id: str
    message_count: int
    anchors_count: int
    summary_chars: int
    last_resolved_tier: int | None
    last_tier_rule: str | None
    last_turn_observables: dict | None = None  # Latest turn metrics


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session_endpoint() -> CreateSessionResponse:
    session: Session = create_session()
    return CreateSessionResponse(session_id=session.session_id)


@router.get("/sessions/{session_id}", response_model=SessionDebugResponse)
def get_session_debug(session_id: str) -> SessionDebugResponse:
    """Debug endpoint exposing internal session observables including latest turn metrics."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    summary_text = session.history._accumulated_summary or ""
    return SessionDebugResponse(
        session_id=session_id,
        message_count=len(session.history._messages),
        anchors_count=session.anchors_count,
        summary_chars=len(summary_text),
        last_resolved_tier=session.last_resolved_tier,
        last_tier_rule=session.last_tier_rule,
        last_turn_observables=session.last_turn_observables,
    )


@router.post("/sessions/{session_id}/estimate", response_model=EstimationResponse)
def session_estimate(
    session_id: str,
    description: str = Form(...),
    project_type: ProjectType = Form(...),
    detail_level: DetailLevel = Form(...),
    output_format: OutputFormat = Form(...),
    attachment: UploadFile | None = File(None),
) -> EstimationResponse:
    from app.services.tier_scoring import get_model_for_tier, score_input

    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Extract attachment if present
    attachment_text = ""
    attachment_filename = ""
    if attachment is not None:
        raw = attachment.file.read()
        attachment_text = extract_text(attachment.filename or "file", raw)
        attachment_filename = attachment.filename or "file"

    # Use unified estimation service
    try:
        output, observables = estimate_conversational(
            session=session,
            description=description,
            project_type=project_type,
            detail_level=detail_level,
            output_format=output_format,
            attachment_text=attachment_text,
            attachment_filename=attachment_filename,
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating estimation: {str(error)}",
        ) from error

    # Get tier info for response
    tier_scoring = score_input(description)
    model_name = get_model_for_tier(session.last_resolved_tier)

    tier_info = TierInfo(
        tier=session.last_resolved_tier,
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
        cost_usd=observables.cost_usd,
        latency_ms=observables.latency_ms,
        tokens_in=observables.tokens_in,
        tokens_out=observables.tokens_out,
        project_metadata=session.metadata,
        tier_info=tier_info,
    )
