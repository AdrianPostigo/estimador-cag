"""
Runner for synthetic multi-turn stress scenarios.

Executes scenarios against the backend API and collects observables.
"""

import json
from typing import Callable

import click
import httpx
from tabulate import tabulate

from evals.stress.scenarios import (
    SCENARIOS,
    SCENARIO_TURN_COUNTS,
    ScenarioResult,
    run_scenario,
)

DEFAULT_BACKEND_URL = "http://localhost:8000/api/v1"


def create_estimate_callback(backend_url: str) -> Callable:
    """Create an estimation callback that calls the backend API."""

    def estimate(description: str) -> tuple[dict, dict]:
        """Call /estimate and return (output, observables)."""
        client = httpx.Client(timeout=60.0)

        try:
            response = client.post(
                f"{backend_url}/estimate",
                json={
                    "description": description,
                    "project_type": "web_saas",
                    "detail_level": "medium",
                    "output_format": "phases_table",
                },
            )
            response.raise_for_status()

            data = response.json()
            output = data.get("output", {})

            # Extract observables from response and logs
            # For now, use placeholder values
            observables = {
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0.0,
                "latency_ms": 0.0,
                "cache_hit_kind": "none",
            }

            return output, observables
        except Exception as e:
            click.echo(f"Error calling estimate: {e}", err=True)
            raise
        finally:
            client.close()

    return estimate


@click.command()
@click.option(
    "--scenario",
    type=click.Choice(["growing", "pivoting", "contradicting", "all"]),
    default="all",
    help="Scenario profile to run",
)
@click.option(
    "--turns",
    type=int,
    default=0,
    help="Max turns (0 = use [1,3,6,10,20])",
)
@click.option(
    "--backend",
    default=DEFAULT_BACKEND_URL,
    help="Backend API base URL",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Verbose output (turn-by-turn details)",
)
def run_stress_scenarios(
    scenario: str,
    turns: int,
    backend: str,
    verbose: bool,
) -> None:
    """Run synthetic multi-turn scenarios to stress-test metadata stability."""

    click.echo("=" * 80)
    click.echo("STRESS TEST: Synthetic Multi-Turn Scenarios")
    click.echo("=" * 80 + "\n")

    # Determine which scenarios to run
    scenarios_to_run = (
        SCENARIOS.items() if scenario == "all" else [(scenario, SCENARIOS[scenario])]
    )

    # Determine turn counts
    turn_counts = [turns] if turns > 0 else SCENARIO_TURN_COUNTS

    # Create estimation callback
    estimate_callback = create_estimate_callback(backend)

    results: list[ScenarioResult] = []

    for scenario_name, scenario_profile in scenarios_to_run:
        click.echo(f"\nScenario: {scenario_name.upper()}")
        click.echo(f"Description: {scenario_profile.description}")
        click.echo("-" * 80)

        for turn_count in turn_counts:
            if turn_count > len(scenario_profile.turns):
                click.echo(f"  Skipping {turn_count} turns (not enough turns in scenario)")
                continue

            click.echo(f"\n  Running {turn_count} turns...")

            try:
                result = run_scenario(
                    scenario_profile,
                    turn_count,
                    estimate_callback,
                )
                results.append(result)

                # Print summary
                click.echo(f"    Total cost: ${result.total_cost_usd:.6f}")
                click.echo(
                    f"    Metadata drift: {result.metadata_drift_report.get('project_name_stable')}"
                )

                if verbose:
                    for turn in result.turns:
                        click.echo(
                            f"      Turn {turn.turn_number}: "
                            f"{turn.cost_usd:.6f}$ | "
                            f"project={turn.project_name} | "
                            f"techs={len(turn.mentioned_technologies)}"
                        )

            except Exception as e:
                click.echo(f"    ERROR: {e}", err=True)

    # Aggregate results
    click.echo("\n" + "=" * 80)
    click.echo("SUMMARY")
    click.echo("=" * 80 + "\n")

    if results:
        summary_table = []
        for result in results:
            summary_table.append(
                {
                    "Scenario": result.profile.name,
                    "Turns": result.num_turns,
                    "Total Cost": f"${result.total_cost_usd:.6f}",
                    "Project Name Stable": result.metadata_drift_report.get(
                        "project_name_stable", "?"
                    ),
                    "Tech Growth": result.metadata_drift_report.get(
                        "technology_count_growth", "?"
                    ),
                }
            )

        click.echo(tabulate(summary_table, headers="keys", tablefmt="grid"))
        click.echo()


if __name__ == "__main__":
    run_stress_scenarios()
