"""Cross-encoder reranking using FlashRank."""

import time
from typing import Any

import structlog
from flashrank import Ranker, RerankRequest

logger = structlog.get_logger()


class FlashRankReranker:
    """
    Lightweight, optimized reranker for ranking search results.

    Uses FlashRank (MS MARCO trained) for fine-grained relevance scoring.
    Designed for the recall-then-rerank pattern: retrieve wide, rerank tight.
    """

    def __init__(self, model_name: str = "ms-marco-MiniLM-L-12-v2"):
        """
        Initialize FlashRank reranker.

        Args:
            model_name: HuggingFace model identifier. Options:
                - "ms-marco-MiniLM-L-12-v2" (recommended, balanced)
                - "ms-marco-TinyBERT-L-2-v2" (faster, lighter)
                - "ms-marco-MultiBERT-L-12" (multilingual)
        """
        try:
            self.ranker = Ranker(model_name=model_name, cache_dir="./models")
            self.model_name = model_name
            logger.info(
                "flash_rank_initialized",
                model_name=model_name,
            )
        except Exception as e:
            logger.error(
                "flash_rank_init_failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Rerank documents by relevance to query using FlashRank cross-encoder.

        Recall-then-rerank pattern: takes retrieved documents (already filtered),
        applies fine-grained cross-encoder scoring, returns top-k.

        Args:
            query: Search query
            documents: List of retrieved documents from retriever
            k: Number of top documents to return after reranking

        Returns:
            Reranked documents (top-k) with reranker_score attached
        """
        if not documents:
            return []

        try:
            # Build passages for FlashRank. We track each passage by its index
            # into `documents` so we can map scored results back to originals.
            passages = [
                {"id": idx, "text": doc.get("content", "")}
                for idx, doc in enumerate(documents)
            ]

            logger.info(
                "reranking_started",
                query_length=len(query),
                num_documents=len(documents),
                target_k=k,
            )

            # FlashRank API: rerank(RerankRequest(query, passages)) -> list of
            # passage dicts with an added "score", sorted by score descending.
            rerank_request = RerankRequest(query=query, passages=passages)
            ranked_results = self.ranker.rerank(rerank_request)

            # Map ranked results back to original documents with scores
            reranked_documents = []
            for ranked_item in ranked_results[:k]:
                doc_idx = ranked_item["id"]
                original_doc = documents[doc_idx].copy()
                original_doc["reranker_score"] = float(ranked_item["score"])
                reranked_documents.append(original_doc)

            logger.info(
                "reranking_complete",
                query_length=len(query),
                documents_reranked=len(documents),
                results_returned=len(reranked_documents),
            )

            return reranked_documents

        except Exception as e:
            logger.error(
                "reranking_failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise


# Module-level singleton: load the model once and reuse it across calls so the
# one-time model load cost is not charged to per-query reranking latency.
_reranker_instance: FlashRankReranker | None = None


def get_reranker(model_name: str = "ms-marco-MiniLM-L-12-v2") -> FlashRankReranker:
    """Return a cached FlashRankReranker, creating it on first use."""
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = FlashRankReranker(model_name)
    return _reranker_instance
