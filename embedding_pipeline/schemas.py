"""Pydantic v2 schemas for embedding pipeline."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


Sector = Literal[
    "finance",
    "ecommerce",
    "healthcare",
    "industrial",
    "education",
    "public_sector",
    "logistics",
    "other",
]

Complexity = Literal["low", "medium", "high"]


class ClientMetadata(BaseModel):
    """Client information associated with a budget."""

    name: str = Field(min_length=1)
    sector: Sector
    country: str = Field(min_length=2, max_length=2)


class BudgetComponent(BaseModel):
    """A component or module within a project budget."""

    component_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    tech_stack: list[str] = Field(default_factory=list)
    estimated_hours: int = Field(gt=0)
    complexity: Complexity
    dependencies: list[str] = Field(default_factory=list)


class Budget(BaseModel):
    """A complete project budget with components."""

    budget_id: str = Field(min_length=1)
    client_metadata: ClientMetadata
    project_summary: str = Field(min_length=1)
    main_technology: str = Field(min_length=1)
    year: int = Field(ge=2000, le=2100)
    total_estimated_hours: int = Field(gt=0)
    components: list[BudgetComponent] = Field(min_length=1)

    @field_validator("components")
    @classmethod
    def component_ids_must_be_unique(
        cls,
        components: list[BudgetComponent],
    ) -> list[BudgetComponent]:
        """Ensure all component IDs are unique within a budget."""
        component_ids = [component.component_id for component in components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("component_id values must be unique within a budget")
        return components


class Chunk(BaseModel):
    """A text chunk extracted from a budget component."""

    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    token_count: int = Field(ge=0)


class EmbeddedChunk(Chunk):
    """A chunk with its corresponding embedding vector."""

    embedding: list[float] = Field(min_length=1)


class IngestRequest(BaseModel):
    """Request to ingest and embed a batch of budgets."""

    budgets: list[Budget] = Field(min_length=1)


class IngestResponse(BaseModel):
    """Response containing embedded chunks and ingestion statistics."""

    chunks: list[EmbeddedChunk]
    stats: dict[str, int | float]
