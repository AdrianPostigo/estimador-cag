#!/usr/bin/env python3
"""
Test semantic search endpoint with representative queries.

Exercises the dataset from different angles:
1. Direct match (known component) — expect near-perfect match
2. Semantic reformulation — same idea, different vocabulary
3. Out-of-domain query — expect high distances or irrelevant results
4. Ambiguous query — short, generic, many partial matches
5. Very specific query — technical vocabulary, distinguish related tech

Usage:
    python scripts/query_examples.py [--backend-url http://localhost:8000]
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

import click
import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

DEFAULT_BACKEND_URL = "http://localhost:8000/api/v1"


# Representative queries
QUERIES = [
    {
        "name": "Direct Match (Sanity Check)",
        "query": "REST API development with JWT authentication for financial sector",
        "description": "Should have near-perfect match against budget components",
    },
    {
        "name": "Semantic Reformulation",
        "query": "secure backend service with token-based access control for banking applications",
        "description": "Same concept, different vocabulary. Tests semantic understanding.",
    },
    {
        "name": "Out-of-Domain Query",
        "query": "mobile application for restaurant reservations",
        "description": "Should have high distances or irrelevant results (not in corpus).",
    },
    {
        "name": "Ambiguous Query",
        "query": "integration with external system",
        "description": "Short, generic. Many chunks could partially match. Tests ranking.",
    },
    {
        "name": "Very Specific Query",
        "query": "migration from monolith to microservices architecture using Kubernetes",
        "description": "Technical vocabulary. Distinguish between related technologies.",
    },
]


async def run_search(
    client: httpx.AsyncClient,
    backend_url: str,
    query: str,
    k: int = 5,
) -> dict[str, Any]:
    """Execute semantic search query."""
    response = await client.post(
        f"{backend_url}/embeddings/search",
        json={"query": query, "k": k},
    )
    response.raise_for_status()
    return response.json()


def format_results(result: dict[str, Any]) -> str:
    """Format search results for terminal display."""
    lines = []

    # Header
    lines.append(f"Query: {result['query']}")
    lines.append(f"Results: {len(result['results'])} chunks | Time: {result['search_time_ms']:.1f}ms")
    lines.append("-" * 100)

    # Results table
    for i, chunk in enumerate(result["results"], 1):
        distance = chunk["distance"]
        chunk_id = chunk["chunk_id"]
        chunk_type = chunk["chunk_type"]
        content_preview = chunk["content"][:120].replace("\n", " ") + ("..." if len(chunk["content"]) > 120 else "")

        lines.append(f"[{i}] ID={chunk_id:4d} | Distance={distance:.4f} | Type={chunk_type:15s}")
        lines.append(f"    {content_preview}")
        lines.append("")

    return "\n".join(lines)


@click.command()
@click.option(
    "--backend-url",
    default=DEFAULT_BACKEND_URL,
    help="Backend API base URL",
)
@click.option(
    "--k",
    type=int,
    default=5,
    help="Number of results per query",
)
async def run_examples(backend_url: str, k: int) -> None:
    """Run example semantic search queries against the backend."""

    click.echo("=" * 100)
    click.echo("SEMANTIC SEARCH EXAMPLES")
    click.echo("=" * 100)
    click.echo("")

    async with httpx.AsyncClient(timeout=30.0) as client:
        for query_config in QUERIES:
            click.echo(f"QUERY: {query_config['name']}")
            click.echo(f"Description: {query_config['description']}")
            click.echo("")

            try:
                result = await run_search(
                    client,
                    backend_url,
                    query_config["query"],
                    k=k,
                )
                click.echo(format_results(result))

            except Exception as e:
                click.echo(f"ERROR: {e}", err=True)
                click.echo("")

            click.echo("")


if __name__ == "__main__":
    asyncio.run(run_examples())
