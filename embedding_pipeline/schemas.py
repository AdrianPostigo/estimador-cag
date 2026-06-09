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


# Session 08: Persistence-based ingestion
class IngestBudgetRequest(BaseModel):
    """Request to ingest a single budget and persist it to PostgreSQL."""

    source_path: str = Field(
        min_length=1,
        description="Unique identifier for the budget (e.g., 'data/budgets/budget_2024_q1.json')",
    )
    document_type: str = Field(
        min_length=1,
        description="Classification of the document (e.g., 'historical_budget', 'estimate')",
    )
    content: dict[str, Any] = Field(
        description="Complete Budget JSON (must validate as Budget model)",
    )


class IngestBudgetResponse(BaseModel):
    """Response after persisting a budget and its chunks to PostgreSQL."""

    document_id: int = Field(description="ID of created document in PostgreSQL")
    chunks_created: int = Field(description="Number of chunks created for this budget")
    embedding_dimension: int = Field(description="Dimensionality of embeddings (1536 for text-embedding-3-small)")
    ingestion_time_ms: float = Field(description="Total ingestion time in milliseconds")


class IngestBudgetConflictResponse(BaseModel):
    """Response when attempting to ingest a budget with duplicate source_path."""

    detail: str = Field(default="Document already ingested")
    document_id: int = Field(description="ID of existing document with this source_path")


# Session 08: Semantic search
class SearchRequest(BaseModel):
    """Request for semantic search over embedded chunks."""

    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Search query (will be embedded with text-embedding-3-small)",
    )
    k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of nearest neighbors to return",
    )


class SearchResult(BaseModel):
    """Single result from semantic search."""

    chunk_id: int = Field(description="ID of chunk in PostgreSQL")
    document_id: int = Field(description="ID of parent document")
    chunk_type: str = Field(description="Type of chunk (e.g., 'component')")
    content: str = Field(description="Text content of chunk")
    distance: float = Field(description="Cosine distance (0=identical, 2=opposite)")
    metadata: dict[str, Any] = Field(description="Metadata dict attached to chunk")


class SearchResponse(BaseModel):
    """Response with semantic search results."""

    query: str = Field(description="Original query")
    k: int = Field(description="Number of results requested")
    search_time_ms: float = Field(description="Query execution time in milliseconds")
    results: list[SearchResult] = Field(description="List of k nearest chunks")
