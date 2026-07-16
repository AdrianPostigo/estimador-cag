"""Build and compile the estimation graph (Session 13)."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from graph.nodes import (
    classify_components,
    extract_requirements,
    generate_estimate,
    search_budgets,
    validate_and_consolidate,
)
from graph.state import EstimationState


def build_graph(checkpointer):
    """Wire the five nodes as a sequential graph and compile it."""
    builder = StateGraph(EstimationState)

    builder.add_node("extract_requirements", extract_requirements)
    builder.add_node("classify_components", classify_components)
    builder.add_node("search_budgets", search_budgets)  # sequential for now
    builder.add_node("generate_estimate", generate_estimate)
    builder.add_node("validate_and_consolidate", validate_and_consolidate)

    builder.add_edge(START, "extract_requirements")
    builder.add_edge("extract_requirements", "classify_components")
    builder.add_edge("classify_components", "search_budgets")
    builder.add_edge("search_budgets", "generate_estimate")
    builder.add_edge("generate_estimate", "validate_and_consolidate")
    builder.add_edge("validate_and_consolidate", END)

    return builder.compile(checkpointer=checkpointer)
