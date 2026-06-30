"""Pydantic v2 schemas for embedding pipeline."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    """Request for search over embedded chunks with optional reranking."""

    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Search query",
    )
    k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Final number of results to return",
    )
    search_mode: str = Field(
        default="semantic",
        description="Search mode: 'semantic' (vector), 'lexical' (full-text), or 'hybrid' (RRF-fused)",
    )
    enable_reranking: bool = Field(
        default=False,
        description="Enable cross-encoder reranking (FlashRank) for fine-grained relevance ordering",
    )
    reranker_k: int = Field(
        default=50,
        ge=5,
        le=200,
        description="Number of documents to retrieve before reranking (recall stage of recall-then-rerank pattern)",
    )


class SearchResult(BaseModel):
    """Single result from search (with optional reranker score)."""

    chunk_id: int = Field(description="ID of chunk in PostgreSQL")
    document_id: int | None = Field(default=None, description="ID of parent document")
    chunk_type: str = Field(description="Type of chunk (e.g., 'component')")
    content: str = Field(description="Text content of chunk")
    distance: float | None = Field(default=None, description="Cosine distance (for semantic mode)")
    rank: float | None = Field(default=None, description="Relevance rank (for lexical/hybrid mode)")
    rrf_score: float | None = Field(default=None, description="RRF fusion score (for hybrid mode)")
    reranker_score: float | None = Field(default=None, description="FlashRank cross-encoder score (if reranking enabled)")
    metadata: dict[str, Any] = Field(description="Metadata dict attached to chunk")


class SearchResponse(BaseModel):
    """Response with search results (semantic, lexical, hybrid, ±reranking)."""

    query: str = Field(description="Original query")
    k: int = Field(description="Final number of results returned")
    search_mode: str = Field(description="Search mode used ('semantic', 'lexical', 'hybrid')")
    enable_reranking: bool = Field(description="Whether reranking was applied")
    search_time_ms: float = Field(description="Retrieval execution time in milliseconds")
    reranking_time_ms: float = Field(description="Reranking time in milliseconds (0 if disabled)")
    results: list[SearchResult] = Field(description="List of final results (after reranking if enabled)")


# Session 10: Estimation with retrieved context
class EstimateWithContextRequest(BaseModel):
    """Request for estimation with context from similar historical budgets."""

    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Search query to find similar budgets (e.g., 'REST API with OAuth for fintech')",
    )
    search_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of similar budget chunks to retrieve as context",
    )
    project_type: str = Field(
        description="Project type (mobile_app, web_saas, internal_tool, data_pipeline)",
    )
    detail_level: str = Field(
        description="Detail level (summary, medium, detailed)",
    )
    output_format: str = Field(
        description="Output format (phases_table, line_items, narrative)",
    )


class RetrievalMetrics(BaseModel):
    """Metrics about chunk retrieval for estimation context."""

    query: str = Field(description="Original search query")
    search_time_ms: float = Field(description="Time to retrieve chunks (milliseconds)")
    chunks_retrieved: int = Field(description="Number of chunks retrieved")
    top_distance: float = Field(description="Distance (cosine) of top-1 result", default=None)


class ContextualizedChunk(BaseModel):
    """Chunk retrieved for estimation context."""

    chunk_id: int = Field(description="ID of chunk in PostgreSQL")
    rank: int = Field(description="Rank in search results (1-indexed)")
    distance: float = Field(description="Cosine distance from query embedding")
    content: str = Field(description="Text content of chunk")
    chunk_type: str = Field(description="Type of chunk (component, etc)")
    metadata: dict[str, Any] = Field(description="Metadata: scope, technologies, complexity, estimated_hours")


class EstimateWithContextResponse(BaseModel):
    """Response with estimation and retrieved context chunks."""

    estimation: dict[str, Any] = Field(
        description="EstimationOutput (project_summary, tasks, total_hours_min/max, etc)",
    )
    retrieval: RetrievalMetrics = Field(description="Search metrics for context retrieval")
    context_chunks: list[ContextualizedChunk] = Field(
        description="Similar budgets retrieved to inform the estimation",
    )


# Session 11: Grounded estimation with verifiable line-level citations
class SourceReference(BaseModel):
    """A citation backing a single estimation line to a retrieved source."""

    chunk_id: str = Field(
        description="ID of the retrieved chunk supporting this line (DB chunk id)",
    )
    document_id: str = Field(
        description="Historical budget the chunk belongs to (budget_id)",
    )
    evidence: str = Field(
        min_length=1,
        description="Verbatim span or figure from the source backing the line",
    )


class EstimateLineItem(BaseModel):
    """A single estimation line with its grounding to historical sources."""

    component: str = Field(min_length=1, description="Name of the estimated component")
    hours: float = Field(ge=0, description="Estimated hours for this component")
    rationale: str = Field(min_length=1, description="Reasoning behind the estimate")
    grounded: bool = Field(
        description="True if derived from retrieved sources; False if insufficient source data",
    )
    sources: list[SourceReference] = Field(
        description="Supporting sources; non-empty iff grounded is True (use [] when grounded is False)",
    )

    @model_validator(mode="after")
    def enforce_grounding_integrity(self) -> "EstimateLineItem":
        """
        Integrity rule:
        - grounded=True  -> at least one source.
        - grounded=False -> no sources and no invented hours (must be 0).
        """
        if self.grounded:
            if not self.sources:
                raise ValueError("a grounded line item must cite at least one source")
        else:
            if self.sources:
                raise ValueError("a non-grounded line item must not cite any source")
            if self.hours != 0:
                raise ValueError(
                    "a non-grounded line item cannot invent hours; hours must be 0"
                )
        return self


class GroundedEstimateOutput(BaseModel):
    """A grounded estimation: project summary plus cited line items."""

    project_summary: str = Field(min_length=1, description="Brief summary of the project")
    line_items: list[EstimateLineItem] = Field(
        min_length=1,
        description="Estimation lines, each carrying its grounding",
    )
    total_hours: float = Field(
        ge=0,
        description="Total estimated hours (sum of line item hours)",
    )

    @model_validator(mode="after")
    def total_hours_matches_lines(self) -> "GroundedEstimateOutput":
        """total_hours must equal the sum of line item hours (small tolerance)."""
        line_sum = sum(item.hours for item in self.line_items)
        if abs(self.total_hours - line_sum) > 0.5:
            raise ValueError(
                f"total_hours ({self.total_hours}) must equal the sum of "
                f"line item hours ({line_sum})"
            )
        return self


# Session 11: Post-generation citation verification
class LineCitationStatus(BaseModel):
    """Citation status of a single estimation line."""

    component: str = Field(description="Component name of the line")
    status: Literal["grounded", "dangling", "insufficient_data"] = Field(
        description="grounded=all cited ids present; dangling=invented id; "
        "insufficient_data=line marked grounded=False",
    )
    cited_chunk_ids: list[str] = Field(
        default_factory=list,
        description="All chunk_ids cited by this line",
    )
    dangling_chunk_ids: list[str] = Field(
        default_factory=list,
        description="Cited chunk_ids that were NOT in the retrieved context",
    )


class CitationReport(BaseModel):
    """Result of verifying a grounded estimate's citations against context."""

    total_lines: int = Field(description="Total number of estimation lines")
    grounded_lines: int = Field(description="Lines correctly grounded in retrieved context")
    dangling_lines: int = Field(description="Lines citing at least one invented chunk_id")
    insufficient_data_lines: int = Field(description="Lines marked grounded=False")
    has_dangling_citations: bool = Field(
        description="True if any line has a dangling citation (quality failure)",
    )
    lines: list[LineCitationStatus] = Field(
        description="Per-line citation status",
    )


class GroundedEstimateRequest(BaseModel):
    """Request for a grounded estimation with verifiable citations."""

    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Project description / estimation request",
    )
    search_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of historical chunks to retrieve as grounding sources",
    )
    search_mode: str = Field(
        default="semantic",
        description="Retrieval mode: 'semantic', 'lexical', or 'hybrid'",
    )


class GroundedEstimateResponse(BaseModel):
    """Response with a grounded estimate plus its citation verification."""

    estimate: GroundedEstimateOutput = Field(description="Generated grounded estimate")
    citation_report: CitationReport = Field(description="Post-generation citation verification")
    contexts: list[str] = Field(description="Retrieved chunk contents passed to the generator")
    request_id: str = Field(description="Correlation id for this generation")
