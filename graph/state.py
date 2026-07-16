"""Typed shared state for the estimation graph (Session 13)."""

from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict


class Component(TypedDict):
    """A component to be estimated, grouped from the requirements."""

    name: str
    category: str


class BudgetMatch(TypedDict):
    """A historical budget reference retrieved for a component."""

    component: str
    reference_budget_id: str
    amount: float


class EstimationState(TypedDict):
    """State that flows through the graph, updated node by node."""

    transcript: str
    requirements: list[str]
    components: list[Component]
    # Accumulator field: grows as each component is searched. The operator.add
    # reducer merges each node's partial list into the running one.
    budget_matches: Annotated[list[BudgetMatch], operator.add]
    estimate: Optional[dict]
    status: Optional[str]  # "validated" | "needs_review"
    errors: Annotated[list[str], operator.add]
