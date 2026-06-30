"""Compare similarity between two texts using embeddings."""

import math
import sys
from pathlib import Path

import click

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from embedding_pipeline.embedder import OpenAIEmbedder


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Formula: similarity = (a · b) / (||a|| * ||b||)

    Args:
        vec_a: First embedding vector
        vec_b: Second embedding vector

    Returns:
        Cosine similarity score (float between -1.0 and 1.0, typically 0.0 to 1.0)
    """
    # Dot product (scalar product)
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))

    # Norms (magnitudes) using L2 norm
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    # Avoid division by zero
    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


@click.command()
@click.option(
    "--text-a",
    required=True,
    help="First text to embed and compare",
)
@click.option(
    "--text-b",
    required=True,
    help="Second text to embed and compare",
)
def compare(text_a: str, text_b: str) -> None:
    """
    Compare cosine similarity between two texts.

    Embeds both texts using OpenAI's text-embedding-3-small model
    and calculates cosine similarity (product of norms approach).

    Examples:

        python scripts/compare.py \
          --text-a "OAuth 2.0 authentication backend for fintech" \
          --text-b "JWT-based authorization service for banking app"

        # Inside container:
        docker compose exec servicio_ia python scripts/compare.py \
          --text-a "..." --text-b "..."

        # Outside container (with uv):
        uv run python scripts/compare.py --text-a "..." --text-b "..."

    Requirements:
        - OPENAI_API_KEY environment variable set
        - text-embedding-3-small model available in OpenAI account

    Exit codes:
        0: Success
        1: Error (missing API key, API failure, invalid inputs)
    """
    try:
        embedder = OpenAIEmbedder()

        # Embed both texts
        click.echo("Embedding texts...", err=True)
        embedding_a = embedder.embed_one(text_a)
        embedding_b = embedder.embed_one(text_b)

        # Calculate cosine similarity
        similarity = cosine_similarity(embedding_a, embedding_b)

        # Output results
        click.echo("")
        click.echo(f"Text A: {text_a}")
        click.echo(f"Text B: {text_b}")
        click.echo(f"Cosine similarity: {similarity:.4f}")
        click.echo("")

    except KeyError as e:
        click.echo(f"Error: Missing environment variable {e}", err=True)
        click.echo("Set OPENAI_API_KEY before running this script", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    compare()
