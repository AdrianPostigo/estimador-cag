# tests/prompts/test_estimation_v1.py

from pydantic import BaseModel

from app.prompts.loader import render_estimation_prompt


class DummyEstimationRequest(BaseModel):
    description: str
    project_type: str = "web_saas"
    output_format: str = "narrative"
    detail_level: str = "summary"


def test_user_prompt_includes_description_inside_project_description_block():
    request = DummyEstimationRequest(
        description="Cliente necesita una app interna para gestionar incidencias.",
        output_format="narrative",
        detail_level="summary",
    )

    _, user = render_estimation_prompt(request=request, version="v1")

    assert "<project_description>" in user
    assert "Cliente necesita una app interna para gestionar incidencias." in user
    assert "</project_description>" in user


def test_system_prompt_includes_phases_table_format_only_when_requested():
    phases_request = DummyEstimationRequest(
        description="Proyecto válido con descripción suficiente.",
        output_format="phases_table",
        detail_level="summary",
    )

    narrative_request = DummyEstimationRequest(
        description="Proyecto válido con descripción suficiente.",
        output_format="narrative",
        detail_level="summary",
    )

    phases_system, _ = render_estimation_prompt(
        request=phases_request,
        version="v1",
    )
    narrative_system, _ = render_estimation_prompt(
        request=narrative_request,
        version="v1",
    )

    assert "agrupa en fases" in phases_system
    assert "agrupa en fases" not in narrative_system
    assert "bloques funcionales de alto nivel" in narrative_system


def test_system_prompt_includes_phase_assumptions_only_when_detailed():
    detailed_request = DummyEstimationRequest(
        description="Proyecto válido con descripción suficiente.",
        output_format="narrative",
        detail_level="detailed",
    )

    summary_request = DummyEstimationRequest(
        description="Proyecto válido con descripción suficiente.",
        output_format="narrative",
        detail_level="summary",
    )

    detailed_system, _ = render_estimation_prompt(
        request=detailed_request,
        version="v1",
    )
    summary_system, _ = render_estimation_prompt(
        request=summary_request,
        version="v1",
    )

    assert "nivel de detalle: alto" in detailed_system.lower()
    assert "mínimo 5 riesgos" in detailed_system.lower()
    assert "resumido" in summary_system.lower()
    assert "máximo 2-3" in summary_system.lower()