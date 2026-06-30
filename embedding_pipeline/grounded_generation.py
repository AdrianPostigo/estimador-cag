"""Grounded estimation generator using the OpenAI Responses API.

This is a deliberate, isolated exception to the LiteLLM provider abstraction:
the grounded endpoint uses OpenAI structured outputs (client.responses.parse)
so the GroundedEstimateOutput schema (and its integrity validators) are enforced
strictly at parse time.
"""

import os
import time
from typing import Any
from uuid import uuid4

import structlog
from openai import AsyncOpenAI

from app.prompts.loader import render_grounded_estimation_prompt
from embedding_pipeline.citations import verify_citations
from embedding_pipeline.persistence import DocumentRepository
from embedding_pipeline.schemas import GroundedEstimateOutput

logger = structlog.get_logger()

GROUNDED_MODEL = os.getenv("GROUNDED_MODEL", "gpt-4o-mini")


class GroundedEstimator:
    """Generates grounded estimates with line-level citations to historical budgets."""

    def __init__(self, repository: DocumentRepository, model: str = GROUNDED_MODEL):
        """
        Args:
            repository: Repository used to retrieve grounding chunks.
            model: OpenAI chat model used as the generator.
        """
        self.repository = repository
        self.client = AsyncOpenAI()
        self.model = model

    async def generate(
        self,
        query: str,
        search_k: int = 5,
        search_mode: str = "semantic",
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a grounded estimate and verify its citations.

        Does NOT raise on dangling citations: it always returns the estimate plus
        its citation report so callers (endpoint, RAGAS eval) can decide what to do.

        Returns:
            {
                "estimate": GroundedEstimateOutput,
                "citation_report": CitationReport,
                "contexts": list[str],          # retrieved chunk contents
                "retrieved_chunk_ids": list[str],
                "request_id": str,
                "elapsed_ms": float,
            }
        """
        request_id = request_id or str(uuid4())
        start_time = time.time()

        # Step 1: Retrieve grounding chunks
        search_result = await self.repository.hybrid_search(
            query=query,
            k=search_k,
            search_mode=search_mode,
        )
        chunks = search_result["results"]

        # Step 2: Assemble sources with stable, citable ids
        sources = []
        for chunk in chunks:
            metadata = chunk.get("metadata") or {}
            sources.append(
                {
                    "chunk_id": str(chunk["chunk_id"]),
                    "document_id": str(metadata.get("budget_id", "")),
                    "content": chunk["content"],
                }
            )

        # Step 3: Render the grounded prompt with ids propagated
        system_prompt, user_prompt = render_grounded_estimation_prompt(
            description=query,
            sources=sources,
        )

        logger.info(
            "grounded_generation_started",
            request_id=request_id,
            model=self.model,
            num_sources=len(sources),
        )

        # Step 4: Generate with strict structured output (parsed to Pydantic)
        response = await self.client.responses.parse(
            model=self.model,
            instructions=system_prompt,
            input=user_prompt,
            text_format=GroundedEstimateOutput,
        )
        estimate = response.output_parsed

        # Step 5: Verify citations against the retrieved context
        retrieved_chunk_ids = {source["chunk_id"] for source in sources}
        citation_report = verify_citations(
            estimate=estimate,
            retrieved_chunk_ids=retrieved_chunk_ids,
            request_id=request_id,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(
            "grounded_generation_completed",
            request_id=request_id,
            model=self.model,
            num_sources=len(sources),
            total_lines=citation_report.total_lines,
            has_dangling_citations=citation_report.has_dangling_citations,
            elapsed_ms=elapsed_ms,
        )

        return {
            "estimate": estimate,
            "citation_report": citation_report,
            "contexts": [source["content"] for source in sources],
            "retrieved_chunk_ids": sorted(retrieved_chunk_ids),
            "request_id": request_id,
            "elapsed_ms": round(elapsed_ms, 1),
        }
