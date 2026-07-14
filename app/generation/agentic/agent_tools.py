"""The two tools the estimation agent can call (Session 12).

- ``search_budgets``: wraps the existing hybrid retrieval pipeline (Sessions 09-10).
  It only retrieves; it never computes totals.
- ``calculate_estimate``: a deterministic Python function. No LLM call.

``TOOL_DEFINITIONS`` holds the JSON Schemas (strict mode) exposed to the model.
The descriptions are the only thing the model reads to decide when to call each
tool, so they carry the usage contract explicitly.
"""

from __future__ import annotations

import statistics
from typing import Any

import structlog

from embedding_pipeline.persistence import DocumentRepository

logger = structlog.get_logger()

# Retrieval settings for search_budgets: the hybrid (RRF) + reranking pipeline
# built in Sessions 09-10. Note: on this small corpus, pure semantic retrieval
# measured better on both Precision@5 and latency (see README, Session 10), so
# these two constants are the knobs to flip if we trade fidelity for measured
# quality.
SEARCH_MODE = "hybrid"
ENABLE_RERANKING = True
SEARCH_K = 5

# A flat contingency buffer added to every component's central estimate. Keep it
# transparent — no hidden multipliers.
CONTINGENCY_FACTOR = 0.15


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "search_budgets",
        "description": (
            "Search historical project budgets for line items relevant to ONE component "
            "or requirement. Call it once per component you need to price, passing a "
            "natural-language description of that component (for example: 'OAuth 2.0 "
            "authentication backend with JWT for a mobile banking app'). It returns "
            "historical budget line items, each with a reference_amount (the hours that "
            "component actually took in a past project) and metadata (source budget id, "
            "client sector, main technology, year, complexity). Feed those "
            "reference_amount values into calculate_estimate as reference_amounts; never "
            "invent them. This tool only retrieves: it computes no totals and no "
            "estimate. If a search returns nothing useful, rephrase the query and search "
            "again before giving up on the component."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural-language description of the single component to price. "
                        "Be specific: state the capability, the technology if known, and "
                        "the domain (for example: 'payment processing with card gateway "
                        "for an e-commerce platform'). Do not pass the whole transcript."
                    ),
                },
                "filters": {
                    "type": ["object", "null"],
                    "description": (
                        "Optional filters applied to the retrieved historical items. Pass "
                        "null to search the whole corpus, which is the right default. "
                        "Only filter when the transcript states a hard constraint, "
                        "because filtering can remove otherwise comparable budgets."
                    ),
                    "properties": {
                        "component_type": {
                            "type": ["string", "null"],
                            "description": (
                                "Keep only historical items whose component name contains "
                                "this text, case-insensitive (for example 'authentication' "
                                "or 'payment'). Use it to sharpen a broad query, not to "
                                "replace it. Null for no restriction."
                            ),
                        },
                        "date_range": {
                            "type": ["object", "null"],
                            "description": (
                                "Keep only budgets whose year falls inside this range. "
                                "Useful when the transcript says recent budgets only. "
                                "Null for no restriction."
                            ),
                            "properties": {
                                "from_year": {
                                    "type": ["integer", "null"],
                                    "description": (
                                        "Earliest budget year to include. Null for no "
                                        "lower bound."
                                    ),
                                },
                                "to_year": {
                                    "type": ["integer", "null"],
                                    "description": (
                                        "Latest budget year to include. Null for no "
                                        "upper bound."
                                    ),
                                },
                            },
                            "required": ["from_year", "to_year"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["component_type", "date_range"],
                    "additionalProperties": False,
                },
            },
            "required": ["query", "filters"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "calculate_estimate",
        "description": (
            "Compute the estimate from the components you identified and the historical "
            "reference amounts you retrieved with search_budgets. Pass every component, "
            "each with the reference_amounts copied verbatim from search_budgets results. "
            "The tool takes the median of each component's reference amounts, adds a 15% "
            "contingency buffer, and sums the components into a total. A component whose "
            "reference_amounts list is empty is costed at 0 hours and flagged as "
            "unbudgeted rather than given an invented figure: if that happens, call "
            "search_budgets again for that component instead of guessing. This is pure "
            "arithmetic — it performs no retrieval and no reasoning. Call it once you "
            "have references for the components you intend to price."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "description": (
                        "Every component to include in the estimate, in the order they "
                        "should appear in the breakdown."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": (
                                    "Short name of the component as it should appear in "
                                    "the estimate (for example: 'Payment module')."
                                ),
                            },
                            "reference_amounts": {
                                "type": "array",
                                "description": (
                                    "Reference hours for this component, copied verbatim "
                                    "from the reference_amount values returned by "
                                    "search_budgets. Use an empty array only when "
                                    "search_budgets found no usable reference: the "
                                    "component is then flagged as unbudgeted instead of "
                                    "receiving an invented figure."
                                ),
                                "items": {"type": "number"},
                            },
                        },
                        "required": ["name", "reference_amounts"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["components"],
            "additionalProperties": False,
        },
    },
]


