#!/usr/bin/env python3
"""
Bulk-ingest the budget dataset into PostgreSQL.

Usage:
    docker compose run --rm ai_service python scripts/ingest_budgets.py

Loads data/budgets_sample.json, normalizes client metadata to the canonical
Budget schema (some records use a legacy {name, industry} shape), and ingests
each budget through DocumentRepository so chunks + embeddings are persisted.

Idempotent: budgets whose source_path already exists are skipped.
"""

import sys
import asyncio
import json
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import AsyncSessionLocal


# Keyword-based mapping from free-form industry/summary to the Sector enum.
SECTOR_KEYWORDS = {
    "finance": ["bank", "banking", "fintech", "payment", "trading", "financial"],
    "ecommerce": ["e-commerce", "ecommerce", "shop", "retail", "point of sale", "pos", "marketplace", "booking", "hotel"],
    "healthcare": ["patient", "health", "medical", "clinic", "hospital", "gym", "fitness"],
    "education": ["learning", "education", "course", "student", "quiz", "training", "school"],
    "logistics": ["fleet", "route", "supply chain", "shipping", "delivery", "tracking", "warehouse"],
    "industrial": ["iot", "sensor", "manufacturing", "industrial", "factory", "kubernetes"],
    "public_sector": ["government", "public", "urban", "city", "municipal"],
}


def infer_sector(industry: str, summary: str) -> str:
    """Infer a Sector enum value from free-form industry + project summary."""
    text = f"{industry} {summary}".lower()
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return sector
    return "other"


def normalize_budget(budget: dict) -> dict:
    """
    Normalize a budget record to the canonical Budget schema.

    Legacy records use client_metadata = {name, industry} without a sector
    or country. We infer a Sector enum and default country to 'ES'.
    """
    client = dict(budget.get("client_metadata", {}))

    # Already canonical: has sector + country
    if "sector" in client and "country" in client:
        return budget

    industry = client.get("industry", "")
    summary = budget.get("project_summary", "")

    normalized_client = {
        "name": client.get("name", "Unknown"),
        "sector": infer_sector(industry, summary),
        "country": client.get("country", "ES"),
    }

    normalized = dict(budget)
    normalized["client_metadata"] = normalized_client
    return normalized


async def ingest_budgets():
    """Load, normalize, and ingest all budgets from the sample dataset."""

    from embedding_pipeline.persistence import DocumentRepository

    print("=" * 100)
    print("BULK BUDGET INGESTION")
    print("=" * 100)

    # Load dataset
    dataset_path = project_root / "data" / "budgets_sample.json"
    with open(dataset_path, encoding="utf-8") as f:
        budgets = json.load(f)

    print(f"\nLoaded {len(budgets)} budgets from {dataset_path.name}\n")

    ingested = 0
    skipped = 0
    failed = 0

    async with AsyncSessionLocal() as session:
        repository = DocumentRepository(session)

        for budget in budgets:
            budget_id = budget.get("budget_id", "UNKNOWN")
            source_path = f"data/budgets_sample.json::{budget_id}"

            try:
                normalized = normalize_budget(budget)

                result = await repository.ingest_budget(
                    source_path=source_path,
                    document_type="historical_budget",
                    budget_dict=normalized,
                )

                sector = normalized["client_metadata"]["sector"]
                print(
                    f"  [OK] {budget_id} | sector={sector} | "
                    f"doc_id={result['document_id']} | chunks={result['chunks_created']}"
                )
                ingested += 1

            except ValueError as e:
                if "already exists" in str(e):
                    print(f"  [SKIP] {budget_id} | already ingested")
                    skipped += 1
                else:
                    print(f"  [FAIL] {budget_id} | validation: {e}", file=sys.stderr)
                    failed += 1

            except Exception as e:
                print(f"  [FAIL] {budget_id} | {type(e).__name__}: {e}", file=sys.stderr)
                failed += 1

    print("\n" + "=" * 100)
    print(f"DONE: {ingested} ingested, {skipped} skipped, {failed} failed")
    print("=" * 100)


if __name__ == "__main__":
    try:
        asyncio.run(ingest_budgets())
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
