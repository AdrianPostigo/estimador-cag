"""
Tests for stress-test metrics: LatencyBudget, CostBudget, MemoryDrift.
"""

import pytest

from evals.metrics import CostBudgetMetric, LatencyBudgetMetric
from evals.stress.metrics import MemoryDriftMetric


class TestLatencyBudgetMetric:
    """Tests for LatencyBudgetMetric."""

    def test_latency_within_budget_passes(self):
        """Latency below budget should pass (score 1.0)."""
        metric = LatencyBudgetMetric(budget_ms=1000)
        observation = {"latency_ms": 500}
        result = metric.evaluate(observation)
        assert result.passed is True
        assert result.score == 1.0

    def test_latency_at_budget_passes(self):
        """Latency exactly at budget should pass."""
        metric = LatencyBudgetMetric(budget_ms=1000)
        observation = {"latency_ms": 1000}
        result = metric.evaluate(observation)
        assert result.passed is True
        assert result.score == 1.0

    def test_latency_exceeds_budget_fails(self):
        """Latency above budget should fail (score 0.0)."""
        metric = LatencyBudgetMetric(budget_ms=1000)
        observation = {"latency_ms": 1500}
        result = metric.evaluate(observation)
        assert result.passed is False
        assert result.score == 0.0

    def test_latency_missing_defaults_to_fail(self):
        """Missing latency_ms should fail (defaults to inf)."""
        metric = LatencyBudgetMetric(budget_ms=1000)
        observation = {}
        result = metric.evaluate(observation)
        assert result.passed is False


class TestCostBudgetMetric:
    """Tests for CostBudgetMetric."""

    def test_cost_within_budget_passes(self):
        """Cost below budget should pass (score 1.0)."""
        metric = CostBudgetMetric(budget_usd=0.01)
        observation = {"cost_usd": 0.005}
        result = metric.evaluate(observation)
        assert result.passed is True
        assert result.score == 1.0

    def test_cost_at_budget_passes(self):
        """Cost exactly at budget should pass."""
        metric = CostBudgetMetric(budget_usd=0.01)
        observation = {"cost_usd": 0.01}
        result = metric.evaluate(observation)
        assert result.passed is True
        assert result.score == 1.0

    def test_cost_exceeds_budget_fails(self):
        """Cost above budget should fail (score 0.0)."""
        metric = CostBudgetMetric(budget_usd=0.01)
        observation = {"cost_usd": 0.015}
        result = metric.evaluate(observation)
        assert result.passed is False
        assert result.score == 0.0

    def test_cost_missing_defaults_to_fail(self):
        """Missing cost_usd should fail (defaults to inf)."""
        metric = CostBudgetMetric(budget_usd=0.01)
        observation = {}
        result = metric.evaluate(observation)
        assert result.passed is False


