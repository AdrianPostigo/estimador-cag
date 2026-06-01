"""
Runner for large attachment stress scenarios.

Executes the same estimation with attachments of increasing sizes (0, 5, 20, 50, 100 KB)
and measures latency, cost, and content recall.
"""

from dataclasses import dataclass
from typing import Optional

import click
import httpx
from tabulate import tabulate

from evals.stress.attachments import ATTACHMENT_SIZES, get_attachment_pdf

DEFAULT_BACKEND_URL = "http://localhost:8000/api/v1"

# Baseline estimation description (fixed across all runs)
BASELINE_DESCRIPTION = """
Necesitamos una plataforma SaaS para gestión de proyectos.
Stack: Next.js, Node.js, PostgreSQL.
Usuarios: 100-500 empresas pequeñas.
Requisitos: dashboard de tareas, colaboración en tiempo real, reportes.
Equipo: 2-3 desarrolladores full-stack.
Timeline: 10-14 semanas.
Presupuesto inicial: 80-120k EUR.
"""


@dataclass
class AttachmentTestResult:
    """Result of running estimation with a specific attachment size."""
    size_label: str
    size_kb: int
    actual_size_kb: float
    attachment_filename: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    attachment_mentioned: bool  # Did summary mention attachment content?
    summary_length: int
    error: Optional[str] = None


def _call_estimate_with_attachment(
    backend_url: str,
    description: str,
    attachment_bytes: bytes,
    attachment_filename: str,
) -> tuple[dict, dict, Optional[str]]:
    """
    Call /estimate endpoint with attachment (via multipart form to sessions endpoint).

    Returns: (output_dict, observables_dict, error_message)
    """
    client = httpx.Client(timeout=120.0)

    try:
        # Create a session first
        response = client.post(f"{backend_url}/sessions")
        response.raise_for_status()
        session_id = response.json()["session_id"]

        # Call estimate with attachment
        files = {
            "description": (None, description),
            "project_type": (None, "web_saas"),
            "detail_level": (None, "medium"),
            "output_format": (None, "phases_table"),
            "attachment": (attachment_filename, attachment_bytes, "application/pdf"),
        }

        response = client.post(
            f"{backend_url}/sessions/{session_id}/estimate",
            files=files,
        )
        response.raise_for_status()

        data = response.json()
        output = data.get("output", {})

        # Extract observables from response
        observables = {
            "tokens_in": 0,  # Placeholder
            "tokens_out": 0,  # Placeholder
            "cost_usd": data.get("cost_usd", 0.0),
            "latency_ms": data.get("latency_ms", 0.0),
        }

        return output, observables, None

    except Exception as e:
        return {}, {}, str(e)
    finally:
        client.close()


def _check_attachment_recall(summary: str, attachment_keywords: list[str]) -> bool:
    """
    Check if attachment content is recalled in summary.

    Look for keywords that are unique to Lorem Ipsum or PDF markers.
    """
    if not summary:
        return False

    # Check for common Lorem Ipsum keywords
    lorem_keywords = ["lorem", "ipsum", "dolor", "sit", "amet", "consectetur"]

    summary_lower = summary.lower()
    for keyword in lorem_keywords:
        if keyword in summary_lower:
            return True

    return False


