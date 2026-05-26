from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.schemas import EstimationOutput


@dataclass
class MetricResult:
    """Result of evaluating a metric."""
    name: str
    score: float  # 0.0 to 1.0
    passed: bool  # score >= 0.5
    details: str  # human-readable explanation


class Metric(ABC):
    """Base class for evaluation metrics."""

    @abstractmethod
    def evaluate(self, output: EstimationOutput, golden_case: dict) -> bool:
        """Evaluate if output passes this metric. Return True/False."""
        pass


class SchemaAdherenceMetric(Metric):
    """Valida que EstimationOutput pase Pydantic validation."""

    def evaluate(self, output: EstimationOutput, golden_case: dict) -> bool:
        try:
            EstimationOutput.model_validate(output.model_dump())
            return True
        except Exception:
            return False


class CostBoundsMetric(Metric):
    """Valida que hours/duration estén dentro de bounds realistas."""

    def evaluate(self, output: EstimationOutput, golden_case: dict) -> bool:
        bounds = golden_case.get("cost_bounds", {})
        if not bounds:
            return True  # No bounds specified, pass

        hours_min = bounds.get("hours_min", 0)
        hours_max = bounds.get("hours_max", 9999)
        weeks_min = bounds.get("weeks_min", 0)
        weeks_max = bounds.get("weeks_max", 9999)

        # Check if any metric is outside bounds
        hours_ok = hours_min <= output.total_hours_max <= hours_max
        weeks_ok = weeks_min <= output.duration_weeks_max <= weeks_max

        return hours_ok and weeks_ok


class ContentRecallMetric(Metric):
    """Valida que estimación mencione key points del input."""

    def evaluate(self, output: EstimationOutput, golden_case: dict) -> bool:
        expected_keys = golden_case.get("expected_keys", [])
        if not expected_keys:
            return True  # No keys specified, pass

        # Combine all text fields where key points might appear
        full_text = (
            output.project_summary.lower()
            + " "
            + " ".join(output.assumptions).lower()
            + " "
            + " ".join(t.name.lower() for t in output.tasks)
        )

        # Count how many expected keys are mentioned
        matched = sum(1 for key in expected_keys if key.lower() in full_text)

        # Need at least 70% of expected keys mentioned
        threshold = len(expected_keys) * 0.7
        return matched >= threshold


class LatencyBudgetMetric(Metric):
    """Validates that latency_ms stays within a budget."""

    def __init__(self, budget_ms: int) -> None:
        self.budget_ms = budget_ms

    def evaluate(self, observation: dict) -> bool:
        """
        Check if latency_ms <= budget_ms.

        observation: dict with 'latency_ms' key (from turn_observed event or similar)
        """
        latency_ms = observation.get("latency_ms", float("inf"))
        return latency_ms <= self.budget_ms


class CostBudgetMetric(Metric):
    """Validates that cost_usd stays within a budget."""

    def __init__(self, budget_usd: float) -> None:
        self.budget_usd = budget_usd

    def evaluate(self, observation: dict) -> bool:
        """
        Check if cost_usd <= budget_usd.

        observation: dict with 'cost_usd' key (from turn_observed event or similar)
        """
        cost_usd = observation.get("cost_usd", float("inf"))
        return cost_usd <= self.budget_usd
