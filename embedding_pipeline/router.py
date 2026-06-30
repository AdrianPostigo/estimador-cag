"""FastAPI router for embedding ingestion."""

from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_async_session
from app.services.llm_service import LLMService
from embedding_pipeline.grounded_generation import GroundedEstimator
from embedding_pipeline.persistence import DocumentRepository
from embedding_pipeline.schemas import (
    EstimateWithContextRequest,
    EstimateWithContextResponse,
    GroundedEstimateRequest,
    GroundedEstimateResponse,
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
    Search over indexed budget chunks (semantic, lexical, hybrid, ±reranking).

    Input: query, k, search_mode, enable_reranking, reranker_k.

    Processing modes:
      - 'semantic': Vector similarity (cosine distance)
      - 'lexical': Full-text search (PostgreSQL tsvector + tsquery)
      - 'hybrid': Reciprocal Rank Fusion (fuses both rankings)

    Recall-then-rerank pattern:
      If enable_reranking=true:
        1. Retrieve top-reranker_k (wide recall)
        2. Apply FlashRank cross-encoder reranking to top-k

    Output: query, k, search_mode, enable_reranking, search_time_ms, reranking_time_ms, results[].

    Status codes:
      - 200: Success (0+ results returned)
      - 422: Validation error (query/k/search_mode invalid)
      - 500: Search/reranking error (OpenAI, database, FlashRank, etc.)
    """
    try:
        repository = DocumentRepository(session)
        result = await repository.hybrid_search(
            query=request.query,
            k=request.k,
            search_mode=request.search_mode,
            enable_reranking=request.enable_reranking,
            reranker_k=request.reranker_k,
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
        # OpenAI API errors, database errors, FlashRank errors, unexpected errors
        logger.error(
            "search_failed",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to execute search. Check server logs for details.",
        )


@router.post(
    "/estimate/with-context",
    response_model=EstimateWithContextResponse,
    status_code=200,
    summary="Estimate with context from similar historical budgets",
    tags=["embeddings"],
    responses={
        422: {"description": "Validation error (query, project_type, etc)"},
        500: {"description": "Estimation error (LLM, database, etc)"},
    },
)
async def estimate_with_context(
    request: EstimateWithContextRequest,
    session: AsyncSession = Depends(get_async_session),
) -> EstimateWithContextResponse:
    """
    Generate project estimation with context from similar historical budgets.

    Input: query (find similar budgets), search_k (how many), + estimation params.

    Processing:
      1. Retrieve top-k similar chunks via semantic search
      2. Format chunks as context block
      3. Inject context into LLM prompt
      4. Generate estimation with informed context
      5. Return: estimation + retrieval metrics + context chunks

    Output: EstimationOutput + retrieval metrics + retrieved chunks.

    This enables measuring how context improves estimation quality vs baseline /estimate.

    Status codes:
      - 200: Success (estimation generated with context)
      - 422: Validation error (query too short/long, invalid project_type, etc)
      - 500: Estimation error (LLM, database, search, etc)
    """
    try:
        repository = DocumentRepository(session)
        llm_service = LLMService()

        estimation_input = {
            "description": request.query,
            "project_type": request.project_type,
            "detail_level": request.detail_level,
            "output_format": request.output_format,
        }

        result = await repository.estimate_with_context(
            query=request.query,
            search_k=request.search_k,
            estimation_input=estimation_input,
            llm_service=llm_service,
        )

        return EstimateWithContextResponse(
            estimation=result["estimation"],
            retrieval=result["retrieval"],
            context_chunks=result["context_chunks"],
        )

    except ValueError as e:
        logger.error(
            "estimate_with_context_validation_error",
            error_message=str(e),
        )
        raise HTTPException(
            status_code=422,
            detail=f"Validation error: {str(e)}",
        )

    except Exception as e:
        logger.error(
            "estimate_with_context_failed",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to generate contextualized estimation. Check server logs for details.",
        )


@router.post(
    "/estimate/grounded",
    response_model=GroundedEstimateResponse,
    status_code=200,
    summary="Grounded estimation with verifiable line-level citations",
    tags=["embeddings"],
    responses={
        422: {"description": "Dangling citations detected (estimate rejected) or validation error"},
        500: {"description": "Generation error (OpenAI, database, etc)"},
    },
)
async def estimate_grounded(
    request: GroundedEstimateRequest,
    session: AsyncSession = Depends(get_async_session),
) -> GroundedEstimateResponse:
    """
    Generate a grounded estimate where every line cites the historical budget
    chunk it was derived from, then verify those citations.

    Processing:
      1. Retrieve top-k grounding chunks
      2. Generate a GroundedEstimateOutput via OpenAI structured outputs
      3. Verify each cited chunk_id exists in the retrieved context
      4. Reject (422) if any dangling citation is detected

    Status codes:
      - 200: Success (all citations verified)
      - 422: Dangling citations detected (quality failure) or schema validation error
      - 500: Generation error (OpenAI, database, etc)
    """
    request_id = str(uuid4())
    try:
        repository = DocumentRepository(session)
        estimator = GroundedEstimator(repository)

        result = await estimator.generate(
            query=request.query,
            search_k=request.search_k,
            search_mode=request.search_mode,
            request_id=request_id,
        )

        report = result["citation_report"]

        # Reject estimates with dangling citations: a hallucinated source is a
        # quality failure, not a cosmetic detail.
        if report.has_dangling_citations:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "dangling_citations_detected",
                    "request_id": request_id,
                    "citation_report": report.model_dump(),
                },
            )

        return GroundedEstimateResponse(
            estimate=result["estimate"],
            citation_report=report,
            contexts=result["contexts"],
            request_id=result["request_id"],
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "grounded_estimate_failed",
            request_id=request_id,
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to generate grounded estimation. Check server logs for details.",
        )
