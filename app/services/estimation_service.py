"""Unified estimation service with turn-level observability."""

from dataclasses import dataclass
from typing import Any

import structlog

from app.config import PROVIDER
from app.prompts.loader import render_estimation_prompt
from app.schemas import (
    DetailLevel,
    EstimationOutput,
    EstimationRequest,
    OutputFormat,
    ProjectType,
)
from app.services.actor_critic_boss import estimate_with_acb
from app.services.metadata import update_metadata
from app.services.tier_scoring import get_model_for_tier, score_input
from app.sessions import Session

logger = structlog.get_logger(__name__)

# Thread-local context for capturing LLM metrics across function boundaries
_llm_metrics_context: dict[str, Any] = {}


def capture_llm_metrics(metrics: dict[str, Any]) -> None:
    """Store LLM metrics for retrieval in estimate_conversational."""
    _llm_metrics_context.update(metrics)


def retrieve_llm_metrics() -> dict[str, Any]:
    """Retrieve and clear captured LLM metrics."""
    metrics = _llm_metrics_context.copy()
    _llm_metrics_context.clear()
    return metrics


@dataclass
class TurnObservables:
    """Unified observables for a single turn."""
    turn_index: int
    session_id: str
    enriched_transcript_chars: int
    attachments_total_chars: int
    messages_in_window: int
    anchors_count: int
    summary_chars: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    cache_hit_kind: str  # "none" | "exact" | "semantic"
    last_resolved_tier: int
    last_tier_rule: str


def estimate_conversational(
    session: Session,
    description: str,
    project_type: ProjectType,
    detail_level: DetailLevel,
    output_format: OutputFormat,
    attachment_text: str = "",
    attachment_filename: str = "",
) -> tuple[EstimationOutput, TurnObservables]:
    """
    Execute estimation with unified turn-level observability.

    Returns: (EstimationOutput, TurnObservables)
    """
    session_id = session.session_id

    # Build enriched transcript
    user_content = description
    attachments_total_chars = 0
    if attachment_text:
        user_content += f"\n\n--- adjunto: {attachment_filename} ---\n{attachment_text}"
        attachments_total_chars = len(attachment_text)

    enriched_transcript_chars = len(user_content)

    # Create estimation request
    request = EstimationRequest(
        description=description,
        project_type=project_type,
        detail_level=detail_level,
        output_format=output_format,
    )

    # Render prompts with metadata context
    system_prompt, _ = render_estimation_prompt(
        request=request,
        version="v1",
        project_metadata=session.metadata if session.history.turn_count > 0 else None,
    )

    # Score input and select model dynamically
    tier_scoring = score_input(description)
    tier = tier_scoring["tier"]
    model_name = get_model_for_tier(tier)

    # Store tier observable in session
    session.last_resolved_tier = tier
    session.last_tier_rule = tier_scoring["reason"]

    # Build messages from conversation history
    messages = session.history.to_messages_list(system_prompt)
    messages.append({"role": "user", "content": user_content})

    # Execute estimation with ACB
    output, raw_output, acb_info = estimate_with_acb(
        messages=messages,
        metadata=session.metadata,
        description=description,
        model_name=model_name,
    )

    # Update session history and metadata
    session.history.add_turn(user_content, raw_output)
    session.metadata = update_metadata(session.metadata, output, description)

    # Retrieve LLM metrics captured during estimate_with_acb
    llm_metrics = retrieve_llm_metrics()
    tokens_in = llm_metrics.get("tokens_in", 0)
    tokens_out = llm_metrics.get("tokens_out", 0)
    cost_usd = llm_metrics.get("cost_usd", 0.0)
    latency_ms = llm_metrics.get("latency_ms", 0.0)
    cache_hit_kind = llm_metrics.get("cache_hit_kind", "none")

    # Build turn observables
    summary_text = session.history._accumulated_summary or ""
    turn_index = session.history.turn_count

    observables = TurnObservables(
        turn_index=turn_index,
        session_id=session_id,
        enriched_transcript_chars=enriched_transcript_chars,
        attachments_total_chars=attachments_total_chars,
        messages_in_window=len(session.history._messages),
        anchors_count=session.anchors_count,
        summary_chars=len(summary_text),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        cache_hit_kind=cache_hit_kind,
        last_resolved_tier=session.last_resolved_tier,
        last_tier_rule=session.last_tier_rule,
    )

    # Emit unified turn_observed event
    logger.info(
        "turn_observed",
        turn_index=observables.turn_index,
        session_id=observables.session_id,
        enriched_transcript_chars=observables.enriched_transcript_chars,
        attachments_total_chars=observables.attachments_total_chars,
        messages_in_window=observables.messages_in_window,
        anchors_count=observables.anchors_count,
        summary_chars=observables.summary_chars,
        tokens_in=observables.tokens_in,
        tokens_out=observables.tokens_out,
        cost_usd=observables.cost_usd,
        latency_ms=observables.latency_ms,
        cache_hit_kind=observables.cache_hit_kind,
        last_resolved_tier=observables.last_resolved_tier,
        last_tier_rule=observables.last_tier_rule,
    )

    return output, observables
