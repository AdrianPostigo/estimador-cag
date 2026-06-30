#!/usr/bin/env python3
"""
Evaluate search configurations using golden set.

Usage:
    docker compose run --rm ai_service python scripts/evaluate_search_configs.py

Runs 4 search configurations against the golden set:
- A: Semantic, no reranking
- B: Hybrid, no reranking
- C: Semantic, with reranking
- D: Hybrid, with reranking

Metrics per config:
- Precision@5 (P@5)
- Latency (ms)

Output: Table + CSV + detailed JSON report
"""

import sys
import asyncio
import json
import csv
from pathlib import Path
from statistics import mean

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import AsyncSessionLocal


async def evaluate_search_configs():
    """Evaluate 4 search configurations against golden set."""

    from embedding_pipeline.persistence import DocumentRepository

    print("=" * 140)
    print("SEARCH CONFIGURATION EVALUATION")
    print("Golden Set: 5 queries × 4 configurations × 2 metrics (Precision@5 + Latency)")
    print("=" * 140)

    # Step 1: Load golden set
    print("\n[STEP 1] LOADING GOLDEN SET")
    print("-" * 140)

    golden_set_path = project_root / "evals" / "golden_set_session_10.json"

    try:
        with open(golden_set_path) as f:
            golden_set = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Golden set not found at {golden_set_path}", file=sys.stderr)
        print("Run scripts/explore_chunks.py first to create and annotate the golden set", file=sys.stderr)
        sys.exit(1)

    # Validate that queries are annotated
    unannotated = [
        q for q in golden_set["queries"]
        if not q.get("relevant_chunk_ids") or len(q.get("relevant_chunk_ids", [])) == 0
    ]

    if unannotated:
        print(f"ERROR: {len(unannotated)} queries are not annotated:", file=sys.stderr)
        for q in unannotated:
            print(f"  - {q['id']}: {q['text'][:60]}...", file=sys.stderr)
        print("\nRun scripts/explore_chunks.py to annotate, then re-run this script", file=sys.stderr)
        sys.exit(1)

    print(f"✓ Loaded {len(golden_set['queries'])} annotated queries")
    for q in golden_set["queries"]:
        print(f"  {q['id']}: {len(q['relevant_chunk_ids'])} relevant chunks")

    # Step 2: Define configurations
    print("\n[STEP 2] DEFINING SEARCH CONFIGURATIONS")
    print("-" * 140)

    configs = [
        {
            "name": "A",
            "label": "Semantic (no reranking)",
            "search_mode": "semantic",
            "enable_reranking": False,
        },
        {
            "name": "B",
            "label": "Hybrid (no reranking)",
            "search_mode": "hybrid",
            "enable_reranking": False,
        },
        {
            "name": "C",
            "label": "Semantic (with reranking)",
            "search_mode": "semantic",
            "enable_reranking": True,
        },
        {
            "name": "D",
            "label": "Hybrid (with reranking)",
            "search_mode": "hybrid",
            "enable_reranking": True,
        },
    ]

    for config in configs:
        print(f"  {config['name']}: {config['label']}")

    # Step 3: Run evaluations
    print("\n[STEP 3] RUNNING EVALUATIONS")
    print("-" * 140)

    all_results = []
    detailed_results = {}

    async with AsyncSessionLocal() as session:
        repository = DocumentRepository(session)

        for config in configs:
            print(f"\nEvaluating Configuration {config['name']}: {config['label']}")
            print(f"  Mode: {config['search_mode']}, Reranking: {config['enable_reranking']}")

            config_results = {
                "config_name": config["name"],
                "config_label": config["label"],
                "search_mode": config["search_mode"],
                "enable_reranking": config["enable_reranking"],
                "query_results": [],
            }

            for query in golden_set["queries"]:
                query_id = query["id"]
                query_text = query["text"]
                relevant_ids = set(query["relevant_chunk_ids"])

                try:
                    # Execute search
                    result = await repository.hybrid_search(
                        query=query_text,
                        k=5,
                        search_mode=config["search_mode"],
                        enable_reranking=config["enable_reranking"],
                        reranker_k=50,
                    )

                    # Get top-5 chunk IDs
                    top_5_ids = [chunk["chunk_id"] for chunk in result["results"]]

                    # Calculate Precision@5
                    # P@5 = (relevant chunks found in top-5) / min(5, total relevant chunks)
                    found_relevant = len(set(top_5_ids) & relevant_ids)
                    total_relevant = len(relevant_ids)
                    precision_at_5 = found_relevant / min(5, max(total_relevant, 1))

                    # Latency
                    latency_ms = result["search_time_ms"] + result.get("reranking_time_ms", 0.0)

                    query_result = {
                        "query_id": query_id,
                        "query_text": query_text[:60] + "..." if len(query_text) > 60 else query_text,
                        "relevant_count": total_relevant,
                        "found_relevant": found_relevant,
                        "precision_at_5": round(precision_at_5, 4),
                        "latency_ms": round(latency_ms, 1),
                        "top_5_ids": top_5_ids,
                    }

                    config_results["query_results"].append(query_result)

                    print(
                        f"    {query_id}: P@5={precision_at_5:.2%} "
                        f"({found_relevant}/{min(5, total_relevant)}), "
                        f"Latency={latency_ms:.1f}ms"
                    )

                except Exception as e:
                    print(f"    {query_id}: ERROR - {e}", file=sys.stderr)

            # Calculate aggregate metrics
            if config_results["query_results"]:
                avg_precision = mean([q["precision_at_5"] for q in config_results["query_results"]])
                avg_latency = mean([q["latency_ms"] for q in config_results["query_results"]])

                config_results["avg_precision_at_5"] = round(avg_precision, 4)
                config_results["avg_latency_ms"] = round(avg_latency, 1)

                all_results.append({
                    "Config": config["name"],
                    "Label": config["label"],
                    "Avg P@5": f"{avg_precision:.2%}",
                    "Avg Latency (ms)": f"{avg_latency:.1f}",
                })

            detailed_results[config["name"]] = config_results

    # Step 4: Print results table
    print("\n" + "=" * 140)
    print("[STEP 4] RESULTS SUMMARY")
    print("=" * 140)

    print("\n" + "COMPARATIVE TABLE".center(140))
    print("-" * 140)

    # Print table header
    header = f"{'Config':<6} {'Label':<35} {'Avg P@5':<15} {'Avg Latency (ms)':<20}"
    print(header)
    print("-" * 140)

    # Print rows
    for result in all_results:
        row = (
            f"{result['Config']:<6} "
            f"{result['Label']:<35} "
            f"{result['Avg P@5']:<15} "
            f"{result['Avg Latency (ms)']:<20}"
        )
        print(row)

    print("-" * 140)

    # Step 5: Detailed breakdown by query
    print("\n\nDETAILED BREAKDOWN BY QUERY".center(140))
    print("-" * 140)

    for query in golden_set["queries"]:
        query_id = query["id"]
        query_text = query["text"][:70] + "..." if len(query["text"]) > 70 else query["text"]

        print(f"\n{query_id}: {query_text}")
        print(f"  Relevant chunks: {len(query['relevant_chunk_ids'])}")
        print()

        breakdown_header = f"{'Config':<10} {'P@5':<12} {'Found':<10} {'Latency (ms)':<15}"
        print(breakdown_header)
        print("-" * 50)

        for config in configs:
            config_name = config["name"]
            config_data = detailed_results[config_name]

            query_data = next(
                (qr for qr in config_data["query_results"] if qr["query_id"] == query_id),
                None
            )

            if query_data:
                precision_pct = f"{query_data['precision_at_5']:.2%}"
                found_str = f"{query_data['found_relevant']}/{query_data['relevant_count']}"
                latency_str = f"{query_data['latency_ms']:.1f}"

                row = f"{config_name:<10} {precision_pct:<12} {found_str:<10} {latency_str:<15}"
                print(row)

    # Step 6: Save results to CSV
    print("\n" + "=" * 140)
    print("[STEP 5] SAVING RESULTS")
    print("=" * 140)

    csv_path = project_root / "evals" / "search_evaluation_session_10.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Config", "Label", "Avg P@5", "Avg Latency (ms)"])
        writer.writeheader()
        writer.writerows(all_results)

    print(f"✓ Results saved to {csv_path}")

    # Step 7: Save detailed JSON report
    json_path = project_root / "evals" / "search_evaluation_session_10.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(detailed_results, f, indent=2, ensure_ascii=False)

    print(f"✓ Detailed results saved to {json_path}")

    print("\n" + "=" * 140)
    print("EVALUATION COMPLETE")
    print("=" * 140)


if __name__ == "__main__":
    try:
        asyncio.run(evaluate_search_configs())
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
