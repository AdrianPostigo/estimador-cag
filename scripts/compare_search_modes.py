#!/usr/bin/env python3
"""
Compare search modes: semantic, lexical, and hybrid (RRF).

Usage:
    docker compose run --rm ai_service python scripts/compare_search_modes.py

This script compares results across three search modes for the same query,
demonstrating how RRF fusion improves recall over pure semantic or lexical search.
"""

import sys
import asyncio
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import AsyncSessionLocal


async def compare_search_modes():
    """Execute search in three modes and compare results."""

    from embedding_pipeline.persistence import DocumentRepository

    print("=" * 100)
    print("HYBRID SEARCH COMPARISON: Semantic vs Lexical vs RRF Fusion")
    print("=" * 100)

    async with AsyncSessionLocal() as session:
        repository = DocumentRepository(session)

        # Example queries demonstrating different search characteristics
        queries = [
            {
                "text": "REST API authentication with OAuth tokens",
                "description": "Direct keyword match + semantic similarity",
            },
            {
                "text": "secure backend service for financial applications",
                "description": "Semantic reformulation (OAuth not mentioned but similar concept)",
            },
            {
                "text": "micro-payment processing system",
                "description": "Moderate semantic match (fintech domain) + lexical mismatch",
            },
        ]

        for query_idx, query_spec in enumerate(queries, 1):
            print(f"\n{'=' * 100}")
            print(f"QUERY {query_idx}: {query_spec['text']}")
            print(f"Scenario: {query_spec['description']}")
            print(f"{'=' * 100}\n")

            try:
                # Run all three modes
                semantic_result = await repository.hybrid_search(
                    query=query_spec["text"],
                    k=5,
                    search_mode="semantic",
                )

                lexical_result = await repository.hybrid_search(
                    query=query_spec["text"],
                    k=5,
                    search_mode="lexical",
                )

                hybrid_result = await repository.hybrid_search(
                    query=query_spec["text"],
                    k=5,
                    search_mode="hybrid",
                )

                # Display results side-by-side
                print(f"SEMANTIC SEARCH (Pure Vector Similarity)")
                print(f"Time: {semantic_result['search_time_ms']}ms | Results: {len(semantic_result['results'])}")
                print("-" * 100)
                for i, chunk in enumerate(semantic_result["results"], 1):
                    print(f"  [{i}] Chunk {chunk['chunk_id']} | Type: {chunk['chunk_type']} | Distance: {chunk.get('distance', 'N/A'):.4f}")
                    print(f"      {chunk['content'][:80]}...")
                    print()

                print(f"\nLEXICAL SEARCH (Full-Text via tsvector)")
                print(f"Time: {lexical_result['search_time_ms']}ms | Results: {len(lexical_result['results'])}")
                print("-" * 100)
                for i, chunk in enumerate(lexical_result["results"], 1):
                    rank_score = chunk.get('rank', 'N/A')
                    print(f"  [{i}] Chunk {chunk['chunk_id']} | Type: {chunk['chunk_type']} | Rank Score: {rank_score}")
                    print(f"      {chunk['content'][:80]}...")
                    print()

                print(f"\nHYBRID SEARCH (RRF Fusion)")
                print(f"Time: {hybrid_result['search_time_ms']}ms | Results: {len(hybrid_result['results'])}")
                print("-" * 100)
                for i, chunk in enumerate(hybrid_result["results"], 1):
                    rrf_score = chunk.get('rrf_score', 'N/A')
                    sem_rank = chunk.get('semantic_rank')
                    lex_rank = chunk.get('lexical_rank')
                    print(f"  [{i}] Chunk {chunk['chunk_id']} | Type: {chunk['chunk_type']} | RRF Score: {rrf_score:.6f}")
                    print(f"      Ranks: Semantic={sem_rank}, Lexical={lex_rank}")
                    print(f"      {chunk['content'][:80]}...")
                    print()

                # Analysis
                print(f"\nANALYSIS")
                print("-" * 100)

                semantic_ids = {r['chunk_id'] for r in semantic_result['results']}
                lexical_ids = {r['chunk_id'] for r in lexical_result['results']}
                hybrid_ids = {r['chunk_id'] for r in hybrid_result['results']}

                semantic_only = semantic_ids - lexical_ids
                lexical_only = lexical_ids - semantic_ids
                both = semantic_ids & lexical_ids
                hybrid_unique = hybrid_ids - (semantic_ids | lexical_ids)

                print(f"  Semantic only (not in lexical): {len(semantic_only)} chunks: {semantic_only}")
                print(f"  Lexical only (not in semantic): {len(lexical_only)} chunks: {lexical_only}")
                print(f"  In both rankings: {len(both)} chunks: {both}")
                print(f"  Hybrid unique (RRF fusion effect): {len(hybrid_unique)} chunks: {hybrid_unique}")

            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()

        print(f"\n{'=' * 100}")
        print("COMPARISON COMPLETE")
        print(f"{'=' * 100}\n")


if __name__ == "__main__":
    try:
        asyncio.run(compare_search_modes())
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