class TestMemoryDriftMetric:
    """Tests for MemoryDriftMetric."""

    def test_fact_found_in_summary_passes(self):
        """Fact appearing in summary should pass."""
        metric = MemoryDriftMetric(
            fact="Multi-tenant",
            turn_introduced=2,
            where=["summary"],
        )
        snapshot = {
            "current_turn": 5,
            "project_summary": "Build a multi-tenant SaaS platform with audit logging",
            "mentioned_technologies": ["React", "Node.js"],
            "project_name": "SaaS Platform",
            "assumed_team_size": 3,
            "agreed_scope": "Core features only",
        }
        result = metric.evaluate(snapshot)
        assert result.passed is True
        assert result.score == 1.0
        assert "FOUND" in result.details

    def test_fact_found_in_technologies_passes(self):
        """Fact appearing in mentioned_technologies should pass."""
        metric = MemoryDriftMetric(
            fact="React",
            turn_introduced=1,
            where=["anchors"],
        )
        snapshot = {
            "current_turn": 5,
            "project_summary": "Build a web app",
            "mentioned_technologies": ["React", "Node.js", "PostgreSQL"],
            "project_name": "Web App",
            "assumed_team_size": 2,
            "agreed_scope": "MVP",
        }
        result = metric.evaluate(snapshot)
        assert result.passed is True
        assert result.score == 1.0

    def test_fact_not_found_fails(self):
        """Fact not appearing anywhere should fail."""
        metric = MemoryDriftMetric(
            fact="Flutter",
            turn_introduced=1,
            where=["summary", "anchors", "metadata"],
        )
        snapshot = {
            "current_turn": 8,
            "project_summary": "Mobile app using React Native",
            "mentioned_technologies": ["React Native", "Firebase"],
            "project_name": "Mobile App",
            "assumed_team_size": 2,
            "agreed_scope": "Cross-platform",
        }
        result = metric.evaluate(snapshot)
        assert result.passed is False
        assert result.score == 0.0
        assert "LOST" in result.details

    def test_fact_not_yet_introduced_passes(self):
        """Fact introduced in future turn should pass (not yet evaluated)."""
        metric = MemoryDriftMetric(
            fact="Analytics",
            turn_introduced=5,
            where=["summary"],
        )
        snapshot = {
            "current_turn": 3,  # Before turn 5
            "project_summary": "Build a SaaS",
            "mentioned_technologies": [],
            "project_name": "SaaS",
            "assumed_team_size": 1,
            "agreed_scope": "",
        }
        result = metric.evaluate(snapshot)
        assert result.passed is True  # Not yet evaluated
        assert "not yet introduced" in result.details.lower()

    def test_fact_case_insensitive_match(self):
        """Fact matching should be case-insensitive."""
        metric = MemoryDriftMetric(
            fact="multi-tenant",
            turn_introduced=1,
            where=["summary"],
        )
        snapshot = {
            "current_turn": 3,
            "project_summary": "MULTI-TENANT architecture required",
            "mentioned_technologies": [],
            "project_name": "SaaS",
            "assumed_team_size": 2,
            "agreed_scope": "",
        }
        result = metric.evaluate(snapshot)
        assert result.passed is True
        assert result.score == 1.0

    def test_metric_result_structure(self):
        """MemoryDriftMetric should return MetricResult with required fields."""
        metric = MemoryDriftMetric(
            fact="test-fact",
            turn_introduced=1,
            where=["summary"],
        )
        snapshot = {
            "current_turn": 2,
            "project_summary": "test-fact",
            "mentioned_technologies": [],
            "project_name": "",
            "assumed_team_size": None,
            "agreed_scope": "",
        }
        result = metric.evaluate(snapshot)

        # Verify MetricResult structure
        assert hasattr(result, "name")
        assert hasattr(result, "score")
        assert hasattr(result, "passed")
        assert hasattr(result, "details")

        assert isinstance(result.name, str)
        assert isinstance(result.score, float)
        assert isinstance(result.passed, bool)
        assert isinstance(result.details, str)

        assert 0.0 <= result.score <= 1.0
        assert result.passed == (result.score >= 0.5)


class TestBudgetMetricsIntegration:
    """Integration tests for budget metrics."""

    def test_multiple_budget_checks_on_same_observation(self):
        """Multiple budget metrics should work on same observation."""
        latency_metric = LatencyBudgetMetric(budget_ms=5000)
        cost_metric = CostBudgetMetric(budget_usd=0.05)

        observation = {
            "latency_ms": 2500,
            "cost_usd": 0.02,
        }

        latency_result = latency_metric.evaluate(observation)
        cost_result = cost_metric.evaluate(observation)

        assert latency_result.passed is True
        assert cost_result.passed is True

    def test_budget_metrics_with_edge_values(self):
        """Budget metrics should handle edge cases."""
        latency_metric = LatencyBudgetMetric(budget_ms=100)
        cost_metric = CostBudgetMetric(budget_usd=0.01)

        # Zero values should pass with positive budget
        assert latency_metric.evaluate({"latency_ms": 0}).passed
        assert cost_metric.evaluate({"cost_usd": 0.0}).passed

        # At exactly budget should pass
        assert latency_metric.evaluate({"latency_ms": 100}).passed
        assert cost_metric.evaluate({"cost_usd": 0.01}).passed
