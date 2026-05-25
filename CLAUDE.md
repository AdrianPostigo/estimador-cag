# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Software estimation generator (estimador-cag): takes a typed project description and returns a structured time estimate. Uses Claude Sonnet 4.5 via LiteLLM. Output and prompts are in Spanish. Two separate runnable components: a FastAPI backend and a Streamlit frontend that calls the backend via HTTP.

Supports multi-turn sessions: conversation history with a sliding window (MAX_TURNS=6), heuristic project metadata accumulation across turns, and file attachment support (PDF, DOCX, TXT).

## Environment Setup

Requires Python 3.11 and [UV](https://docs.astral.sh/uv/) for dependency management.

```bash
uv sync
```

Required in `.env`:
```
ANTHROPIC_API_KEY=<your-key>
LLM_MODEL=anthropic/claude-sonnet-4-5   # optional — change provider/model here
```

`LLM_MODEL` uses LiteLLM format: `anthropic/claude-sonnet-4-5`, `openai/gpt-4o`, etc. Defaults to `anthropic/claude-sonnet-4-5` if not set.

## Running the Application

```bash
# Backend (FastAPI + Uvicorn)
uv run python -m uvicorn app.main:app --reload  # → http://localhost:8000

# Frontend (Streamlit — calls the backend via HTTP)
uv run streamlit run frontend/streamlit_app.py  # → http://localhost:8501

# Tests (no API key needed — LLM is mocked)
uv run python -m pytest tests/ -v
```

Both backend and frontend must be running for the UI to work.

## Architecture

```
app/
  main.py                        # FastAPI app; mounts estimations + sessions routers at /api/v1
  config.py                      # MODEL_NAME and PROVIDER read from LLM_MODEL env var
  schemas.py                     # Pydantic domain models: EstimationRequest/Response, enums, ProjectMetadata
  observability.py               # configure_logging() — structlog setup (ConsoleRenderer, ISO timestamps)
  sessions.py                    # In-memory session store: ConversationHistory (sliding window), Session
  routers/
    estimations.py               # POST /estimate (blocking JSON) and POST /estimate/stream (StreamingResponse)
    sessions.py                  # POST /sessions and POST /sessions/{session_id}/estimate (multipart)
  services/
    llm_service.py               # LiteLLM wrapper: _stream_completion(), stream_project_estimation(), stream_with_history()
    llm_wrapper.py               # Observable LLM metrics: MODEL_COSTS, calculate_cost(), create_metrics()
    estimation_service.py        # Unified estimation: estimate_conversational() with turn-level observables
    guardrails.py                # parse_and_validate(): JSON extract + Pydantic EstimationOutput validation
    attachments.py               # extract_text(): pypdf for PDF, python-docx for DOCX, UTF-8 for TXT
    metadata.py                  # update_metadata(): heuristic extraction from EstimationOutput (no extra LLM call)
  prompts/
    loader.py                    # render_estimation_prompt(request, version, project_metadata)
    estimation/v1/
      system.j2                  # System prompt: conditionals on output_format/detail_level/project_type + metadata block
      user.j2                    # User prompt — injects {{ request.description }}
      examples.j2                # Few-shot JSON examples included via {% include %}
frontend/
  streamlit_app.py               # Form UI: session management, file uploader, sidebar metadata, Nueva conversación
tests/
  test_sessions.py               # 3 integration tests: two-turn metadata, PDF attachment, sliding window cap
  prompts/
    test_estimation_v1.py        # Prompt rendering unit tests
```

## Key Design Decisions

**LiteLLM as provider abstraction** — `llm_service.py` never imports `anthropic` or `openai` directly. The model is configured via `LLM_MODEL` env var. Switching providers requires no code changes.

**Exact-match cache** — `_cache: dict[str, dict]` in `llm_service.py`, keyed by `SHA-256(system_prompt + user_prompt)`. Changing any request parameter produces a different key. The session endpoint bypasses this cache because messages change every turn.

**Streaming architecture** — `_stream_completion(messages)` is the single generator that calls LiteLLM. `stream_project_estimation()` wraps it with cache logic. `stream_with_history()` wraps it for multi-turn. FastAPI wraps generators in `StreamingResponse`. The non-streaming `/estimate` endpoint collects the full generator with `"".join(...)`.

**Guardrails** — `parse_and_validate()` in `guardrails.py`: strips markdown fences, `json.loads()`, then `EstimationOutput.model_validate()`. Violations come directly from Pydantic with field paths. The `/estimate` endpoint raises HTTP 422 on failure; the session endpoint also raises 422. The `/estimate/stream` endpoint logs violations but cannot block mid-stream.

**Jinja2 versioned prompts** — templates in `app/prompts/estimation/v1/`. Adding a v2 prompt requires only a new directory. `system.j2` uses `{% if request.project_type %}`, `{% if request.output_format %}`, `{% if request.detail_level %}`, and `{% if project_metadata %}` blocks. `loader.py` passes `project_metadata` through to Jinja2 render.

**Sessions and sliding window** — `ConversationHistory` uses `deque(maxlen=MAX_TURNS * 2)` (one entry per role per turn). `to_messages_list(system_prompt)` prepends the system message. History is stored in-memory in `_sessions: dict[str, Session]` — restarting the server clears all sessions.

**Attachment support** — `attachments.py` dispatches by filename extension: `.pdf` → `pypdf.PdfReader`, `.docx` → `python-docx`, else UTF-8. Extracted text is appended to the user message as `"\n\n--- adjunto: {filename} ---\n{text}"` before being added to the conversation history.

**Heuristic metadata** — `update_metadata()` extracts `agreed_scope` from `project_summary`, `assumed_team_size` from `len(recommended_team)`, and `mentioned_technologies` by keyword scanning the description. No extra LLM call. The metadata is injected into `system.j2` on turns > 0 via the `{% if project_metadata %}` block.

**Observable LLM metrics** — `llm_wrapper.py` provides `MODEL_COSTS` (per-model input/output pricing in USD), `calculate_cost()` (computes call cost), and `create_metrics()` (wraps all observability). `_stream_completion()` tracks latency via `time.time()` start/stop. Every LLM call logs `streaming_complete` or `history_streaming_complete` events with `latency_ms`, `cost_usd`, `input_tokens`, `output_tokens`. Cache hits log 0ms latency and cached cost.

**Two endpoint families:**
- `/estimate` (blocking) + `/estimate/stream` (streaming) — stateless, no session, no attachments
- `/sessions` + `/sessions/{id}/estimate` — multipart form, maintains history and metadata

## API Contract

**`POST /api/v1/estimate`**
```json
// Request (JSON)
{
  "description": "string (20–2000 chars)",
  "project_type": "mobile_app | web_saas | internal_tool | data_pipeline",
  "detail_level": "summary | medium | detailed",
  "output_format": "phases_table | line_items | narrative"
}

// Response 200
{
  "output": { ...EstimationOutput... },
  "prompt_version": "v1",
  "model": "anthropic/claude-sonnet-4-5",
  "provider": "anthropic",
  "project_metadata": null
}

// Response 422 — guardrail failure
{ "error": "guardrail_failed", "violations": ["tasks → 0 → hours_min: ...", ...] }
```

**`POST /api/v1/estimate/stream`**
- Same JSON request body.
- Response: `text/plain` chunked stream (raw LLM output).
- Headers: `X-Model`, `X-Provider`, `X-Prompt-Version`.

**`POST /api/v1/sessions`**
```json
// Response 200
{ "session_id": "uuid4-string" }
```

**`POST /api/v1/sessions/{session_id}/estimate`**
```
// Request: multipart/form-data
description     string (20–2000 chars)
project_type    mobile_app | web_saas | internal_tool | data_pipeline
detail_level    summary | medium | detailed
output_format   phases_table | line_items | narrative
attachment      file (pdf / docx / txt, optional)

// Response 200 — same shape as /estimate, project_metadata populated
// Response 404 — session not found
// Response 422 — guardrail failure
```

**`GET /api/v1/sessions/{session_id}` (debug endpoint)**
```json
// Response 200
{
  "session_id": "uuid4-string",
  "message_count": 12,
  "anchors_count": 3,
  "summary_chars": 456,
  "last_resolved_tier": 2,
  "last_tier_rule": "Medium complexity: keyword density score 0.65"
}

// Response 404 — session not found
```

## Schemas (`app/schemas.py`)

```python
ProjectType:    mobile_app | web_saas | internal_tool | data_pipeline
DetailLevel:    summary | medium | detailed
OutputFormat:   phases_table | line_items | narrative

TaskBlock:          name, hours_min (≥1), hours_max (≥1); validator: min ≤ max
EstimationOutput:   project_summary, assumptions, tasks, total_hours_min/max,
                    recommended_team, duration_weeks_min/max, risks, open_questions;
                    validator: range coherence + ±25% task-sum tolerance
ProjectMetadata:    project_name, assumed_team_size, mentioned_technologies, agreed_scope
EstimationRequest:  description, project_type, detail_level, output_format
EstimationResponse: output, prompt_version, model, provider, project_metadata (optional)
```

## Observability

structlog emits structured events at key points:

| Event | Fields |
|---|---|
| `cache_hit` | `cache_key`, `model` |
| `cache_miss` | `cache_key`, `model` |
| `streaming_started` | `cache_key`, `model` |
| `streaming_complete` | `input_tokens`, `output_tokens`, `latency_ms`, `cost_usd`, `cached`, `guardrail_passed` |
| `history_streaming_started` | `model`, `turns` |
| `history_streaming_complete` | `input_tokens`, `output_tokens`, `latency_ms`, `cost_usd`, `guardrail_passed` |
| `turn_observed` | `turn_index`, `session_id`, `enriched_transcript_chars`, `attachments_total_chars`, `messages_in_window`, `anchors_count`, `summary_chars`, `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms`, `cache_hit_kind`, `last_resolved_tier`, `last_tier_rule` |
| `guardrail_violations` | `violations` (list of strings) |
| `llm_call_failed` | `error`, `error_type` |
| `streaming_failed` | `error`, `error_type` |
