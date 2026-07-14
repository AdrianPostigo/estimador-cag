"""Schemas for the estimation agent: reasoning trace and structured result."""

from pydantic import BaseModel, Field


class TraceStep(BaseModel):
    """One reason -> act -> observe step of the agent loop."""

    step: int = Field(description="1-indexed position in the trace")
    turn: int = Field(
        description="Loop iteration this step belongs to; a turn can issue several "
        "tool calls in parallel, and they share the turn's reasoning",
    )
    reasoning: str | None = Field(
        default=None,
        description="Reasoning summary emitted by the model for this turn, if any. "
        "Carried by the first step of the turn; parallel calls in the same turn "
        "leave it None",
    )
    action: str = Field(description="Tool invoked with its arguments")
    observation: str = Field(description="Summary of what the tool returned")


class EstimatedComponent(BaseModel):
    """A component priced by the deterministic calculate_estimate tool."""

    name: str = Field(description="Component name")
    reference_count: int = Field(description="Historical references used")
    estimated_hours: float = Field(description="Median of references + contingency")
    unbudgeted: bool = Field(description="True when no historical reference was found")


class AgentEstimate(BaseModel):
    """The structured estimate.

    Figures come exclusively from calculate_estimate (deterministic); the model
    only contributes the narrative summary.
    """

    components: list[EstimatedComponent] = Field(description="Per-component breakdown")
    total_hours: float = Field(description="Total estimated hours")
    summary: str = Field(description="Narrative summary written by the agent")


class AgentRunResult(BaseModel):
    """Result of one agent run: the estimate plus the reasoning trace."""

    estimate: AgentEstimate | None = Field(
        default=None,
        description="None when the agent never produced a calculation",
    )
    trace: list[TraceStep] = Field(description="Ordered reason/act/observe steps")
    iterations: int = Field(description="Number of loop iterations executed")
    request_id: str = Field(description="Correlation id for this run")


class AgentEstimateRequest(BaseModel):
    """Request carrying the meeting transcript to estimate."""

    transcript: str = Field(
        min_length=20,
        max_length=50000,
        description="Transcript of the client discovery meeting",
    )
