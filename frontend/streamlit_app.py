import os
from datetime import datetime, timezone

import requests
import streamlit as st

API_BASE_URL = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8000")
STREAM_URL = f"{API_BASE_URL}/api/v1/estimate/stream"

st.set_page_config(
    page_title="Estimador CAG",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 Estimador CAG de proyectos software")
st.caption("Introduce una descripción o transcripción y obtén una estimación técnica.")

if "last_response" not in st.session_state:
    st.session_state.last_response = None

if "last_error" not in st.session_state:
    st.session_state.last_error = None


def stream_from_api(payload: dict, metadata: dict):
    with requests.post(STREAM_URL, json=payload, stream=True, timeout=120) as response:
        response.raise_for_status()
        metadata["model"] = response.headers.get("X-Model", "-")
        metadata["provider"] = response.headers.get("X-Provider", "-")
        metadata["prompt_version"] = response.headers.get("X-Prompt-Version", "-")
        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            if chunk:
                yield chunk


with st.form("estimation_form"):
    project_description = st.text_area(
        "Descripción o transcripción del proyecto",
        height=260,
        placeholder="Pega aquí la transcripción de la reunión o describe el proyecto...",
    )

    col1, col2 = st.columns(2)

    with col1:
        output_format = st.selectbox(
            "Formato de salida",
            options=["markdown", "plain_text"],
            index=0,
        )

    with col2:
        detail_level = st.selectbox(
            "Nivel de detalle",
            options=["low", "medium", "high"],
            index=1,
        )

    submitted = st.form_submit_button("Generar estimación")

if submitted:
    st.session_state.last_response = None
    st.session_state.last_error = None

    payload = {
        "project_description": project_description,
        "output_format": output_format,
        "detail_level": detail_level,
    }

    metadata: dict = {}

    try:
        st.subheader("Estimación generada")
        full_text = st.write_stream(stream_from_api(payload, metadata))

        st.session_state.last_response = {
            "estimation": full_text,
            "model": metadata.get("model", "-"),
            "provider": metadata.get("provider", "-"),
            "prompt_version": metadata.get("prompt_version", "-"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with st.expander("Metadatos"):
            st.write("Modelo:", metadata.get("model"))
            st.write("Proveedor:", metadata.get("provider"))
            st.write("Versión de prompt:", metadata.get("prompt_version"))
            st.write("Timestamp:", st.session_state.last_response["timestamp"])

    except Exception as error:
        st.session_state.last_error = str(error)
        st.error(f"❌ Error llamando al servicio IA: {error}")

else:
    if st.session_state.last_error:
        st.error(f"❌ Error llamando al servicio IA: {st.session_state.last_error}")

    if st.session_state.last_response:
        data = st.session_state.last_response

        st.subheader("Estimación generada")
        st.markdown(data["estimation"])

        with st.expander("Metadatos"):
            st.write("Modelo:", data.get("model"))
            st.write("Proveedor:", data.get("provider"))
            st.write("Versión de prompt:", data.get("prompt_version"))
            st.write("Timestamp:", data.get("timestamp"))
