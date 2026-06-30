"""OpenAI embedding service."""

import time

import structlog
from openai import OpenAI, RateLimitError

from embedding_pipeline.schemas import Chunk, EmbeddedChunk

# Pricing constant: $0.02 per million input tokens (text-embedding-3-small)
EMBEDDING_PRICE_PER_MTK = 0.02

# Batch size for API calls
BATCH_SIZE = 100

# Retry configuration for RateLimitError
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # seconds

logger = structlog.get_logger()


class OpenAIEmbedder:
    """Embeds text chunks using OpenAI's text-embedding-3-small model."""

    def __init__(self, model: str = "text-embedding-3-small"):
        """
        Initialize embedder with OpenAI client.

        Args:
            model: OpenAI embedding model name.
                   Defaults to "text-embedding-3-small" (1536 dimensions).
        """
        self.model = model
        self.client = OpenAI()  # Reads OPENAI_API_KEY from environment

    def embed_one(self, text: str) -> list[float]:
        """
        Embed a single text string.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector (list of floats, dimension 1536).

        Raises:
            OpenAI API exceptions.
        """
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    def embed_many(
        self, chunks: list[Chunk]
    ) -> tuple[list[EmbeddedChunk], dict[str, int | float]]:
        """
        Embed multiple chunks in batches with retry logic.

        Processes chunks in batches of 100 to avoid serialized API calls.
        Retries on RateLimitError with exponential backoff (1s, 2s, 4s).

        Args:
            chunks: List of Chunk objects to embed.

        Returns:
            Tuple of:
            - List of EmbeddedChunk objects with embeddings attached
            - Stats dict with keys: total_chunks, total_tokens, estimated_cost_usd

        Raises:
            OpenAI exceptions (except RateLimitError which is retried).
        """
        embedded_chunks = []
        total_tokens = 0

        # Process in batches
        for batch_start in range(0, len(chunks), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(chunks))
            batch = chunks[batch_start:batch_end]

            # Extract texts for embedding
            texts = [chunk.text for chunk in batch]

            # Call API with retry logic
            start_time = time.time()
            embeddings = self._embed_texts_with_retry(texts)
            latency_ms = (time.time() - start_time) * 1000

            # Count tokens for cost calculation
            batch_tokens = sum(chunk.token_count for chunk in batch)
            total_tokens += batch_tokens

            # Create EmbeddedChunk objects
            for chunk, embedding in zip(batch, embeddings):
                embedded_chunk = EmbeddedChunk(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    metadata=chunk.metadata,
                    token_count=chunk.token_count,
                    embedding=embedding,
                )
                embedded_chunks.append(embedded_chunk)

            # Log batch completion
            logger.info(
                "embedding_batch_complete",
                batch_number=batch_start // BATCH_SIZE + 1,
                batch_size=len(batch),
                batch_tokens=batch_tokens,
                batch_latency_ms=latency_ms,
                model=self.model,
            )

        # Calculate estimated cost
        estimated_cost_usd = (total_tokens / 1_000_000) * EMBEDDING_PRICE_PER_MTK

        # Build stats
        stats = {
            "total_chunks": len(chunks),
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
        }

        logger.info(
            "embedding_complete",
            total_chunks=len(chunks),
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )

        return embedded_chunks, stats

    def _embed_texts_with_retry(self, texts: list[str]) -> list[list[float]]:
        """
        Call OpenAI embeddings API with retry logic for RateLimitError.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each vector is list[float]).

        Raises:
            RateLimitError if max retries exceeded; other OpenAI exceptions propagate.
        """
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=texts,
                )
                return [item.embedding for item in response.data]
            except RateLimitError as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        "rate_limit_error_retry",
                        attempt=attempt + 1,
                        max_retries=MAX_RETRIES,
                        delay_seconds=delay,
                        error_message=str(e),
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "rate_limit_max_retries_exceeded",
                        attempts=MAX_RETRIES,
                        error_message=str(e),
                    )
                    raise
