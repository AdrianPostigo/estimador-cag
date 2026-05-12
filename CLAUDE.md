# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Software estimation generator (estimador-cag) that takes a project transcription and returns a time estimate. Uses Claude Sonnet 4.5 for generation, with Spanish prompts and output. Two separate runnable components: a FastAPI backend and a Streamlit frontend.

## Environment Setup

Requires Python 3.11 and [UV](https://docs.astral.sh/uv/) for dependency management.

```bash
# Install dependencies
uv sync

# Set required environment variable
ANTHROPIC_API_KEY=<your-key>   # in .env file
```

## Running the Application

```bash
# Backend (FastAPI + Uvicorn)
uv run uvicorn app.main:app --reload

# Frontend (Streamlit — runs standalone, calls llm_service directly)
uv run streamlit run frontend/streamlit_app.py
```

The FastAPI backend exposes `POST /api/v1/estimate` and `GET /health`. The Streamlit frontend does **not** call the FastAPI backend — it imports and calls `stream_project_estimation()` from `app/services/llm_service.py` directly.

## Architecture

```
app/
  main.py              # FastAPI app, single router mounted at /api/v1
  routers/
    estimations.py     # POST /estimate endpoint, wraps llm_service
  services/
    llm_service.py     # All Claude API logic: prompt building + streaming
  context/
    examples.py        # 4 hardcoded few-shot examples (Spanish)
frontend/
  streamlit_app.py     # Chat UI; imports llm_service directly
```

### Key Design Decisions

- **Two entry points**: FastAPI (`app/`) for API consumers; Streamlit (`frontend/`) for the chat UI. Both share `llm_service.py`.
- **Streaming**: `stream_project_estimation()` uses `client.messages.stream()` and yields text chunks. The Streamlit UI renders these via `st.write_stream()`.
- **Few-shot prompting**: `build_examples_context()` formats 4 static examples from `context/examples.py` and injects them into the system prompt via `build_system_prompt()`.
- **Metrics**: `stream_project_estimation()` returns a dict with `estimation`, `model`, `provider`, `input_tokens`, `output_tokens`, `response_time_seconds`, and `timestamp`. The Streamlit sidebar displays these after each call.
- **Model config**: `MODEL_NAME = "claude-sonnet-4-5"`, `max_tokens=1200`, `temperature=0.3` — all in `llm_service.py`.

### API Contract

`POST /api/v1/estimate`
- Request: `{ "transcription": "string (min 20 chars)" }`
- Response: `{ "estimation": str, "model": str, "provider": str, "timestamp": str }`

The router endpoint is non-streaming (collects the full stream before returning). For streaming behavior, use `stream_project_estimation()` directly.
