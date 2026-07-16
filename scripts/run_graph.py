#!/usr/bin/env python3
"""
Run the estimation graph over a sample transcript and print the final state.

Uses the project's PostgreSQL as the graph checkpointer (thread_id = estimation
id) and Logfire for the per-node trace. Without a LOGFIRE_TOKEN the spans are
printed to the console; set the token to also ship them to the dashboard.

Usage:
    docker compose run --rm ai_service python scripts/run_graph.py --transcript simple
    docker compose run --rm ai_service python scripts/run_graph.py --transcript complex
"""

import sys
import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import AsyncSessionLocal

TRANSCRIPTS = {
    "simple": project_root / "data" / "transcripts" / "sample_transcript_simple.txt",
    "complex": project_root / "data" / "transcripts" / "sample_transcript_complex.txt",
}


async def run(transcript_path: Path) -> None:
    import logfire
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from embedding_pipeline.persistence import DocumentRepository
    from graph.build import build_graph
    from graph.checkpointer import checkpointer_conn_string
    from graph.observability import configure_logfire

    configure_logfire()

    transcript = transcript_path.read_text(encoding="utf-8")
    estimation_id = str(uuid4())

    print("=" * 100)
    print(f"ESTIMATION GRAPH — {transcript_path.name}")
    print("=" * 100)

    async with AsyncPostgresSaver.from_conn_string(checkpointer_conn_string()) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(checkpointer)

        async with AsyncSessionLocal() as session:
            repository = DocumentRepository(session)
            config = {
                "configurable": {
                    "thread_id": estimation_id,
                    "repository": repository,
                }
            }
            with logfire.span("estimation run {thread_id}", thread_id=estimation_id):
                result = await graph.ainvoke(
                    {"transcript": transcript, "budget_matches": [], "errors": []},
                    config,
                )

    print("\nREQUIREMENTS")
    print("-" * 100)
    for requirement in result.get("requirements", []):
        print(f"  - {requirement}")

    print("\nCOMPONENTS")
    print("-" * 100)
    for component in result.get("components", []):
        print(f"  - {component['name']} [{component['category']}]")

    print("\nBUDGET MATCHES (accumulator)")
    print("-" * 100)
    for match in result.get("budget_matches", []):
        print(f"  - {match['component']}: {match['amount']}h (budget {match['reference_budget_id']})")

    print("\nESTIMATE")
    print("-" * 100)
    estimate = result.get("estimate")
    if estimate:
        print(json.dumps(estimate, indent=2, ensure_ascii=False))
    else:
        print("  (none)")

    print("\nSTATUS")
    print("-" * 100)
    print(f"  status: {result.get('status')}")
    print(f"  errors: {result.get('errors')}")
    print(f"\nthread_id / estimation_id: {estimation_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the estimation graph on a transcript")
    parser.add_argument(
        "--transcript",
        choices=sorted(TRANSCRIPTS),
        default="complex",
    )
    parser.add_argument("--file", help="Path to a custom transcript file")
    args = parser.parse_args()

    path = Path(args.file) if args.file else TRANSCRIPTS[args.transcript]
    if not path.exists():
        print(f"Transcript not found: {path}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(run(path))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
