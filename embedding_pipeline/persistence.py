"""Persistence layer for documents and chunks with transactional guarantees."""

import time
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from embedding_pipeline.chunker import JSONStructuralChunker
from embedding_pipeline.embedder import OpenAIEmbedder
from embedding_pipeline.models import Chunk, Document
from embedding_pipeline.reranker import get_reranker
from embedding_pipeline.schemas import Budget

logger = structlog.get_logger()


class DocumentRepository:
    """Handles transactional ingestion of budgets into documents + chunks."""

    def __init__(self, session: AsyncSession):
        """Initialize with async SQLAlchemy session."""
        self.session = session
        self.chunker = JSONStructuralChunker()
        self.embedder = OpenAIEmbedder()

    async def ingest_budget(
        self,
        source_path: str,
        document_type: str,
        budget_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Ingest a budget into documents + chunks in a single transaction.

        Args:
            source_path: Unique identifier (e.g., "data/budgets/budget_2024_q1.json")
            document_type: Classification (e.g., "historical_budget")
            budget_dict: Complete Budget JSON (will be validated as Budget model)

        Returns:
            {
                "document_id": int,
                "chunks_created": int,
                "embedding_dimension": 1536,
                "ingestion_time_ms": float,
            }

        Raises:
            ValueError: If source_path already exists (409 Conflict)
            SQLAlchemy/OpenAI exceptions: Rolled back automatically
        """
        start_time = time.time()

        try:
            # Step 1: Verify no duplicate
            existing = await self.session.execute(
                select(Document).where(Document.source_path == source_path)
            )
            if existing.scalar_one_or_none():
                logger.error(
                    "ingest_duplicate_source_path",
                    source_path=source_path,
                )
                raise ValueError(f"Document with source_path '{source_path}' already exists")

            # Step 2: Validate and parse budget
            budget = Budget.model_validate(budget_dict)

            # Step 3: Create document row
            document = Document(
                source_path=source_path,
                document_type=document_type,
                doc_metadata={
                    "budget_id": budget.budget_id,
                    "client_name": budget.client_metadata.name,
                    "client_sector": budget.client_metadata.sector,
                    "year": budget.year,
                },
            )
            self.session.add(document)
            await self.session.flush()  # Get document.id without committing

            logger.info(
                "document_created",
                document_id=document.id,
                source_path=source_path,
            )

            # Step 4: Chunk the budget
            from embedding_pipeline.schemas import Chunk as ChunkSchema

            chunk_schemas = self.chunker.chunk([budget])
            logger.info(
                "chunking_complete",
                document_id=document.id,
                chunk_count=len(chunk_schemas),
            )

            # Step 5: Embed all chunks in a single batch
            embedded_chunks, stats = self.embedder.embed_many(chunk_schemas)
            logger.info(
                "embedding_complete",
                document_id=document.id,
                chunk_count=len(embedded_chunks),
                total_tokens=stats.get("total_tokens"),
                estimated_cost_usd=stats.get("estimated_cost_usd"),
            )

            # Step 6: Create chunk rows
            chunks = [
                Chunk(
                    document_id=document.id,
                    chunk_type="component",  # All chunks from budget components
                    content=embedded_chunk.text,
                    embedding=embedded_chunk.embedding,
                    chunk_metadata={
                        **embedded_chunk.metadata,
                        "chunk_id": embedded_chunk.chunk_id,
                    },
                )
                for embedded_chunk in embedded_chunks
            ]
            self.session.add_all(chunks)
            await self.session.flush()

            logger.info(
                "chunks_created",
                document_id=document.id,
                chunk_count=len(chunks),
            )

            # Step 7: Commit transaction
            await self.session.commit()

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "ingest_success",
                document_id=document.id,
                chunks_created=len(chunks),
                elapsed_ms=elapsed_ms,
            )

            return {
                "document_id": document.id,
                "chunks_created": len(chunks),
                "embedding_dimension": 1536,
                "ingestion_time_ms": round(elapsed_ms, 1),
            }

        except ValueError as e:
            await self.session.rollback()
            raise

        except Exception as e:
            await self.session.rollback()
            logger.error(
                "ingest_failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def search(
        self,
        query: str,
        k: int = 5,
    ) -> dict[str, Any]:
        """
        Semantic search over indexed chunks.

        Args:
            query: Text query to search for
            k: Number of nearest neighbors to return

        Returns:
            {
                "query": str,
                "k": int,
                "search_time_ms": float,
                "results": [
                    {
                        "chunk_id": int,
                        "document_id": int,
                        "chunk_type": str,
                        "content": str,
                        "distance": float,
                        "metadata": dict,
                    }
                ],
            }
        """
        start_time = time.time()

        try:
            # Embed the query
            query_embedding = self.embedder.embed_one(query)

            logger.info(
                "search_query_embedded",
                query_length=len(query),
            )

            # Execute k-nearest neighbors query via SQLAlchemy
            stmt = (
                select(
                    Chunk.id,
                    Chunk.document_id,
                    Chunk.chunk_type,
                    Chunk.content,
                    Chunk.chunk_metadata,
                    Chunk.embedding.cosine_distance(query_embedding).label("distance"),
                )
                .order_by(Chunk.embedding.cosine_distance(query_embedding))
                .limit(k)
            )

            result = await self.session.execute(stmt)
            rows = result.fetchall()

            elapsed_ms = (time.time() - start_time) * 1000

            # Format results
            results = [
                {
                    "chunk_id": row.id,
                    "document_id": row.document_id,
                    "chunk_type": row.chunk_type,
                    "content": row.content,
                    "distance": float(row.distance),
                    "metadata": row.chunk_metadata,
                }
                for row in rows
            ]

            logger.info(
                "search_complete",
                query_length=len(query),
                k=k,
                results_count=len(results),
                elapsed_ms=elapsed_ms,
            )

            return {
                "query": query,
                "k": k,
                "search_time_ms": round(elapsed_ms, 1),
                "results": results,
            }

        except Exception as e:
            logger.error(
                "search_failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def search_fulltext(
        self,
        query: str,
        k: int = 5,
    ) -> dict[str, Any]:
        """
        Full-text search using PostgreSQL tsvector and tsquery.

        Uses Spanish text search configuration for stop words and stemming.

        Args:
            query: Search query (Spanish text)
            k: Number of nearest neighbors to return

        Returns:
            {
                "query": str,
                "k": int,
                "search_time_ms": float,
                "results": [
                    {
                        "chunk_id": int,
                        "document_id": int,
                        "chunk_type": str,
                        "content": str,
                        "rank": float,
                        "metadata": dict,
                    }
                ],
            }
        """
        start_time = time.time()

        try:
            # Build an OR'd tsquery with Spanish config.
            # plainto_tsquery ANDs every term, which is too strict for long
            # natural-language queries (no single chunk holds all words).
            # ORing the terms is recall-oriented: any matching keyword
            # contributes, and ts_rank orders by how many terms match.
            import re

            from sqlalchemy import func as sa_func

            terms = re.findall(r"\w+", query.lower())
            if not terms:
                elapsed_ms = (time.time() - start_time) * 1000
                return {
                    "query": query,
                    "k": k,
                    "search_time_ms": round(elapsed_ms, 1),
                    "results": [],
                }

            tsquery = sa_func.to_tsquery("spanish", " | ".join(terms))

            # Execute full-text search with ts_rank for relevance scoring.
            # Use the @@ match operator directly against our prebuilt tsquery.
            stmt = (
                select(
                    Chunk.id,
                    Chunk.document_id,
                    Chunk.chunk_type,
                    Chunk.content,
                    Chunk.chunk_metadata,
                    sa_func.ts_rank(Chunk.content_fts, tsquery).label("rank"),
                )
                .where(Chunk.content_fts.op("@@")(tsquery))
                .order_by(sa_func.ts_rank(Chunk.content_fts, tsquery).desc())
                .limit(k)
            )

            result = await self.session.execute(stmt)
            rows = result.fetchall()

            elapsed_ms = (time.time() - start_time) * 1000

            # Format results
            results = [
                {
                    "chunk_id": row.id,
                    "document_id": row.document_id,
                    "chunk_type": row.chunk_type,
                    "content": row.content,
                    "rank": float(row.rank),
                    "metadata": row.chunk_metadata,
                }
                for row in rows
            ]

            logger.info(
                "fulltext_search_complete",
                query_length=len(query),
                k=k,
                results_count=len(results),
                elapsed_ms=elapsed_ms,
            )

            return {
                "query": query,
                "k": k,
                "search_time_ms": round(elapsed_ms, 1),
                "results": results,
            }

        except Exception as e:
            logger.error(
                "fulltext_search_failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def estimate_with_context(
        self,
        query: str,
        search_k: int,
        estimation_input: dict[str, Any],
        llm_service: Any,  # LLMService instance (avoid circular import)
    ) -> dict[str, Any]:
        """
        Generate estimation with context from similar historical budgets.

        Orchestrates: search → format context → call LLM → return estimation + metrics.

        Args:
            query: Search query to find similar budgets
            search_k: Number of chunks to retrieve as context
            estimation_input: Dict with description, project_type, detail_level, output_format
            llm_service: LLMService instance for calling LLM

        Returns:
            {
                "estimation": { /* EstimationOutput */ },
                "retrieval": { query, search_time_ms, chunks_retrieved, top_distance },
                "context_chunks": [{ chunk_id, rank, distance, content, metadata }],
            }
        """
        start_time = time.time()

        try:
            # Step 1: Retrieve similar chunks
            search_result = await self.search(query=query, k=search_k)
            retrieval_time_ms = search_result["search_time_ms"]
            chunks = search_result["results"]

            logger.info(
                "estimate_with_context_retrieval_done",
                query=query,
                chunks_retrieved=len(chunks),
                retrieval_time_ms=retrieval_time_ms,
            )

            # Step 2: Format chunks for prompt (as context block)
            context_block = self._format_chunks_as_context(chunks)

            # Step 3: Inject context into estimation request
            enriched_description = f"{estimation_input.get('description', '')}\n\n## Similar historical budgets\n{context_block}"

            # Step 4: Call LLM with context
            estimation_output = await llm_service.stream_project_estimation(
                description=enriched_description,
                project_type=estimation_input.get("project_type"),
                detail_level=estimation_input.get("detail_level"),
                output_format=estimation_input.get("output_format"),
            )

            elapsed_ms = (time.time() - start_time) * 1000

            # Step 5: Format response
            context_chunks_formatted = [
                {
                    "chunk_id": chunk["chunk_id"],
                    "rank": i + 1,
                    "distance": chunk["distance"],
                    "content": chunk["content"],
                    "chunk_type": chunk["chunk_type"],
                    "metadata": chunk["metadata"],
                }
                for i, chunk in enumerate(chunks)
            ]

            logger.info(
                "estimate_with_context_complete",
                query=query,
                chunks_retrieved=len(chunks),
                total_time_ms=elapsed_ms,
            )

            return {
                "estimation": estimation_output,
                "retrieval": {
                    "query": query,
                    "search_time_ms": retrieval_time_ms,
                    "chunks_retrieved": len(chunks),
                    "top_distance": chunks[0]["distance"] if chunks else None,
                },
                "context_chunks": context_chunks_formatted,
            }

        except Exception as e:
            logger.error(
                "estimate_with_context_failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    def _format_chunks_as_context(self, chunks: list[dict[str, Any]]) -> str:
        """Format retrieved chunks as readable context block for prompt injection."""
        lines = []
        for i, chunk in enumerate(chunks, 1):
            lines.append(f"**Budget {i}** (Similarity: {1 - chunk['distance']:.2%})")
            lines.append(f"- Component: {chunk['content'][:100]}...")
            lines.append(f"- Type: {chunk['chunk_type']}")

            metadata = chunk.get("metadata", {})
            if metadata.get("complexity"):
                lines.append(f"- Complexity: {metadata['complexity']}")
            if metadata.get("estimated_hours"):
                lines.append(f"- Estimated Hours: {metadata['estimated_hours']}")
            if metadata.get("technologies"):
                lines.append(f"- Technologies: {', '.join(metadata['technologies'])}")

            lines.append("")

        return "\n".join(lines)

    async def hybrid_search(
        self,
        query: str,
        k: int = 5,
        search_mode: str = "semantic",
        rrf_k: int = 60,
        enable_reranking: bool = False,
        reranker_k: int = 50,
    ) -> dict[str, Any]:
        """
        Hybrid search with optional reranking (recall-then-rerank pattern).

        Supports three search modes:
        - "semantic": Vector similarity (baseline)
        - "lexical": Full-text search (keyword matching)
        - "hybrid": Fused ranking via Reciprocal Rank Fusion (RRF)

        Recall-then-rerank pattern:
        1. Retrieve top-reranker_k documents (wide recall)
        2. If enable_reranking: Apply FlashRank cross-encoder to reorder to top-k
        3. Else: Return top-k from retrieval

        Args:
            query: Search query
            k: Final number of results to return
            search_mode: "semantic" | "lexical" | "hybrid"
            rrf_k: RRF smoothing constant (default 60)
            enable_reranking: Whether to apply cross-encoder reranking
            reranker_k: Number of documents to retrieve before reranking (default 50)

        Returns:
            {
                "query": str,
                "k": int,
                "search_mode": str,
                "enable_reranking": bool,
                "search_time_ms": float,
                "reranking_time_ms": float (0 if disabled),
                "results": [{ chunk_id, rank, score, reranker_score?, content, metadata }],
            }
        """
        start_time = time.time()

        try:
            # Step 1: Determine retrieval k (wider if reranking is enabled)
            retrieval_k = reranker_k if enable_reranking else k

            # Step 2: Perform retrieval
            if search_mode == "semantic":
                result = await self.search(query=query, k=retrieval_k)
                retrieved_results = result["results"]

            elif search_mode == "lexical":
                result = await self.search_fulltext(query=query, k=retrieval_k)
                retrieved_results = result["results"]

            elif search_mode == "hybrid":
                # Hybrid: retrieve top-2*k from each, fuse with RRF
                semantic_result = await self.search(query=query, k=min(retrieval_k * 2, 100))
                lexical_result = await self.search_fulltext(query=query, k=min(retrieval_k * 2, 100))

                retrieved_results = self._fuse_rankings_rrf(
                    semantic_results=semantic_result["results"],
                    lexical_results=lexical_result["results"],
                    k=retrieval_k,
                    rrf_k=rrf_k,
                )

            else:
                raise ValueError(f"Invalid search_mode: {search_mode}. Must be 'semantic', 'lexical', or 'hybrid'.")

            # Step 3: Optional reranking (fine-grained ordering)
            reranking_time_ms = 0.0
            if enable_reranking:
                # Resolve the cached reranker outside the timing window so the
                # one-time model load is not charged to reranking latency.
                reranker = get_reranker()

                reranking_start = time.time()
                final_results = await reranker.rerank(
                    query=query,
                    documents=retrieved_results,
                    k=k,
                )
                reranking_time_ms = (time.time() - reranking_start) * 1000
            else:
                final_results = retrieved_results[:k]

            total_time_ms = (time.time() - start_time) * 1000

            logger.info(
                "hybrid_search_complete",
                search_mode=search_mode,
                enable_reranking=enable_reranking,
                retrieved_count=len(retrieved_results),
                final_count=len(final_results),
                retrieval_time_ms=total_time_ms - reranking_time_ms,
                reranking_time_ms=reranking_time_ms,
                total_time_ms=total_time_ms,
            )

            return {
                "query": query,
                "k": k,
                "search_mode": search_mode,
                "enable_reranking": enable_reranking,
                "search_time_ms": round(total_time_ms - reranking_time_ms, 1),
                "reranking_time_ms": round(reranking_time_ms, 1),
                "results": final_results,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "hybrid_search_failed",
                search_mode=search_mode,
                enable_reranking=enable_reranking,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    def _fuse_rankings_rrf(
        self,
        semantic_results: list[dict[str, Any]],
        lexical_results: list[dict[str, Any]],
        k: int,
        rrf_k: int = 60,
    ) -> list[dict[str, Any]]:
        """
        Fuse two search rankings using Reciprocal Rank Fusion (RRF).

        RRF formula: score = Σ (1 / (rrf_k + rank_i))

        Returns merged, re-ranked results sorted by RRF score descending.
        """
        # Create rank maps: chunk_id → rank (1-indexed)
        semantic_ranks = {r["chunk_id"]: i + 1 for i, r in enumerate(semantic_results)}
        lexical_ranks = {r["chunk_id"]: i + 1 for i, r in enumerate(lexical_results)}

        # Get all unique chunk IDs
        all_chunk_ids = set(semantic_ranks.keys()) | set(lexical_ranks.keys())

        # Create lookup dicts for metadata
        semantic_lookup = {r["chunk_id"]: r for r in semantic_results}
        lexical_lookup = {r["chunk_id"]: r for r in lexical_results}

        # Calculate RRF scores
        rrf_scores = {}
        for chunk_id in all_chunk_ids:
            # Default to worst rank if not in one of the lists
            sem_rank = semantic_ranks.get(chunk_id, len(semantic_results) + 1)
            lex_rank = lexical_ranks.get(chunk_id, len(lexical_results) + 1)

            rrf_score = 1 / (rrf_k + sem_rank) + 1 / (rrf_k + lex_rank)
            rrf_scores[chunk_id] = {
                "chunk_id": chunk_id,
                "rrf_score": rrf_score,
                "semantic_rank": sem_rank if chunk_id in semantic_ranks else None,
                "lexical_rank": lex_rank if chunk_id in lexical_ranks else None,
            }

        # Sort by RRF score descending
        sorted_by_rrf = sorted(rrf_scores.values(), key=lambda x: x["rrf_score"], reverse=True)

        # Build final results (top-k), preferring semantic result for metadata if available
        fused_results = []
        for rank, item in enumerate(sorted_by_rrf[:k], 1):
            chunk_id = item["chunk_id"]

            # Get metadata from whichever result has it
            chunk_data = semantic_lookup.get(chunk_id) or lexical_lookup.get(chunk_id)

            fused_results.append({
                "chunk_id": chunk_id,
                "rank": rank,
                "rrf_score": item["rrf_score"],
                "semantic_rank": item["semantic_rank"],
                "lexical_rank": item["lexical_rank"],
                "content": chunk_data.get("content"),
                "chunk_type": chunk_data.get("chunk_type"),
                "metadata": chunk_data.get("metadata"),
            })

        return fused_results
