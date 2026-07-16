"""FastAPI router exposing the estimation graph (Session 13).

The external contract is unchanged: a transcript goes in, a structured estimate
with its status comes out. The graph lives entirely inside the AI service.

The graph is compiled once at application startup with the Postgres checkpointer
(see app/main.py lifespan) and reached through app.state.
"""

from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_async_session
from embedding_pipeline.persistence import DocumentRepository

logger = structlog.get_logger()

router = APIRouter()


class GraphEstimateRequest(BaseModel):
    """Request carrying the meeting transcript to estimate."""

    transcript: str = Field(min_length=20, max_length=50000)


class GraphEstimateResponse(BaseModel):
    """Structured estimate produced by the graph, plus its status."""

    status: str | None = Field(description="'validated' | 'needs_review'")
    estimate: dict | None = Field(description="Breakdown + total from generate_estimate")
    requirements: list[str] = Field(description="Requirements extracted from the transcript")
    components: list[dict] = Field(description="Components classified from the requirements")
    errors: list[str] = Field(description="Issues accumulated during the run")
    request_id: str = Field(description="Estimation id, used as the graph thread_id")


@router.post(
    "/estimate",
    response_model=GraphEstimateResponse,
    status_code=200,
    summary="Estimate a project from a transcript using the LangGraph flow",
    tags=["graph"],
    responses={
        422: {"description": "Validation error (transcript too short or too long)"},
        500: {"description": "Graph execution error"},
    },
)
async def graph_estimate(
    request: GraphEstimateRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> GraphEstimateResponse:
    """Run the estimation graph end to end and return the estimate + status."""
    estimation_id = str(uuid4())
    try:
        repository = DocumentRepository(session)
        # The estimation id is the graph thread_id, so a run can be resumed and
        # inspected in the checkpointer.
        config = {
            "configurable": {
                "thread_id": estimation_id,
                "repository": repository,
            }
        }

        graph = http_request.app.state.graph
        result = await graph.ainvoke(
            {"transcript": request.transcript, "budget_matches": [], "errors": []},
            config,
        )

        return GraphEstimateResponse(
            status=result.get("status"),
            estimate=result.get("estimate"),
            requirements=result.get("requirements", []),
            components=result.get("components", []),
            errors=result.get("errors", []),
            request_id=estimation_id,
        )

    except Exception as e:
        logger.error(
            "graph_estimate_failed",
            request_id=estimation_id,
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Graph failed to produce an estimate. Check server logs for details.",
        )
