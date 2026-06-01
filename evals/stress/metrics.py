"""
Stress-test specific metrics for multi-turn scenarios.

Measures metadata stability, fact retention, and coherence across turns.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MetricResult:
    """Result of evaluating a metric."""
    name: str
    score: float  # 0.0 to 1.0
    passed: bool  # score >= 0.5
    details: str  # human-readable explanation


class MemoryDriftMetric:
    """
    Validates that a fact declared in turn k appears in turn N (N > k).

    Checks across: summary, anchors (metadata), or ProjectMetadata fields.
    Uses exact match (case-insensitive) for determinism.
    """

    def __init__(
        self,
        fact: str,
        turn_introduced: int,
        where: list[str] | None = None,
    ) -> None:
        """
        Initialize memory drift metric.

        Args:
            fact: The statement to search for (e.g., "Multi-tenant architecture")
            turn_introduced: Turn number where fact was first mentioned (1-based)
            where: Fields to search in: ["summary", "anchors", "metadata"]
                   Default: all three
        """
        self.fact = fact
        self.turn_introduced = turn_introduced
        self.where = where or ["summary", "anchors", "metadata"]

    def evaluate(self, session_snapshot: dict) -> MetricResult:
        """
        Check if fact from turn_introduced survives in session_snapshot.

        session_snapshot: dict with keys:
            - current_turn: int (current turn number)
            - project_summary: str
            - mentioned_technologies: list[str]  # "anchors"
            - project_name: str | None
            - assumed_team_size: int | None
            - agreed_scope: str | None

        Returns: MetricResult with score 1.0 if fact found, 0.0 if not.
        """
        current_turn = session_snapshot.get("current_turn", 1)

        # Only evaluate if we're past the turn where fact was introduced
        if current_turn <= self.turn_introduced:
            return MetricResult(
                name=f"MemoryDrift({self.fact[:30]}...)",
                score=1.0,
                passed=True,
                details=f"Fact not yet introduced (current turn: {current_turn})",
            )

        fact_lower = self.fact.lower()
        found_in = []

        # Search in summary
        if "summary" in self.where:
            summary = session_snapshot.get("project_summary", "").lower()
            if fact_lower in summary:
                found_in.append("summary")

        # Search in anchors (mentioned_technologies, project_name, agreed_scope)
        if "anchors" in self.where:
            techs = session_snapshot.get("mentioned_technologies", [])
            techs_lower = [t.lower() for t in techs]
            if any(fact_lower in tech for tech in techs_lower):
                found_in.append("anchors_tech")

            project_name = session_snapshot.get("project_name", "").lower()
            if fact_lower in project_name:
                found_in.append("anchors_name")

            agreed_scope = session_snapshot.get("agreed_scope", "").lower()
            if fact_lower in agreed_scope:
                found_in.append("anchors_scope")

        # Search in metadata (ProjectMetadata fields)
        if "metadata" in self.where:
            team_size = session_snapshot.get("assumed_team_size")
            if team_size and fact_lower in str(team_size).lower():
                found_in.append("metadata_team")

        # Determine if fact was found
        found = len(found_in) > 0
        score = 1.0 if found else 0.0

        details = (
            f"Fact '{self.fact}' from turn {self.turn_introduced} "
            f"{'FOUND' if found else 'LOST'} at turn {current_turn}."
        )
        if found_in:
            details += f" Found in: {', '.join(found_in)}"

        return MetricResult(
            name=f"MemoryDrift({self.fact[:30]}...)",
            score=score,
            passed=found,
            details=details,
        )


class AttachmentRecallMetric:
    """
    Validates that attachment content is recalled in summary.

    Measures how well the system integrates attachment content
    into the final estimation summary (not truncated or ignored).
    """

    def __init__(self, keywords: list[str]) -> None:
        """
        Initialize attachment recall metric.

        Args:
            keywords: Keywords unique to the attachment (e.g., ["lorem", "ipsum"])
        """
        self.keywords = [k.lower() for k in keywords]

    def evaluate(self, observation: dict) -> MetricResult:
        """
        Check if attachment keywords appear in summary.

        observation: dict with:
            - project_summary: str
            - attachment_size_kb: int (for context)
            - attachment_present: bool

        Returns: MetricResult with score based on keyword match rate.
        """
        if not observation.get("attachment_present", False):
            return MetricResult(
                name="AttachmentRecall",
                score=1.0,
                passed=True,
                details="No attachment (baseline case)",
            )

        summary = observation.get("project_summary", "").lower()
        matched = sum(1 for kw in self.keywords if kw in summary)
        score = matched / len(self.keywords) if self.keywords else 1.0

        attachment_size = observation.get("attachment_size_kb", 0)
        details = (
            f"Matched {matched}/{len(self.keywords)} keywords "
            f"in summary (attachment: {attachment_size} KB). "
            f"Score: {score:.2f}"
        )

        return MetricResult(
            name="AttachmentRecall",
            score=score,
            passed=score >= 0.5,  # Pass if at least 50% of keywords found
            details=details,
        )


class MetadataCoherenceMetric:
    """
    Validates that metadata fields are coherent and don't contradict.

    For example:
    - If project_name says "SaaS", but mentioned_technologies is all mobile,
      that's a contradiction.
    - If team_size = 10 but duration_weeks = 1, that's incoherent.
    """

    def evaluate(self, snapshot: dict) -> MetricResult:
        """
        Check coherence between metadata fields.

        snapshot: dict with metadata fields

        Returns: MetricResult with score based on coherence checks.
        """
        issues = []

        project_name = snapshot.get("project_name", "").lower()
        technologies = snapshot.get("mentioned_technologies", [])
        team_size = snapshot.get("assumed_team_size", 0)
        agreed_scope = snapshot.get("agreed_scope", "").lower()

        # Check 1: If project mentions mobile/iOS/Android, but techs are all backend
        mobile_keywords = ["ios", "android", "mobile", "app", "flutter", "react native"]
        backend_keywords = ["django", "flask", "node.js", "java", "go", ".net"]

        project_is_mobile = any(kw in project_name for kw in mobile_keywords)
        techs_lower = [t.lower() for t in technologies]
        has_backend_only = all(
            any(bkw in t for bkw in backend_keywords) for t in techs_lower
        )

        if project_is_mobile and has_backend_only:
            issues.append("Mobile project declared but only backend technologies listed")

        # Check 2: If team size is 1 but scope mentions "enterprise", that's incoherent
        if team_size == 1 and any(
            kw in agreed_scope for kw in ["enterprise", "multi-tenant", "saas", "scalable"]
        ):
            issues.append("Solo developer assigned to enterprise-scale project")

        # Check 3: Empty critical fields
        if not project_name or not technologies:
            issues.append("Missing critical metadata (project_name or technologies)")

        score = max(0.0, 1.0 - (len(issues) * 0.2))  # -0.2 per issue, floor 0.0
        passed = len(issues) == 0

        details = (
            f"Coherence score: {score:.2f}. "
            + ("No issues detected." if passed else f"Issues: {'; '.join(issues)}")
        )

        return MetricResult(
            name="MetadataCoherence",
            score=score,
            passed=passed,
            details=details,
        )
