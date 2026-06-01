from dataclasses import dataclass, field
from typing import Literal

from app.schemas import EstimationOutput, ProjectMetadata


@dataclass
class CriticFeedback:
    has_issues: bool
    issues: list[str] = field(default_factory=list)
    severity: Literal["low", "medium", "high"] = "low"


def critique_estimation(
    output: EstimationOutput,
    metadata: ProjectMetadata,
    description: str,
) -> CriticFeedback:
    """Validate estimation coherence against context and metadata."""
    issues: list[str] = []

    # Check 1: Team size realistic vs duration
    team_count = len(output.recommended_team)
    if team_count > 0:
        total_hours = (output.total_hours_min + output.total_hours_max) / 2
        hours_per_person = total_hours / team_count
        # Threshold: >300 hours per person = ~7.5 weeks full-time (suspicious)
        if hours_per_person > 320:
            issues.append(
                f"Team size ({team_count}) seems small for estimated hours ({total_hours:.0f}): "
                f"{hours_per_person:.0f} hours/person"
            )

    # Check 2: Duration vs hours realistic
    avg_duration_weeks = (output.duration_weeks_min + output.duration_weeks_max) / 2
    avg_hours = (output.total_hours_min + output.total_hours_max) / 2
    if team_count > 0 and avg_duration_weeks > 0:
        # Expected: 40 hours/week per person
        expected_hours = avg_duration_weeks * 40 * team_count
        hours_diff_pct = abs(expected_hours - avg_hours) / expected_hours if expected_hours > 0 else 0

        if hours_diff_pct > 0.2:  # >20% difference
            issues.append(
                f"Duration/hours mismatch: {avg_duration_weeks:.1f} weeks × {team_count} people "
                f"expects ~{expected_hours:.0f} hours, but got {avg_hours:.0f}"
            )

    # Check 3: Too few risks for complex projects
    total_hours_threshold = 150  # Complex if >150 hours
    if avg_hours > total_hours_threshold and len(output.risks) < 2:
        issues.append(
            f"Large project ({avg_hours:.0f} hours) has only {len(output.risks)} risk(s); "
            "recommend at least 2-3 risks identified"
        )

    # Check 4: Too few assumptions
    if len(output.assumptions) < 1:
        issues.append("No assumptions documented; at least 1 assumption should be stated")

    # Check 5: Metadata coherence (if metadata exists)
    if metadata and metadata.assumed_team_size and metadata.assumed_team_size != team_count:
        issues.append(
            f"Recommended team ({team_count}) differs from previous session assumption "
            f"({metadata.assumed_team_size}); major scope change?"
        )

    # Calculate severity
    if not issues:
        severity: Literal["low", "medium", "high"] = "low"
    elif len(issues) >= 3:
        severity = "high"
    else:
        severity = "medium"

    return CriticFeedback(
        has_issues=len(issues) > 0,
        issues=issues,
        severity=severity,
    )
