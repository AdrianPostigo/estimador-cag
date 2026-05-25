import structlog

from app.schemas import EstimationOutput, ProjectMetadata, ACBInfo
from app.services.critic import CriticFeedback, critique_estimation
from app.services.guardrails import parse_and_validate
from app.services.llm_service import stream_with_history

logger = structlog.get_logger(__name__)

MAX_ACB_ITERATIONS = 2


def estimate_with_acb(
    messages: list[dict],
    metadata: ProjectMetadata,
    description: str,
    model_name: str,
) -> tuple[EstimationOutput, str, ACBInfo]:
    """Orchestrate Actor-Critic-Boss flow for iterative estimation refinement.

    Returns: (EstimationOutput, raw_json_string, ACBInfo)
    """
    iteration = 0
    last_feedback: CriticFeedback | None = None
    last_raw_output = ""

    log = logger.bind(model=model_name, acb_enabled=True)

    while iteration < MAX_ACB_ITERATIONS:
        log.info("acb_iteration_start", iteration=iteration, max_iterations=MAX_ACB_ITERATIONS)

        # ACTOR: Generate estimation
        try:
            raw_output = "".join(stream_with_history(messages, model_name=model_name))
            last_raw_output = raw_output
        except Exception as exc:
            log.error("actor_failed", error=str(exc))
            raise

        # GUARDRAILS: Validate schema
        guardrail = parse_and_validate(raw_output)
        if not guardrail.passed:
            log.warning("actor_guardrail_failed", violations=guardrail.violations)
            raise ValueError(f"Guardrail failed: {guardrail.violations}")

        output = guardrail.output

        # CRITIC: Validate coherence
        feedback = critique_estimation(output, metadata, description)
        last_feedback = feedback

        log.info(
            "critic_feedback",
            iteration=iteration,
            has_issues=feedback.has_issues,
            severity=feedback.severity,
            issues_count=len(feedback.issues),
        )

        # If no issues, return
        if not feedback.has_issues:
            log.info("acb_passed", iterations=iteration, severity=feedback.severity)
            return (
                output,
                raw_output,
                ACBInfo(
                    iterations=iteration,
                    re_estimated=(iteration > 0),
                    critic_issues=[],
                ),
            )

        # BOSS: Decide if re-estimate
        if iteration >= MAX_ACB_ITERATIONS - 1:
            # Last iteration, accept as-is
            log.warning(
                "acb_max_iterations_reached",
                iterations=iteration,
                severity=feedback.severity,
                issues=feedback.issues,
            )
            break

        if feedback.severity in ["medium", "high"]:
            # Re-estimate with Critic feedback injected
            critic_prompt = "Issues detected in previous estimation:\n" + "\n".join(
                f"- {issue}" for issue in feedback.issues
            )
            critic_prompt += "\n\nPlease regenerate the estimation addressing these issues."

            # Append feedback to last user message
            messages[-1]["content"] += f"\n\n[Critic Feedback]: {critic_prompt}"

            log.info("boss_re_estimate", iteration=iteration, severity=feedback.severity)
            iteration += 1
        else:
            # Low severity, accept
            log.info("acb_low_severity_accept", iteration=iteration)
            break

    # Final return with issues (after all iterations)
    return output, last_raw_output, ACBInfo(
        iterations=iteration,
        re_estimated=(iteration > 0),
        critic_issues=last_feedback.issues if last_feedback else [],
    )
