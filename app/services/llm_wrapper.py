import time
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

# Precios en USD por 1M tokens (aproximados a mayo 2026)
MODEL_COSTS = {
    "anthropic/claude-opus-4-7": {
        "input": 15.00,
        "output": 75.00,
    },
    "anthropic/claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
    },
    "anthropic/claude-haiku-4-5-20251001": {
        "input": 0.80,
        "output": 4.00,
    },
    # Fallback for unknown models
    "default": {
        "input": 1.00,
        "output": 5.00,
    },
}


@dataclass
class LLMMetrics:
    """Observability metrics from a single LLM call."""
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float


def _get_model_costs(model_name: str) -> dict:
    """Get pricing for a model; fallback to default if not found."""
    return MODEL_COSTS.get(model_name, MODEL_COSTS["default"])


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for a single LLM call."""
    costs = _get_model_costs(model_name)
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return round(input_cost + output_cost, 6)


def create_metrics(
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
) -> LLMMetrics:
    """Create observable LLMMetrics from LLM call data."""
    cost = calculate_cost(model, input_tokens, output_tokens)
    return LLMMetrics(
        model=model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cost_usd=cost,
    )
