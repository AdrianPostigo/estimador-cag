"""Structural chunking strategy for budget documents."""

import tiktoken

from embedding_pipeline.schemas import Budget, BudgetComponent, Chunk


class JSONStructuralChunker:
    """Chunks budgets by component, preserving parent context."""

    def __init__(self):
        """Initialize with tiktoken encoder for token counting."""
        self.encoding = tiktoken.encoding_for_model("text-embedding-3-small")

    def chunk(self, budgets: list[Budget]) -> list[Chunk]:
        """
        Split budgets into chunks, one per component.

        Each chunk combines parent budget context with component details.
        No splitting or overlap; one component = one chunk.

        Args:
            budgets: List of Budget objects to chunk.

        Returns:
            List of Chunk objects, ready for embedding.
        """
        chunks = []

        for budget in budgets:
            for component in budget.components:
                # Build chunk text with parent context + component details
                chunk_text = self._build_chunk_text(budget, component)

                # Count tokens
                tokens = self.encoding.encode(chunk_text)
                token_count = len(tokens)

                # Build metadata (filterable, not embedded)
                metadata = {
                    "budget_id": budget.budget_id,
                    "component_id": component.component_id,
                    "client_sector": budget.client_metadata.sector,
                    "main_technology": budget.main_technology,
                    "year": budget.year,
                    "complexity": component.complexity,
                    "estimated_hours": component.estimated_hours,
                }

                # Create chunk_id
                chunk_id = f"{budget.budget_id}::{component.component_id}"

                # Create Chunk object
                chunk = Chunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    metadata=metadata,
                    token_count=token_count,
                )

                chunks.append(chunk)

        return chunks

    def _build_chunk_text(self, budget: Budget, component: BudgetComponent) -> str:
        """Build readable chunk text combining parent context and component details."""
        lines = [
            f"[Project: {budget.project_summary}]",
            f"[Client sector: {budget.client_metadata.sector} | Year: {budget.year} | Main tech: {budget.main_technology}]",
            "",
            f"Component: {component.name}",
            f"Description: {component.description}",
            f"Tech stack: {', '.join(component.tech_stack) if component.tech_stack else 'N/A'}",
            f"Complexity: {component.complexity}",
            f"Estimated hours: {component.estimated_hours}",
        ]
        return "\n".join(lines)
