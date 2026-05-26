"""
Synthetic multi-turn scenarios for stress-testing metadata stability and cost tracking.

Three profiles:
1. Growing Project: coherent requirements accumulate across turns
2. Pivoting Project: stack changes at turn 5
3. Contradicting Project: conflicting budget claims at different turns
"""

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Fact:
    """A fact that should be remembered across turns."""
    statement: str
    turn_introduced: int
    metric_name: str  # e.g., "project_name", "mentioned_technologies", "budget"


@dataclass
class ScenarioProfile:
    """A multi-turn scenario profile with fact-tracking."""
    name: str
    description: str
    turns: list[str]  # Description for each turn
    facts_tracker: list[Fact]  # Facts introduced and their expected lifetimes
    expected_metadata_drift: dict[str, str | None]  # Field -> expected value at final turn


# ============================================================================
# Profile 1: Growing Project
# ============================================================================

GROWING_PROJECT_TURNS = [
    # Turn 1: Basic SaaS with simple auth
    """
    Necesitamos una plataforma SaaS para gestión de tareas.
    Stack: Next.js + TypeScript frontend, Node.js/Express backend, PostgreSQL.
    Autenticación simple con email/password.
    Equipo: 3 desarrolladores, presupuesto 60k€.
    Timeline: 12 semanas.
    """,
    # Turn 2: Multi-tenant requirement
    """
    Actualizamos requisitos: necesitamos multi-tenant (cada empresa en su base de datos separada).
    Mismo stack, pero ahora con isolación de datos robusta.
    Equipo sigue siendo 3 developers.
    """,
    # Turn 3: Audit logging
    """
    Agregamos auditoría completa: cada acción debe loguear usuario, timestamp, cambios.
    Cumplimiento GDPR.
    """,
    # Turn 4: CSV exports
    """
    Los clientes necesitan exportar sus tareas a CSV, Excel, PDF.
    """,
    # Turn 5: Analytics
    """
    Dashboard con analítica de uso: qué tareas toman más tiempo, por qué.
    """,
]

GROWING_PROJECT_FACTS = [
    Fact("Plataforma SaaS para gestión de tareas", 1, "project_name"),
    Fact("Stack: Next.js + Node.js + PostgreSQL", 1, "mentioned_technologies"),
    Fact("Autenticación simple (email/password)", 1, "agreed_scope"),
    Fact("Multi-tenant con isolación de datos", 2, "mentioned_technologies"),
    Fact("Auditoría GDPR-compliant", 3, "mentioned_technologies"),
    Fact("Exportación (CSV, Excel, PDF)", 4, "mentioned_technologies"),
    Fact("Dashboard analítico", 5, "mentioned_technologies"),
]

GROWING_PROJECT = ScenarioProfile(
    name="growing_project",
    description="Project requirements grow coherently; measures metadata accumulation and cost curve",
    turns=GROWING_PROJECT_TURNS,
    facts_tracker=GROWING_PROJECT_FACTS,
    expected_metadata_drift={
        "project_name": "Plataforma SaaS para gestión de tareas",
        "mentioned_technologies": "should contain Next.js, Node.js, PostgreSQL, multi-tenant, audit, export, analytics",
        "agreed_scope": "should reflect cumulative scope after turn 5",
    },
)


# ============================================================================
# Profile 2: Pivoting Project
# ============================================================================

PIVOTING_PROJECT_TURNS = [
    # Turn 1: Initial iOS app idea
    """
    Quiero una app iOS nativa para fitness tracking.
    Stack: Swift, CoreData local, Apple HealthKit integration.
    1-2 desarrolladores iOS.
    Timeline: 8 semanas.
    """,
    # Turn 2: Refinements
    """
    Detalles: GPS tracking, heart rate sensors, offline support.
    """,
    # Turn 3: Apple Watch
    """
    Agregamos watchOS app para companion experience.
    """,
    # Turn 4: Final tweaks
    """
    UI refinements, onboarding flow, push notifications.
    """,
    # Turn 5: **PIVOT** — Switch to cross-platform
    """
    Cambiamos planes. Necesitamos iOS + Android con código compartido.
    Usaremos Flutter en lugar de Swift nativo.
    Backend: Node.js + Firebase.
    Equipo: 2 Flutter devs + 1 backend.
    """,
]

PIVOTING_PROJECT_FACTS = [
    Fact("App iOS nativa para fitness tracking", 1, "project_name"),
    Fact("Stack: Swift + CoreData + HealthKit", 1, "mentioned_technologies"),
    Fact("GPS tracking, heart rate sensors", 2, "agreed_scope"),
    Fact("watchOS companion app", 3, "agreed_scope"),
    Fact("Pivoted a Flutter + Firebase", 5, "mentioned_technologies"),
]

PIVOTING_PROJECT = ScenarioProfile(
    name="pivoting_project",
    description="Project pivot at turn 5 (Swift→Flutter); measures if mentioned_technologies replaces or accumulates",
    turns=PIVOTING_PROJECT_TURNS,
    facts_tracker=PIVOTING_PROJECT_FACTS,
    expected_metadata_drift={
        "project_name": "could be 'fitness tracking app' or variant",
        "mentioned_technologies": "should replace Swift with Flutter; question: does it keep both or only Flutter?",
        "agreed_scope": "should reflect cross-platform + backend",
    },
)


# ============================================================================
# Profile 3: Contradicting Project
# ============================================================================

