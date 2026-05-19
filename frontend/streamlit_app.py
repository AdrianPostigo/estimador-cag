import os
from datetime import datetime, timezone

import requests
import streamlit as st

API_BASE_URL = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8000")
API_ESTIMATE_URL = f"{API_BASE_URL}/api/v1/estimate"
API_SESSIONS_URL = f"{API_BASE_URL}/api/v1/sessions"

st.set_page_config(
    page_title="Estimador CAG",
    page_icon="🧠",
    layout="wide",
)

# ── session state init ──────────────────────────────────────────────────────

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "last_response" not in st.session_state:
    st.session_state.last_response = None

if "last_error" not in st.session_state:
    st.session_state.last_error = None

if "turn_count" not in st.session_state:
    st.session_state.turn_count = 0

if "project_metadata" not in st.session_state:
    st.session_state.project_metadata = None


def _ensure_session() -> str:
    if st.session_state.session_id is None:
        resp = requests.post(API_SESSIONS_URL, timeout=10)
        resp.raise_for_status()
        st.session_state.session_id = resp.json()["session_id"]
    return st.session_state.session_id


def _reset_session() -> None:
    st.session_state.session_id = None
    st.session_state.last_response = None
    st.session_state.last_error = None
    st.session_state.turn_count = 0
    st.session_state.project_metadata = None


# ── sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Sesión")

    if st.session_state.session_id:
        st.caption(f"ID: `{st.session_state.session_id[:8]}…`")
        st.caption(f"Turno: {st.session_state.turn_count}")
    else:
        st.caption("Sin sesión activa")

    if st.button("Nueva conversación", use_container_width=True):
        _reset_session()
        st.rerun()

    meta = st.session_state.project_metadata
    if meta:
        st.divider()
        st.subheader("Contexto del proyecto")
        if meta.get("project_name"):
            st.write("**Nombre:**", meta["project_name"])
        if meta.get("assumed_team_size"):
            st.write("**Equipo:**", meta["assumed_team_size"], "personas")
        if meta.get("mentioned_technologies"):
            st.write("**Tecnologías:**", ", ".join(meta["mentioned_technologies"]))
        if meta.get("agreed_scope"):
            with st.expander("Alcance acordado"):
                st.write(meta["agreed_scope"])


# ── helpers ─────────────────────────────────────────────────────────────────

