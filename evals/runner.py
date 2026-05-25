import json
from enum import Enum
from typing import Literal

import click
import structlog
from tabulate import tabulate

from app.prompts.loader import render_estimation_prompt
from app.schemas import EstimationRequest, DetailLevel, OutputFormat, ProjectType
from app.services.actor_critic_boss import estimate_with_acb
from app.services.llm_service import stream_with_history
from app.services.guardrails import parse_and_validate
from app.services.tier_scoring import get_model_for_tier, score_input
from evals.metrics import SchemaAdherenceMetric, CostBoundsMetric, ContentRecallMetric

logger = structlog.get_logger(__name__)


class Mode(str, Enum):
    ACTOR = "actor"
    ACB = "acb"


def run_case_actor(case: dict, model_name: str) -> dict:
    """Run a single case in actor mode (no ACB iteration)."""
    request = EstimationRequest(
        description=case["description"],
        project_type=ProjectType(case["project_type"]),
        detail_level=DetailLevel(case["detail_level"]),
        output_format=OutputFormat(case["output_format"]),
    )

    system_prompt, user_prompt = render_estimation_prompt(request=request, version="v1")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        raw_output = "".join(stream_with_history(messages, model_name=model_name))
        guardrail = parse_and_validate(raw_output)
        if guardrail.passed:
            return {"success": True, "output": guardrail.output}
        else:
            return {"success": False, "error": f"Guardrail failed: {guardrail.violations}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_case_acb(case: dict, model_name: str) -> dict:
    """Run a single case in ACB mode (with iteration)."""
    request = EstimationRequest(
        description=case["description"],
        project_type=ProjectType(case["project_type"]),
        detail_level=DetailLevel(case["detail_level"]),
        output_format=OutputFormat(case["output_format"]),
    )

    system_prompt, user_prompt = render_estimation_prompt(request=request, version="v1")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        output, raw_output, acb_info = estimate_with_acb(
            messages=messages,
            metadata=None,
            description=case["description"],
            model_name=model_name,
        )
        return {
            "success": True,
            "output": output,
            "acb_iterations": acb_info.iterations,
            "acb_re_estimated": acb_info.re_estimated,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@click.command()
@click.option(
    "--mode",
    type=click.Choice(["actor", "acb"]),
    default="acb",
    help="Execution mode: actor (no iteration) or acb (with Actor-Critic-Boss)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Print case-by-case results",
)
@click.option(
    "--dataset",
    type=click.Path(exists=True),
    default="evals/golden_dataset.json",
    help="Path to golden dataset JSON",
)
def run_evals(mode: str, verbose: bool, dataset: str) -> None:
    """Run evaluation suite on golden dataset."""

    with open(dataset) as f:
        data = json.load(f)
        cases = data.get("cases", [])

    if not cases:
        click.echo("No cases found in dataset")
        return

    metrics = [
        SchemaAdherenceMetric(),
        CostBoundsMetric(),
        ContentRecallMetric(),
    ]

    # Results: {metric_name: [{case_id, passed}, ...]}
    results: dict[str, list[dict]] = {m.__class__.__name__: [] for m in metrics}

    click.echo(f"Running {len(cases)} cases in {mode.upper()} mode...\n")

    for i, case in enumerate(cases, 1):
        case_id = case["id"]

        # Run case
        if mode == "actor":
            # Detect tier and get model
            tier_scoring = score_input(case["description"])
            model_name = get_model_for_tier(tier_scoring["tier"])
            result = run_case_actor(case, model_name)
        else:  # acb
            tier_scoring = score_input(case["description"])
            model_name = get_model_for_tier(tier_scoring["tier"])
            result = run_case_acb(case, model_name)

        if not result["success"]:
            if verbose:
                click.echo(f"[{i:2d}] {case_id}: ERROR - {result['error']}")
            # Mark all metrics as failed
            for metric in metrics:
                results[metric.__class__.__name__].append({"case_id": case_id, "passed": False})
            continue

        output = result["output"]

        # Evaluate metrics
        for metric in metrics:
            passed = metric.evaluate(output, case)
            results[metric.__class__.__name__].append({"case_id": case_id, "passed": passed})

            if verbose:
                status = "PASS" if passed else "FAIL"
                click.echo(f"[{i:2d}] {case_id:10} - {metric.__class__.__name__:20}: {status}")

        # Log ACB info if available
        if mode == "acb" and "acb_iterations" in result:
            logger.info(
                "eval_case_complete",
                case_id=case_id,
                iterations=result["acb_iterations"],
                re_estimated=result["acb_re_estimated"],
            )

    # Report summary
    click.echo("\n" + "=" * 60)
    click.echo("EVALUATION SUMMARY")
    click.echo("=" * 60 + "\n")

    summary = []
    for metric_name, evals in results.items():
        pass_count = sum(1 for e in evals if e["passed"])
        total = len(evals)
        pass_rate = (pass_count / total * 100) if total > 0 else 0.0

        summary.append(
            {
                "Metric": metric_name,
                "Passed": pass_count,
                "Total": total,
                "Pass Rate": f"{pass_rate:.1f}%",
            }
        )

    click.echo(tabulate(summary, headers="keys", tablefmt="grid"))
    click.echo()

    # Overall pass rate
    all_passed = sum(1 for m_evals in results.values() for e in m_evals if e["passed"])
    all_total = sum(len(m_evals) for m_evals in results.values())
    overall_rate = (all_passed / all_total * 100) if all_total > 0 else 0.0

    click.echo(f"Overall Pass Rate: {overall_rate:.1f}% ({all_passed}/{all_total})")


if __name__ == "__main__":
    run_evals()
