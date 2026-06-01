"""FastAPI router for embedding ingestion."""

import structlog
from fastapi import APIRouter, HTTPException

from embedding_pipeline.chunker import JSONStructuralChunker
from embedding_pipeline.embedder import OpenAIEmbedder
from embedding_pipeline.schemas import IngestRequest, IngestResponse

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=200,
    summary="Ingest and embed budget documents",
    tags=["embeddings"],
)
async def ingest_budgets(request: IngestRequest) -> IngestResponse:
    """
    Ingest budget documents, chunk them, and embed all chunks.

    Input: List of budgets with components.

    Processing pipeline:
      1. Chunk by component (JSONStructuralChunker)
      2. Embed all chunks in batches (OpenAIEmbedder)
      3. Aggregate statistics (tokens, cost)

    Output: EmbeddedChunk list + aggregated stats.

    Status codes:
      - 200: Success
      - 422: Validation error (Pydantic)
      - 500: Embedding API error (OpenAI, network, etc.)
    """
    try:
        # Stage 1: Chunk budgets by component
        chunker = JSONStructuralChunker()
        chunks = chunker.chunk(request.budgets)

        logger.info(
            "chunking_complete",
            budget_count=len(request.budgets),
            chunk_count=len(chunks),
        )

        # Stage 2: Embed chunks in batches
        embedder = OpenAIEmbedder()
        embedded_chunks, stats = embedder.embed_many(chunks)

        logger.info(
            "ingestion_embedding_complete",
            chunk_count=len(embedded_chunks),
            total_tokens=stats.get("total_tokens"),
            estimated_cost_usd=stats.get("estimated_cost_usd"),
        )

        # Stage 3: Assemble response
        response = IngestResponse(
            chunks=embedded_chunks,
            stats=stats,
        )

        return response

    except ValueError as e:
        # Chunking validation errors
        logger.error(
            "chunking_error",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=422,
            detail=f"Validation error: {str(e)}",
        )

    except Exception as e:
        # OpenAI API errors, network errors, unexpected errors
        logger.error(
            "ingest_failed",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to process embedding request. Check server logs for details.",
        )