def fetch_estimation(payload: dict, metadata: dict) -> dict:
    response = requests.post(API_ESTIMATE_URL, json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()
    metadata["model"] = data.get("model", "-")
    metadata["provider"] = data.get("provider", "-")
    metadata["prompt_version"] = data.get("prompt_version", "-")
    return data["output"]


def fetch_session_estimation(
    session_id: str,
    form_data: dict,
    attachment,
    metadata: dict,
) -> dict:
    files = {}
    if attachment is not None:
        files["attachment"] = (attachment.name, attachment.getvalue(), attachment.type)

    response = requests.post(
        f"{API_SESSIONS_URL}/{session_id}/estimate",
        data=form_data,
        files=files if files else None,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    metadata["model"] = data.get("model", "-")
    metadata["provider"] = data.get("provider", "-")
    metadata["prompt_version"] = data.get("prompt_version", "-")
    st.session_state.project_metadata = data.get("project_metadata")
    return data["output"]


def render_estimation(output: dict, metadata: dict) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Horas mín", output["total_hours_min"])
    col2.metric("Horas máx", output["total_hours_max"])
    col3.metric("Duración mín", f"{output['duration_weeks_min']} sem")
    col4.metric("Duración máx", f"{output['duration_weeks_max']} sem")

    st.subheader("Resumen")
    st.write(output["project_summary"])

    st.subheader("Desglose de tareas")
    st.dataframe(
        output["tasks"],
        column_config={
            "name": st.column_config.TextColumn("Tarea"),
            "hours_min": st.column_config.NumberColumn("Horas mín"),
            "hours_max": st.column_config.NumberColumn("Horas máx"),
        },
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Equipo recomendado")
    for member in output["recommended_team"]:
        st.markdown(f"- {member}")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Supuestos")
        for assumption in output["assumptions"]:
            st.markdown(f"- {assumption}")

        if output.get("risks"):
            st.subheader("Riesgos")
            for risk in output["risks"]:
                st.markdown(f"- {risk}")

    with col_right:
        if output.get("open_questions"):
            st.subheader("Preguntas abiertas")
            for question in output["open_questions"]:
                st.markdown(f"- {question}")

    with st.expander("Metadatos"):
        st.write("Modelo:", metadata.get("model"))
        st.write("Proveedor:", metadata.get("provider"))
        st.write("Versión de prompt:", metadata.get("prompt_version"))
        st.write("Timestamp:", metadata.get("timestamp"))


# ── main form ────────────────────────────────────────────────────────────────

st.title("🧠 Estimador CAG de proyectos software")
st.caption("Introduce una descripción o transcripción y obtén una estimación técnica estructurada.")

with st.form("estimation_form"):
    description = st.text_area(
        "Descripción o transcripción del proyecto",
        height=260,
        placeholder="Pega aquí la transcripción de la reunión o describe el proyecto...",
        max_chars=2000,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        project_type = st.selectbox(
            "Tipo de proyecto",
            options=["mobile_app", "web_saas", "internal_tool", "data_pipeline"],
            format_func=lambda x: {
                "mobile_app": "App móvil",
                "web_saas": "Web / SaaS",
                "internal_tool": "Herramienta interna",
                "data_pipeline": "Pipeline de datos",
            }[x],
        )

    with col2:
        output_format = st.selectbox(
            "Formato de salida",
            options=["phases_table", "line_items", "narrative"],
            format_func=lambda x: {
                "phases_table": "Tabla por fases",
                "line_items": "Líneas de tarea",
                "narrative": "Narrativo",
            }[x],
        )

    with col3:
        detail_level = st.selectbox(
            "Nivel de detalle",
            options=["summary", "medium", "detailed"],
            index=1,
            format_func=lambda x: {
                "summary": "Resumen",
                "medium": "Medio",
                "detailed": "Detallado",
            }[x],
        )

    attachment = st.file_uploader(
        "Adjuntar documento (opcional)",
        type=["pdf", "docx", "txt"],
        help="El contenido del documento se añade al contexto de la estimación.",
    )

    use_session = st.checkbox(
        "Mantener contexto entre estimaciones (sesión)",
        value=True,
    )

    submitted = st.form_submit_button("Generar estimación")

if submitted:
    st.session_state.last_response = None
    st.session_state.last_error = None

    metadata: dict = {"timestamp": datetime.now(timezone.utc).isoformat()}

    try:
        with st.spinner("Generando estimación..."):
            if use_session:
                session_id = _ensure_session()
                form_data = {
                    "description": description,
                    "project_type": project_type,
                    "output_format": output_format,
                    "detail_level": detail_level,
                }
                output = fetch_session_estimation(session_id, form_data, attachment, metadata)
                st.session_state.turn_count += 1
            else:
                payload = {
                    "description": description,
                    "project_type": project_type,
                    "output_format": output_format,
                    "detail_level": detail_level,
                }
                output = fetch_estimation(payload, metadata)

        st.session_state.last_response = {"output": output, "metadata": metadata}
        st.subheader("Estimación generada")
        render_estimation(output, metadata)

    except Exception as error:
        st.session_state.last_error = str(error)
        st.error(f"Error llamando al servicio IA: {error}")

else:
    if st.session_state.last_error:
        st.error(f"{st.session_state.last_error}")

    if st.session_state.last_response:
        data = st.session_state.last_response
        st.subheader("Estimación generada")
        render_estimation(data["output"], data["metadata"])
