import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

from app.services.llm_service import (
    MODEL_NAME,
    PROVIDER,
    build_examples_context,
    build_system_prompt,
    stream_project_estimation,
)

st.set_page_config(
    page_title="Estimador CAG",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 Estimador CAG de proyectos software")
st.caption("Introduce una transcripción de reunión y obtén una estimación técnica en streaming.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hola. Pega una transcripción de reunión y generaré una estimación técnica.",
        }
    ]

if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = {
        "model": MODEL_NAME,
        "provider": PROVIDER,
        "input_tokens": None,
        "output_tokens": None,
        "response_time_seconds": None,
    }

with st.sidebar:
    st.header("⚙️ Contexto CAG")

    st.subheader("System prompt activo")
    st.text_area(
        label="Prompt",
        value=build_system_prompt(),
        height=300,
        disabled=True,
        label_visibility="collapsed",
    )

    st.subheader("Contexto estático inyectado")
    st.text_area(
        label="Ejemplos CAG",
        value=build_examples_context(),
        height=300,
        disabled=True,
        label_visibility="collapsed",
    )

    st.subheader("Métricas última llamada")

    metrics = st.session_state.last_metrics

    st.metric("Modelo", metrics.get("model") or "-")
    st.metric("Proveedor", metrics.get("provider") or "-")
    st.metric("Input tokens", metrics.get("input_tokens") or "-")
    st.metric("Output tokens", metrics.get("output_tokens") or "-")

    response_time = metrics.get("response_time_seconds")
    st.metric(
        "Tiempo respuesta",
        f"{response_time:.2f}s" if response_time is not None else "-",
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("Pega aquí la transcripción de la reunión...")

if user_input:
    st.session_state.messages.append(
        {"role": "user", "content": user_input}
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        try:
            call_metrics = {}

            start_time = time.perf_counter()

            streamed_response = st.write_stream(
                stream_project_estimation(
                    meeting_transcription=user_input,
                    metrics=call_metrics,
                )
            )

            end_time = time.perf_counter()

            call_metrics["response_time_seconds"] = end_time - start_time

            st.session_state.last_metrics = call_metrics

        except Exception as e:
            streamed_response = f"❌ Error generando estimación:\n\n{str(e)}"
            st.error(streamed_response)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": streamed_response,
        }
    )

    st.rerun()