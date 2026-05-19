"""Integration tests for multi-turn session endpoints.

Tests mock litellm.completion so no real API key is needed.
"""

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# A minimal EstimationOutput that passes all guardrails.
_VALID_OUTPUT = {
    "project_summary": "Aplicación web para gestión de tareas de equipos remotos.",
    "assumptions": ["Autenticación con email/contraseña.", "Sin app móvil nativa."],
    "tasks": [
        {"name": "Análisis y diseño", "hours_min": 8, "hours_max": 16},
        {"name": "Backend API", "hours_min": 24, "hours_max": 40},
        {"name": "Frontend", "hours_min": 24, "hours_max": 40},
        {"name": "Testing", "hours_min": 8, "hours_max": 16},
    ],
    "total_hours_min": 64,
    "total_hours_max": 112,
    "recommended_team": ["1 desarrollador full-stack senior", "1 QA"],
    "duration_weeks_min": 4,
    "duration_weeks_max": 6,
    "risks": ["Cambios de alcance tardíos pueden retrasar la entrega."],
    "open_questions": ["¿Se requiere integración con Slack?"],
}

_VALID_JSON = json.dumps(_VALID_OUTPUT)


def _make_mock_chunk(content: str | None = None, usage=None):
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = content
    chunk.usage = usage
    return chunk


def _mock_completion(**_kwargs):
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 200

    chunks = list(_VALID_JSON)
    mock_chunks = [_make_mock_chunk(c) for c in chunks]
    mock_chunks.append(_make_mock_chunk(None, usage))
    return iter(mock_chunks)


@pytest.fixture()
def mock_llm():
    with patch("litellm.completion", side_effect=_mock_completion):
        yield


@pytest.fixture()
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Test 1: two-turn session updates project_metadata ───────────────────────

async def test_two_turn_session_updates_metadata(client, mock_llm):
    # Create session
    resp = await client.post("/api/v1/sessions")
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    form = {
        "description": "Necesitamos una app web para gestionar tareas de equipos remotos con Django y React.",
        "project_type": "web_saas",
        "detail_level": "medium",
        "output_format": "phases_table",
    }

    # First turn
    resp1 = await client.post(f"/api/v1/sessions/{session_id}/estimate", data=form)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["output"]["project_summary"] != ""
    assert data1["project_metadata"] is not None

    # Second turn — refinement
    form2 = {**form, "description": "Añadir también notificaciones por email y exportación PDF."}
    resp2 = await client.post(f"/api/v1/sessions/{session_id}/estimate", data=form2)
    assert resp2.status_code == 200
    data2 = resp2.json()
    meta2 = data2["project_metadata"]
    assert meta2 is not None
    # assumed_team_size should be derived from recommended_team length
    assert meta2["assumed_team_size"] == len(data2["output"]["recommended_team"])


# ── Test 2: PDF attachment content reaches the LLM messages ─────────────────

async def test_pdf_attachment_text_injected(client, mock_llm):
    resp = await client.post("/api/v1/sessions")
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    # Build a minimal valid PDF in memory using raw PDF syntax
    pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 100 700 Td (Requisitos del proyecto) Tj ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000360 00000 n
trailer<</Size 6/Root 1 0 R>>
startxref
441
%%EOF"""

    captured_messages: list = []

    def capturing_completion(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return _mock_completion(**kwargs)

    with patch("litellm.completion", side_effect=capturing_completion):
        form = {
            "description": "Sistema de gestión de proyectos internos para una empresa de 50 empleados.",
            "project_type": "internal_tool",
            "detail_level": "medium",
            "output_format": "line_items",
        }
        files = {"attachment": ("spec.pdf", io.BytesIO(pdf_content), "application/pdf")}
        resp = await client.post(
            f"/api/v1/sessions/{session_id}/estimate",
            data=form,
            files=files,
        )

    assert resp.status_code == 200
    user_messages = [m for m in captured_messages if m["role"] == "user"]
    assert len(user_messages) >= 1
    last_user = user_messages[-1]["content"]
    assert "spec.pdf" in last_user


# ── Test 3: sliding window caps at MAX_TURNS pairs ──────────────────────────

async def test_sliding_window_caps_history(client, mock_llm):
    from app.sessions import MAX_TURNS, get_session

    resp = await client.post("/api/v1/sessions")
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    form = {
        "project_type": "web_saas",
        "detail_level": "summary",
        "output_format": "narrative",
    }

    for i in range(MAX_TURNS + 2):
        turn_form = {
            **form,
            "description": f"Turno {i + 1}: plataforma SaaS para gestión de inventario en tiempo real con Python y Vue.",
        }
        resp = await client.post(f"/api/v1/sessions/{session_id}/estimate", data=turn_form)
        assert resp.status_code == 200

    session = get_session(session_id)
    assert session is not None
    assert session.history.turn_count <= MAX_TURNS
