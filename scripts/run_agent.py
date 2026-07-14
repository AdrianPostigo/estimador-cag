#!/usr/bin/env python3
"""
Run the estimation agent over a meeting transcript and print its trace.

Usage:
    docker compose run --rm ai_service python scripts/run_agent.py --transcript simple
    docker compose run --rm ai_service python scripts/run_agent.py --transcript complex
    docker compose run --rm ai_service python scripts/run_agent.py --file path/to/transcript.txt
"""

import sys
import argparse
import asyncio
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import AsyncSessionLocal

TRANSCRIPTS = {
    "simple": project_root / "data" / "transcripts" / "sample_transcript_simple.txt",
    "complex": project_root / "data" / "transcripts" / "sample_transcript_complex.txt",
}


async def run(transcript_path: Path) -> None:
    from app.generation.agentic.agent import EstimationAgent, format_trace
    from embedding_pipeline.persistence import DocumentRepository

    transcript = transcript_path.read_text(encoding="utf-8")

    print("=" * 100)
    print(f"ESTIMATION AGENT — {transcript_path.name}")
    print("=" * 100)

    async with AsyncSessionLocal() as session:
        repository = DocumentRepository(session)
        agent = EstimationAgent(repository)
        result = await agent.run(transcript)

    print("\n" + "=" * 100)
    print("REASONING TRACE")
    print("=" * 100 + "\n")
    print(format_trace(result))

    print("=" * 100)
    print("STRUCTURED ESTIMATE")
    print("=" * 100 + "\n")

    if result.estimate is None:
        print("The agent produced no calculation.")
    else:
        print(f"{'Component':<45} {'Refs':<6} {'Hours':<10} {'Unbudgeted'}")
        print("-" * 100)
        for component in result.estimate.components:
            print(
                f"{component.name[:44]:<45} "
                f"{component.reference_count:<6} "
                f"{component.estimated_hours:<10} "
                f"{'YES' if component.unbudgeted else ''}"
            )
        print("-" * 100)
        print(f"{'TOTAL':<45} {'':<6} {result.estimate.total_hours}")
        print(f"\nSummary:\n{result.estimate.summary}")

    print(f"\nIterations: {result.iterations} | Trace steps: {len(result.trace)}")
    print(f"Request id: {result.request_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the estimation agent on a transcript")
    parser.add_argument(
        "--transcript",
        choices=sorted(TRANSCRIPTS),
        default="simple",
        help="Which sample transcript to use",
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
