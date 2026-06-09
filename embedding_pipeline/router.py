"""FastAPI router for embedding ingestion."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_async_session
from embedding_pipeline.persistence import DocumentRepository
from embedding_pipeline.schemas import (
    IngestBudgetRequest,
    IngestBudgetResponse,
    SearchRequest,
    SearchResponse,
)

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/ingest",
    response_model=IngestBudgetResponse,
    status_code=200,
    summary="Ingest and persist a budget with embeddings",
    tags=["embeddings"],
    responses={
        409: {
            "description": "Document with this source_path already exists",
            "model": dict,
        },
        422: {"description": "Validation error (Budget schema)"},
        500: {"description": "Embedding API error (OpenAI, network, etc.)"},
    },
)
async def ingest_budget(
    request: IngestBudgetRequest,
    session: AsyncSession = Depends(get_async_session),
) -> IngestBudgetResponse:
    """
    Ingest a budget and persist to PostgreSQL with embeddings.

    Input: source_path, document_type, content (Budget JSON).

    Processing pipeline (single transaction):
      1. Verify source_path not duplicated
      2. Create document row
      3. Chunk the budget (JSONStructuralChunker)
      4. Embed all chunks in batch (OpenAIEmbedder)
      5. Create chunk rows with embeddings
      6. Commit transaction

    Output: document_id, chunks_created, embedding_dimension, ingestion_time_ms.

    Status codes:
      - 200: Success (document persisted)
      - 409: Conflict (source_path already exists)
      - 422: Validation error (content doesn't match Budget schema)
      - 500: Embedding API error (OpenAI, network, etc.)
    """
    try:
        repository = DocumentRepository(session)
        result = await repository.ingest_budget(
            source_path=request.source_path,
            document_type=request.document_type,
            budget_dict=request.content,
        )
        return IngestBudgetResponse(**result)

    except ValueError as e:
        # Duplicate source_path or Budget validation error
        error_msg = str(e)
        if "already exists" in error_msg:
            logger.warning(
                "ingest_duplicate",
                source_path=request.source_path,
            )
            raise HTTPException(
                status_code=409,
                detail="Document already ingested",
            )
        else:
            logger.error(
                "ingest_validation_error",
                error_message=error_msg,
            )
            raise HTTPException(
                status_code=422,
                detail=f"Validation error: {error_msg}",
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


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=200,
    summary="Semantic search over embedded chunks",
    tags=["embeddings"],
    responses={
        422: {"description": "Validation error (query or k invalid)"},
        500: {"description": "Search error (embedding API, database, etc.)"},
    },
)
async def search_chunks(
    request: SearchRequest,
    session: AsyncSession = Depends(get_async_session),
) -> SearchResponse:
    """
    Semantic search over indexed budget chunks.

    Input: query (text to search for), k (number of results).

    Processing:
      1. Embed query with text-embedding-3-small
      2. Execute k-nearest neighbors via cosine distance in PostgreSQL
      3. Return k results sorted by distance (ascending = most similar)

    Output: query, k, search_time_ms, results[] with metadata.

    Status codes:
      - 200: Success (0+ results returned)
      - 422: Validation error (query too short/long, k out of range)
      - 500: Search error (OpenAI, database, etc.)
    """
    try:
        repository = DocumentRepository(session)
        result = await repository.search(
            query=request.query,
            k=request.k,
        )
        return SearchResponse(**result)

    except ValueError as e:
        logger.error(
            "search_validation_error",
            error_message=str(e),
        )
        raise HTTPException(
            status_code=422,
            detail=f"Validation error: {str(e)}",
        )

    except Exception as e:
        # OpenAI API errors, database errors, unexpected errors
        logger.error(
            "search_failed",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to execute search. Check server logs for details.",
        )
