#!/usr/bin/env python3
"""
Explore chunks in database and test golden queries.

Usage:
    docker compose run --rm ai_service python scripts/explore_chunks.py

This script:
1. Lists all chunks in the database
2. For each golden query, retrieves top-50 results
3. Prints formatted output for manual annotation

User then:
- Reviews top-50 per query
- Manually annotates which chunk_ids are actually relevant
- Updates evals/golden_set_session_10.json with real chunk IDs
"""

import sys
import asyncio
import json
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import AsyncSessionLocal


async def explore_chunks():
    """Explore chunks and retrieve top-50 for each golden query."""

    from embedding_pipeline.persistence import DocumentRepository
    from sqlalchemy import select
    from embedding_pipeline.models import Chunk

    print("=" * 120)
    print("CHUNK EXPLORATION & GOLDEN QUERY TEST")
    print("=" * 120)

    async with AsyncSessionLocal() as session:
        repository = DocumentRepository(session)

        # Step 1: List all chunks
        print("\n[STEP 1] LISTING ALL CHUNKS IN DATABASE\n")
        print("-" * 120)

        stmt = select(Chunk).order_by(Chunk.id)
        result = await session.execute(stmt)
        all_chunks = result.scalars().all()

        print(f"Total chunks in database: {len(all_chunks)}\n")

        for chunk in all_chunks:
            print(f"Chunk ID: {chunk.id}")
            print(f"  Document ID: {chunk.document_id}")
            print(f"  Type: {chunk.chunk_type}")
            print(f"  Content: {chunk.content[:100]}...")
            print(f"  Metadata: {chunk.chunk_metadata}")
            print()

        # Step 2: Test golden queries
        print("\n" + "=" * 120)
        print("[STEP 2] TESTING GOLDEN QUERIES (TOP-50 FOR ANNOTATION)")
        print("=" * 120)

        golden_queries = [
            {
                "id": "Q1",
                "text": "REST API with OAuth 2.0 authentication for fintech mobile application",
                "domain": "Fintech / Banking",
                "description": "Backend authentication system using OAuth 2.0 and JWT tokens",
            },
            {
                "id": "Q2",
                "text": "E-commerce platform with payment processing and inventory management",
                "domain": "E-commerce / Retail",
                "description": "Shopping platform with shopping cart, payments, and stock tracking",
            },
            {
                "id": "Q3",
                "text": "Data warehouse with ETL pipeline and real-time analytics",
                "domain": "Data / Analytics",
                "description": "Data infrastructure for ingestion, transformation, and analytics queries",
            },
            {
                "id": "Q4",
                "text": "Machine learning model deployment with monitoring and retraining",
                "domain": "ML / AI",
                "description": "ML operations platform for serving models and continuous retraining",
            },
            {
                "id": "Q5",
                "text": "Internal tool for team collaboration with real-time sync",
                "domain": "Internal Tools / Productivity",
                "description": "Simple internal application for team communication and task management",
            },
        ]

        all_results = {}

        for query_spec in golden_queries:
            query_id = query_spec["id"]
            query_text = query_spec["text"]

            print(f"\n{'=' * 120}")
            print(f"QUERY {query_id}: {query_text}")
            print(f"Domain: {query_spec['domain']}")
            print(f"Description: {query_spec['description']}")
            print(f"{'=' * 120}\n")

            try:
                # Retrieve top-50 using hybrid search
                result = await repository.hybrid_search(
                    query=query_text,
                    k=50,
                    search_mode="hybrid",
                    enable_reranking=False,
                )

                results_for_query = []

                # Print results for annotation
                print(f"TOP-50 RESULTS (ordered by RRF score)")
                print("-" * 120)
                print(f"{'Rank':<6} {'Chunk ID':<12} {'Type':<15} {'Content Preview':<75}")
                print("-" * 120)

                for i, chunk in enumerate(result["results"], 1):
                    chunk_id = chunk["chunk_id"]
                    chunk_type = chunk.get("chunk_type", "N/A")
                    content_preview = chunk["content"][:70].replace("\n", " ")

                    print(f"{i:<6} {chunk_id:<12} {chunk_type:<15} {content_preview}...")

                    results_for_query.append({
                        "rank": i,
                        "chunk_id": chunk_id,
                        "chunk_type": chunk_type,
                        "content": chunk["content"],
                        "rrf_score": chunk.get("rrf_score"),
                        "metadata": chunk.get("metadata"),
                    })

                all_results[query_id] = {
                    "query_text": query_text,
                    "domain": query_spec["domain"],
                    "results": results_for_query,
                }

            except Exception as e:
                print(f"Error retrieving results: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()

        # Step 3: Generate annotation template
        print("\n" + "=" * 120)
        print("[STEP 3] ANNOTATION TEMPLATE")
        print("=" * 120)
        print("\nFor each query above, manually identify which chunk IDs are ACTUALLY RELEVANT.")
        print("Example annotation (add to evals/golden_set_session_10.json):\n")

        annotation_template = {
            "description": "Golden set for evaluating hybrid search + reranking (Session 10)",
            "instructions": "For each query, identify which chunks are truly relevant to the query intent",
            "queries": [],
        }

        for query_id in sorted(all_results.keys()):
            query_data = all_results[query_id]
            annotation_template["queries"].append({
                "id": query_id,
                "text": query_data["query_text"],
                "domain": query_data["domain"],
                "relevant_chunk_ids": "# TODO: Annotate manually based on top-50 results above",
                "comment": "# TODO: Add reasoning",
            })

        print(json.dumps(annotation_template, indent=2, ensure_ascii=False))

        print("\n" + "=" * 120)
        print("INSTRUCTIONS FOR NEXT STEP:")
        print("=" * 120)
        print("""
1. Review the top-50 results printed above for each query
2. For each query, identify which chunks are ACTUALLY RELEVANT (not just similar)
3. Update evals/golden_set_session_10.json with the relevant chunk IDs
4. Run scripts/evaluate_search_configs.py to measure search quality

Example annotation:
  "Q1": {
    "relevant_chunk_ids": [1, 5, 12, 28],
    "comment": "Chunks 1,5 are OAuth/auth components; 12,28 are fintech-specific"
  }
""")

        print("=" * 120)


if __name__ == "__main__":
    try:
        asyncio.run(explore_chunks())
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
