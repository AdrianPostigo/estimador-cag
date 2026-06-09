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
                metadata={
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
                    metadata={
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
                    Chunk.metadata,
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
                    "metadata": row.metadata,
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
