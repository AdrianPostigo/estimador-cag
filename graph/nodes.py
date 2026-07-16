"""LangGraph nodes for the estimation flow (Session 13).

Each node is a pure function of the shared state that returns a partial update.
Nodes reuse the Session 09-12 logic: extract/classify are LLM steps (OpenAI
Responses API with structured outputs), search_budgets wraps the retrieval
pipeline, and generate_estimate is the deterministic cost function.
"""

from __future__ import annotations

import os
from typing import Any

import logfire
import structlog
from langchain_core.runnables import RunnableConfig
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.generation.agentic.agent_tools import calculate_estimate
from app.generation.agentic.agent_tools import search_budgets as search_budgets_tool
from graph.state import BudgetMatch, EstimationState

logger = structlog.get_logger()

# Extraction/classification are structured tasks, not open-ended reasoning, so a
# small model is the right cost/latency point. Decoupled from AGENT_MODEL (the
# Session 12 agent stays on gpt-5).
GRAPH_MODEL = os.getenv("GRAPH_MODEL", "gpt-5-mini")

_client = AsyncOpenAI()


# --- Structured outputs for the two LLM nodes --------------------------------

class _RequirementsOutput(BaseModel):
    requirements: list[str] = Field(
        description="Distinct functional and technical requirements stated by the client",
    )


class _ComponentOutput(BaseModel):
    name: str = Field(description="Short English name of the component")
    category: str = Field(
        description="Category, e.g. backend, integration, mobile_app, analytics, frontend",
    )


class _ComponentsOutput(BaseModel):
    components: list[_ComponentOutput]


_EXTRACT_PROMPT = """You are a requirements analyst.

Read the client discovery meeting transcript (it may be written in Spanish) and
list the distinct functional and technical requirements the client stated. Write
each requirement as a short, self-contained English phrase. Ignore scheduling,
pleasantries and commercial chatter.
"""

_CLASSIFY_PROMPT = """You group requirements into the software components to estimate.

Given the list of requirements, produce the distinct components of work. Each
component has a short English name and a category (for example: backend,
integration, mobile_app, analytics, frontend, infrastructure). Merge requirements
that belong to the same deliverable into one component; keep clearly separate
pieces (for example an ERP integration versus a mobile app) as distinct components.
"""


async def extract_requirements(state: EstimationState) -> dict[str, Any]:
    """Transcript -> list of requirements (LLM)."""
    with logfire.span("node: extract_requirements") as span:
        response = await _client.responses.parse(
            model=GRAPH_MODEL,
            instructions=_EXTRACT_PROMPT,
            input=state["transcript"],
            text_format=_RequirementsOutput,
        )
        requirements = response.output_parsed.requirements

        span.set_attribute("model", GRAPH_MODEL)
        span.set_attribute("transcript_chars", len(state["transcript"]))
        span.set_attribute("requirements", len(requirements))

    logger.info("node_extract_requirements", requirements=len(requirements))
    return {"requirements": requirements}


async def classify_components(state: EstimationState) -> dict[str, Any]:
    """Requirements -> components with a category (LLM)."""
    with logfire.span("node: classify_components") as span:
        requirements = state["requirements"]
        user_input = "Requirements:\n" + "\n".join(f"- {req}" for req in requirements)

        response = await _client.responses.parse(
            model=GRAPH_MODEL,
            instructions=_CLASSIFY_PROMPT,
            input=user_input,
            text_format=_ComponentsOutput,
        )
        components = [
            {"name": component.name, "category": component.category}
            for component in response.output_parsed.components
        ]

        span.set_attribute("model", GRAPH_MODEL)
        span.set_attribute("requirements", len(requirements))
        span.set_attribute("components", len(components))

    logger.info("node_classify_components", components=len(components))
    return {"components": components}


async def search_budgets(state: EstimationState, config: RunnableConfig) -> dict[str, Any]:
    """For each component, retrieve historical budget references (sequential).

    Wraps the Session 09-12 retrieval tool. Returns a partial update to the
    accumulator field budget_matches.

    The repository is injected through config rather than the state: it is a live
    per-request object, so it must not end up in the checkpointed state.
    """
    repository = config["configurable"]["repository"]
    matches: list[BudgetMatch] = []

    with logfire.span("node: search_budgets") as span:
        for component in state["components"]:
            # One child span per component: makes the cost of doing this
            # sequentially visible in the trace.
            with logfire.span(
                "search component {component}", component=component["name"]
            ) as component_span:
                query = f"{component['name']} ({component['category']})"
                result = await search_budgets_tool(
                    {"query": query, "filters": None}, repository
                )

                found = 0
                for item in result["results"]:
                    amount = item.get("reference_amount")
                    if amount is None:
                        continue
                    matches.append(
                        {
                            "component": component["name"],
                            "reference_budget_id": str(item.get("budget_id")),
                            "amount": float(amount),
                        }
                    )
                    found += 1

                component_span.set_attribute("matches", found)

        span.set_attribute("components", len(state["components"]))
        span.set_attribute("matches", len(matches))

    logger.info("node_search_budgets", components=len(state["components"]), matches=len(matches))
    return {"budget_matches": matches}


def generate_estimate(state: EstimationState) -> dict[str, Any]:
    """Consolidate the retrieved references into an estimate (deterministic)."""
    with logfire.span("node: generate_estimate") as span:
        references: dict[str, list[float]] = {
            component["name"]: [] for component in state["components"]
        }
        for match in state["budget_matches"]:
            references.setdefault(match["component"], []).append(match["amount"])

        components_arg = [
            {"name": name, "reference_amounts": amounts}
            for name, amounts in references.items()
        ]
        estimate = calculate_estimate({"components": components_arg})

        span.set_attribute("components", len(components_arg))
        span.set_attribute("total_hours", estimate["total_hours"])

    logger.info("node_generate_estimate", total_hours=estimate["total_hours"])
    return {"estimate": estimate}


def validate_and_consolidate(state: EstimationState) -> dict[str, Any]:
    """Review the estimate and set the output status (deterministic)."""
    with logfire.span("node: validate_and_consolidate") as span:
        estimate = state.get("estimate")
        errors: list[str] = []

        if not estimate or not estimate.get("components"):
            span.set_attribute("status", "needs_review")
            logger.info("node_validate_and_consolidate", status="needs_review")
            return {"status": "needs_review", "errors": ["no estimate was produced"]}

        unbudgeted = [c["name"] for c in estimate["components"] if c["unbudgeted"]]
        if unbudgeted:
            errors.append(f"unbudgeted components: {', '.join(unbudgeted)}")

        status = "needs_review" if unbudgeted else "validated"

        span.set_attribute("status", status)
        span.set_attribute("unbudgeted", len(unbudgeted))

    logger.info("node_validate_and_consolidate", status=status, unbudgeted=len(unbudgeted))
    return {"status": status, "errors": errors}