def _component_name(content: str) -> str:
    """Extract the component name from a chunk's contextual header."""
    for line in content.splitlines():
        if line.startswith("Component:"):
            return line.removeprefix("Component:").strip()
    return ""


def _passes_filters(
    component: str,
    metadata: dict[str, Any],
    filters: dict[str, Any] | None,
) -> bool:
    """Check a retrieved item against the optional tool filters."""
    if not filters:
        return True

    component_type = filters.get("component_type")
    if component_type and component_type.lower() not in component.lower():
        return False

    date_range = filters.get("date_range")
    if date_range:
        year = metadata.get("year")

        from_year = date_range.get("from_year")
        if from_year is not None and (year is None or year < from_year):
            return False

        to_year = date_range.get("to_year")
        if to_year is not None and (year is None or year > to_year):
            return False

    return True


async def search_budgets(
    args: dict[str, Any],
    repository: DocumentRepository,
) -> dict[str, Any]:
    """Retrieve historical budget line items relevant to one component.

    Wraps the existing retrieval pipeline (Sessions 09-10); it does not
    reimplement it. Metadata filters are applied to the retrieved results.
    """
    query = args["query"]
    filters = args.get("filters")

    search_result = await repository.hybrid_search(
        query=query,
        k=SEARCH_K,
        search_mode=SEARCH_MODE,
        enable_reranking=ENABLE_RERANKING,
    )

    items: list[dict[str, Any]] = []
    for chunk in search_result["results"]:
        metadata = chunk.get("metadata") or {}
        component = _component_name(chunk["content"])

        if not _passes_filters(component, metadata, filters):
            continue

        items.append(
            {
                "chunk_id": str(chunk["chunk_id"]),
                "budget_id": metadata.get("budget_id"),
                "component": component,
                "reference_amount": metadata.get("estimated_hours"),
                "client_sector": metadata.get("client_sector"),
                "main_technology": metadata.get("main_technology"),
                "year": metadata.get("year"),
                "complexity": metadata.get("complexity"),
                "excerpt": chunk["content"],
            }
        )

    logger.info(
        "tool_search_budgets",
        query=query,
        filtered=bool(filters),
        retrieved=len(search_result["results"]),
        returned=len(items),
    )

    if items:
        summary = (
            f"{len(items)} historical items for '{query}'; "
            f"reference amounts: {[item['reference_amount'] for item in items]}"
        )
    else:
        summary = f"no historical items matched '{query}'"

    return {"results": items, "summary": summary}


def calculate_estimate(args: dict[str, Any]) -> dict[str, Any]:
    """Cost each component from its historical reference amounts, then total."""
    components = args["components"]
    breakdown: list[dict[str, Any]] = []
    total = 0.0

    for component in components:
        name = component["name"]
        refs = component.get("reference_amounts", [])

        if refs:
            # Median, not mean: a single outlier budget (an unusually large or
            # small past project) should not drag the central estimate.
            central = statistics.median(refs)
            hours = round(central * (1 + CONTINGENCY_FACTOR), 1)
            unbudgeted = False
        else:
            # Never invent a figure for a component with no historical reference:
            # cost it at 0 and flag it so the agent can search again.
            hours = 0.0
            unbudgeted = True

        total += hours
        breakdown.append(
            {
                "name": name,
                "reference_count": len(refs),
                "estimated_hours": hours,
                "unbudgeted": unbudgeted,
            }
        )

    total = round(total, 1)

    unbudgeted_names = [item["name"] for item in breakdown if item["unbudgeted"]]
    summary = f"total={total}h across {len(breakdown)} components"
    if unbudgeted_names:
        # Surface unbudgeted components in the observation the agent reads, so it
        # can decide to search again rather than accept a 0-hour line.
        summary += (
            f"; {len(unbudgeted_names)} unbudgeted (no references): "
            f"{', '.join(unbudgeted_names)}"
        )

    logger.info(
        "tool_calculate_estimate",
        components=len(breakdown),
        total_hours=total,
        unbudgeted=len(unbudgeted_names),
    )

    return {
        "components": breakdown,
        "total_hours": total,
        "summary": summary,
    }
