from abc import ABC, abstractmethod

from app.schemas import EstimationOutput


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
