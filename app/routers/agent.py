"""FastAPI router exposing the estimation agent (Session 12).

The business backend does not see the loop: it posts a transcript and receives a
structured estimate, plus the reasoning trace for auditability.
"""

from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_async_session
from app.generation.agentic.agent import EstimationAgent
from app.generation.agentic.schemas import AgentEstimateRequest, AgentRunResult
from embedding_pipeline.persistence import DocumentRepository

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/estimate",
    response_model=AgentRunResult,
    status_code=200,
    summary="Estimate a project from a meeting transcript using the agent",
    tags=["agent"],
    responses={
        422: {"description": "Validation error (transcript too short or too long)"},
        500: {"description": "Agent error (OpenAI, database, tool execution)"},
    },
)
async def agent_estimate(
    request: AgentEstimateRequest,
    session: AsyncSession = Depends(get_async_session),
) -> AgentRunResult:
    """
    Run the estimation agent over a meeting transcript.

    The agent decomposes the transcript into components, searches historical
    budgets for each of them, and computes the estimate with a deterministic
    tool. Every figure comes from calculate_estimate, never from the model.

    Returns the structured estimate together with the ordered reasoning trace
    (reasoning, action and observation per step).

    Status codes:
      - 200: Success
      - 422: Validation error
      - 500: Agent error (OpenAI, database, tool execution)
    """
    request_id = str(uuid4())
    try:
        repository = DocumentRepository(session)
        agent = EstimationAgent(repository)

        return await agent.run(transcript=request.transcript, request_id=request_id)

    except Exception as e:
        logger.error(
            "agent_estimate_failed",
            request_id=request_id,
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Agent failed to produce an estimate. Check server logs for details.",
        )
