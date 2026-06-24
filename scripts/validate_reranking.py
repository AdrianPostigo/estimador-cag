#!/usr/bin/env python3
"""
Validate reranking (FlashRank) effectiveness.

Usage:
    docker compose run --rm ai_service python scripts/validate_reranking.py

Compares search results with and without reranking enabled, showing:
- How ranking changes with reranking
- FlashRank scores vs retrieval scores
- Impact on top-5 results
"""

import sys
import asyncio
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import AsyncSessionLocal


async def validate_reranking():
    """Validate reranking effectiveness across multiple queries."""

    from embedding_pipeline.persistence import DocumentRepository

    print("=" * 120)
    print("RERANKING VALIDATION: Recall-Then-Rerank Pattern (FlashRank)")
    print("=" * 120)

    async with AsyncSessionLocal() as session:
        repository = DocumentRepository(session)

        # Test queries
        queries = [
            {
                "text": "REST API authentication with OAuth tokens for fintech",
                "description": "Query with strong semantic + lexical signals",
            },
            {
                "text": "secure backend service with token-based access control",
                "description": "Query with strong semantic but weaker lexical signals",
            },
            {
                "text": "payment processing system with compliance requirements",
                "description": "Query with moderate semantic relevance",
            },
        ]

        for query_idx, query_spec in enumerate(queries, 1):
            print(f"\n{'=' * 120}")
            print(f"QUERY {query_idx}: {query_spec['text']}")
            print(f"Scenario: {query_spec['description']}")
            print(f"{'=' * 120}\n")

            try:
                # Run search WITHOUT reranking
                result_no_rerank = await repository.hybrid_search(
                    query=query_spec["text"],
                    k=5,
                    search_mode="hybrid",
                    enable_reranking=False,
                    reranker_k=50,
                )

                # Run search WITH reranking
                result_with_rerank = await repository.hybrid_search(
                    query=query_spec["text"],
                    k=5,
                    search_mode="hybrid",
                    enable_reranking=True,
                    reranker_k=50,
                )

                # Display results
                print(f"WITHOUT RERANKING (Top-5 from hybrid fusion)")
                print(f"Retrieval time: {result_no_rerank['search_time_ms']}ms | Results: {len(result_no_rerank['results'])}")
                print("-" * 120)
                for i, chunk in enumerate(result_no_rerank["results"], 1):
                    rrf_score = chunk.get("rrf_score", "N/A")
                    print(f"  [{i}] Chunk {chunk['chunk_id']} | RRF Score: {rrf_score:.6f}")
                    print(f"      {chunk['content'][:85]}...")
                    print()

                print(f"\nWITH RERANKING (Recall-then-rerank: retrieve 50, rerank to 5)")
                print(f"Retrieval time: {result_with_rerank['search_time_ms']}ms | Reranking time: {result_with_rerank['reranking_time_ms']}ms | Total: {result_with_rerank['search_time_ms'] + result_with_rerank['reranking_time_ms']}ms")
                print(f"Results: {len(result_with_rerank['results'])}")
                print("-" * 120)
                for i, chunk in enumerate(result_with_rerank["results"], 1):
                    reranker_score = chunk.get("reranker_score", "N/A")
                    print(f"  [{i}] Chunk {chunk['chunk_id']} | FlashRank Score: {reranker_score:.6f}")
                    print(f"      {chunk['content'][:85]}...")
                    print()

                # Analysis
                print(f"\nANALYSIS")
                print("-" * 120)

                no_rerank_ids = [r["chunk_id"] for r in result_no_rerank["results"]]
                with_rerank_ids = [r["chunk_id"] for r in result_with_rerank["results"]]

                # Check ranking changes
                moved_chunks = sum(1 for i, cid in enumerate(with_rerank_ids) if i < len(no_rerank_ids) and no_rerank_ids[i] != cid)
                stable_chunks = 5 - moved_chunks

                print(f"  Ranking stability: {stable_chunks}/5 chunks in same position")
                print(f"  Chunks reordered by reranker: {moved_chunks}/5")

                # Top-1 changes
                if no_rerank_ids[0] != with_rerank_ids[0]:
                    print(f"  Top-1 changed: {no_rerank_ids[0]} → {with_rerank_ids[0]}")
                else:
                    print(f"  Top-1 stable: {with_rerank_ids[0]}")

                # New in top-5 (not in original top-5)
                new_chunks = set(with_rerank_ids) - set(no_rerank_ids)
                if new_chunks:
                    print(f"  New chunks promoted to top-5: {new_chunks}")
                else:
                    print(f"  Top-5 identical (no promotion)")

                print(f"  Latency increase: {result_with_rerank['reranking_time_ms']:.1f}ms for reranking stage")

            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()

        print(f"\n{'=' * 120}")
        print("RERANKING VALIDATION COMPLETE")
        print(f"{'=' * 120}\n")


if __name__ == "__main__":
    try:
        asyncio.run(validate_reranking())
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