CONTRADICTING_PROJECT_TURNS = [
    # Turn 1: Initial scope
    """
    Platform SaaS para e-learning.
    Cursos con videos, quizzes, certificados.
    Stack: Django REST + React + S3.
    Presupuesto inicial: 40k€.
    Equipo: 2 developers.
    Timeline: 10 semanas.
    """,
    # Turn 2: Small enhancements
    """
    Agregamos foro de comunidad integrado.
    """,
    # Turn 3: Budget increase
    """
    El presupuesto puede crecer a 60k€ si es necesario.
    """,
    # Turn 4: Feature expansion
    """
    Necesitamos live classes (video conferencing).
    """,
    # Turn 5: Team grows
    """
    Contratamos 1 dev más. Equipo: 3 developers.
    """,
    # Turn 6: Scope creep
    """
    Marketplace donde instructores venden cursos.
    Gamification (badges, leaderboards).
    """,
    # Turn 7: More budget
    """
    Presupuesto extendido a 70k€.
    """,
    # Turn 8: **CONTRADICTION** — Different budget claim
    """
    Wait, se nos comunicó que tenemos sólo 30k€ para gastos de desarrollo.
    Necesitamos priorizar qué se hace.
    """,
]

CONTRADICTING_PROJECT_FACTS = [
    Fact("E-learning SaaS platform", 1, "project_name"),
    Fact("Stack: Django REST + React + S3", 1, "mentioned_technologies"),
    Fact("Presupuesto 40k€", 1, "agreed_scope"),
    Fact("Presupuesto puede ser 60k€", 3, "agreed_scope"),
    Fact("Live classes (video conferencing)", 4, "mentioned_technologies"),
    Fact("Marketplace + gamification", 6, "agreed_scope"),
    Fact("Presupuesto 70k€", 7, "agreed_scope"),
    Fact("Presupuesto 30k€ (CONTRADICTION)", 8, "agreed_scope"),
]

CONTRADICTING_PROJECT = ScenarioProfile(
    name="contradicting_project",
    description="Budget contradictions at turns 3, 7, 8; measures which is preserved in metadata",
    turns=CONTRADICTING_PROJECT_TURNS,
    facts_tracker=CONTRADICTING_PROJECT_FACTS,
    expected_metadata_drift={
        "project_name": "E-learning platform",
        "mentioned_technologies": "should include all tech stacks mentioned",
        "agreed_scope": "question: which budget wins? last one (30k€) or highest (70k€)?",
    },
)


# ============================================================================
# Scenario Execution
# ============================================================================

@dataclass
class TurnResult:
    """Result of a single turn estimation."""
    turn_number: int
    description: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: float
    project_name: str | None
    mentioned_technologies: list[str]
    agreed_scope: str | None
    total_hours_max: int
    facts_recalled: list[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    """Result of running a full scenario."""
    profile: ScenarioProfile
    num_turns: int
    turns: list[TurnResult]
    total_cost_usd: float
    metadata_drift_report: dict[str, str]


def run_scenario(
    profile: ScenarioProfile,
    num_turns: int,
    estimate_callback: Callable[[str], tuple[dict, dict]],
) -> ScenarioResult:
    """
    Run a scenario for N turns using provided estimation callback.

    estimate_callback returns: (EstimationOutput dict, turn_observables dict)
    """
    turns_results = []
    cumulative_cost = 0.0
    session_id = None  # Will be created on first turn

    for turn_idx in range(1, num_turns + 1):
        if turn_idx > len(profile.turns):
            break

        description = profile.turns[turn_idx - 1]

        # Call estimation (placeholder)
        # In real scenario, this would call the actual API
        output, observables = estimate_callback(description)

        # Track result
        turn_result = TurnResult(
            turn_number=turn_idx,
            description=description[:100] + "...",
            tokens_in=observables.get("tokens_in", 0),
            tokens_out=observables.get("tokens_out", 0),
            cost_usd=observables.get("cost_usd", 0.0),
            latency_ms=observables.get("latency_ms", 0.0),
            project_name=output.get("project_name"),
            mentioned_technologies=output.get("mentioned_technologies", []),
            agreed_scope=output.get("agreed_scope"),
            total_hours_max=output.get("total_hours_max", 0),
        )

        cumulative_cost += turn_result.cost_usd
        turns_results.append(turn_result)

    # Analyze metadata drift
    drift_report = {
        "initial_project_name": turns_results[0].project_name if turns_results else None,
        "final_project_name": turns_results[-1].project_name if turns_results else None,
        "project_name_stable": (
            turns_results[0].project_name == turns_results[-1].project_name
            if turns_results
            else None
        ),
        "technology_count_growth": (
            len(turns_results[-1].mentioned_technologies)
            - len(turns_results[0].mentioned_technologies)
            if turns_results
            else 0
        ),
    }

    return ScenarioResult(
        profile=profile,
        num_turns=num_turns,
        turns=turns_results,
        total_cost_usd=cumulative_cost,
        metadata_drift_report=drift_report,
    )


# ============================================================================
# Scenario Registry
# ============================================================================

SCENARIOS = {
    "growing": GROWING_PROJECT,
    "pivoting": PIVOTING_PROJECT,
    "contradicting": CONTRADICTING_PROJECT,
}

SCENARIO_TURN_COUNTS = [1, 3, 6, 10, 20]