@click.command()
@click.option(
    "--backend",
    default=DEFAULT_BACKEND_URL,
    help="Backend API base URL",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Verbose output with full summaries",
)
@click.option(
    "--output",
    type=click.Path(),
    help="Save results to CSV file",
)
def run_attachment_stress(backend: str, verbose: bool, output: Optional[str]) -> None:
    """Stress-test large attachment handling with increasing file sizes."""

    click.echo("=" * 100)
    click.echo("STRESS TEST: Large Attachment Handling")
    click.echo("=" * 100 + "\n")

    click.echo(f"Baseline description: {BASELINE_DESCRIPTION[:80]}...\n")
    click.echo("Testing attachment sizes: 0 KB (baseline) → 5 KB → 20 KB → 50 KB → 100 KB\n")
    click.echo("-" * 100)

    results: list[AttachmentTestResult] = []

    for size_label in ["baseline", "small", "medium", "large", "huge"]:
        size_kb = ATTACHMENT_SIZES[size_label]

        click.echo(f"\nTesting {size_label} attachment ({size_kb} KB)...")

        # Generate attachment
        pdf_bytes, filename = get_attachment_pdf(size_label)
        actual_size = len(pdf_bytes) / 1024

        # Call estimation
        output, observables, error = _call_estimate_with_attachment(
            backend,
            BASELINE_DESCRIPTION,
            pdf_bytes,
            f"attachment_{size_label}.pdf",
        )

        if error:
            click.echo(f"  ERROR: {error}", err=True)
            results.append(
                AttachmentTestResult(
                    size_label=size_label,
                    size_kb=size_kb,
                    actual_size_kb=actual_size,
                    attachment_filename=filename,
                    tokens_in=0,
                    tokens_out=0,
                    cost_usd=0.0,
                    latency_ms=0.0,
                    attachment_mentioned=False,
                    summary_length=0,
                    error=error,
                )
            )
            continue

        # Extract data
        summary = output.get("project_summary", "")
        recall = _check_attachment_recall(summary, ["lorem", "ipsum"])

        result = AttachmentTestResult(
            size_label=size_label,
            size_kb=size_kb,
            actual_size_kb=actual_size,
            attachment_filename=filename,
            tokens_in=observables.get("tokens_in", 0),
            tokens_out=observables.get("tokens_out", 0),
            cost_usd=observables.get("cost_usd", 0.0),
            latency_ms=observables.get("latency_ms", 0.0),
            attachment_mentioned=recall,
            summary_length=len(summary),
        )

        results.append(result)

        click.echo(f"  Latency: {result.latency_ms:.1f} ms")
        click.echo(f"  Cost: ${result.cost_usd:.6f}")
        click.echo(f"  Summary length: {result.summary_length} chars")
        click.echo(f"  Attachment mentioned: {result.attachment_mentioned}")

        if verbose and summary:
            click.echo(f"  Summary preview: {summary[:150]}...")

    # Print summary table
    click.echo("\n" + "=" * 100)
    click.echo("SUMMARY")
    click.echo("=" * 100 + "\n")

    summary_table = []
    for result in results:
        summary_table.append(
            {
                "Size Label": result.size_label,
                "Size KB": result.size_kb,
                "Latency (ms)": f"{result.latency_ms:.1f}",
                "Cost (USD)": f"${result.cost_usd:.6f}",
                "Summary Len": result.summary_length,
                "Mentioned": "✓" if result.attachment_mentioned else "✗",
                "Error": result.error or "-",
            }
        )

    click.echo(tabulate(summary_table, headers="keys", tablefmt="grid"))
    click.echo()

    # Analyze curves
    if len(results) > 1 and all(r.error is None for r in results):
        click.echo("CURVE ANALYSIS:")
        click.echo("-" * 100)

        # Latency curve
        latencies = [r.latency_ms for r in results]
        latency_growth = ((latencies[-1] - latencies[0]) / latencies[0] * 100) if latencies[0] > 0 else 0
        click.echo(f"Latency growth (0→100KB): {latency_growth:.1f}%")

        # Cost curve
        costs = [r.cost_usd for r in results]
        cost_growth = ((costs[-1] - costs[0]) / costs[0] * 100) if costs[0] > 0 else 0
        click.echo(f"Cost growth (0→100KB): {cost_growth:.1f}%")

        # Content recall
        mentioned_count = sum(1 for r in results if r.attachment_mentioned)
        click.echo(f"Attachment mentioned in {mentioned_count}/{len(results)} summaries")

    # Save results to CSV if requested
    if output:
        import csv

        with open(output, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "size_label",
                    "size_kb",
                    "actual_size_kb",
                    "latency_ms",
                    "cost_usd",
                    "summary_length",
                    "attachment_mentioned",
                    "error",
                ],
            )
            writer.writeheader()
            for result in results:
                writer.writerow({
                    "size_label": result.size_label,
                    "size_kb": result.size_kb,
                    "actual_size_kb": f"{result.actual_size_kb:.1f}",
                    "latency_ms": f"{result.latency_ms:.1f}",
                    "cost_usd": f"{result.cost_usd:.6f}",
                    "summary_length": result.summary_length,
                    "attachment_mentioned": result.attachment_mentioned,
                    "error": result.error or "",
                })

        click.echo(f"Results saved to {output}")


if __name__ == "__main__":
    run_attachment_stress()
