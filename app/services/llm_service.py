import hashlib
import time
from collections.abc import Generator
from typing import TYPE_CHECKING

import litellm
import structlog

from app.config import MODEL_NAME, PROVIDER
from app.services.guardrails import parse_and_validate
from app.services.llm_wrapper import create_metrics

if TYPE_CHECKING:
    from app.services.estimation_service import capture_llm_metrics

logger = structlog.get_logger(__name__)

_cache: dict[str, dict] = {}


def _cache_key(system_prompt: str, user_prompt: str) -> str:
    raw_prompt = f"{system_prompt.strip()}\n---\n{user_prompt.strip()}"
    return hashlib.sha256(raw_prompt.encode()).hexdigest()


def _stream_completion(messages: list[dict], model_name: str | None = None) -> Generator[str, None, dict]:
    """Yield text chunks; return usage dict + latency when exhausted."""
    if model_name is None:
        model_name = MODEL_NAME

    start_time = time.time()

    try:
        response = litellm.completion(
            model=model_name,
            messages=messages,
            max_tokens=1200,
            temperature=0.3,
            stream=True,
            stream_options={"include_usage": True},
        )
    except Exception as exc:
        logger.error("llm_call_failed", error=str(exc), error_type=type(exc).__name__)
        raise

    chunks: list[str] = []
    usage = None

    try:
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                chunks.append(delta)
                yield delta
            if hasattr(chunk, "usage") and chunk.usage is not None:
                usage = chunk.usage
    except Exception as exc:
        logger.error("streaming_failed", error=str(exc), error_type=type(exc).__name__)
        raise

    latency_ms = (time.time() - start_time) * 1000

    return {
        "full_text": "".join(chunks),
        "input_tokens": usage.prompt_tokens if usage else None,
        "output_tokens": usage.completion_tokens if usage else None,
        "latency_ms": latency_ms,
    }


def stream_project_estimation(
    system_prompt: str,
    user_prompt: str,
    metrics: dict | None = None,
    model_name: str | None = None,
) -> Generator[str, None, None]:
    if model_name is None:
        model_name = MODEL_NAME

    key = _cache_key(system_prompt, user_prompt)
    log = logger.bind(cache_key=key[:8], model=model_name)

    if key in _cache:
        cached = _cache[key]
        log.info("cache_hit")
        if metrics is not None:
            metrics["model"] = model_name
            metrics["provider"] = PROVIDER
            metrics["input_tokens"] = cached["input_tokens"]
            metrics["output_tokens"] = cached["output_tokens"]
            metrics["latency_ms"] = cached.get("latency_ms", 0.0)
            metrics["cost_usd"] = cached.get("cost_usd", 0.0)
        yield cached["estimation"]
        return

    log.info("cache_miss")
    log.info("streaming_started")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    gen = _stream_completion(messages, model_name=model_name)
    chunks: list[str] = []

    try:
        while True:
            chunk = next(gen)
            chunks.append(chunk)
            yield chunk
    except StopIteration as stop:
        result = stop.value or {}
        full_text = "".join(chunks)
        input_tokens = result.get("input_tokens")
        output_tokens = result.get("output_tokens")
        latency_ms = result.get("latency_ms", 0.0)
    except Exception:
        raise

    guardrail = parse_and_validate(full_text)
    if not guardrail.passed:
        log.warning("guardrail_violations", violations=guardrail.violations)

    cost_usd = 0.0
    if input_tokens and output_tokens:
        from app.services.llm_wrapper import calculate_cost
        cost_usd = calculate_cost(model_name, input_tokens, output_tokens)

    _cache[key] = {
        "estimation": full_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
    }

    log.info(
        "streaming_complete",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=round(latency_ms, 2),
        cost_usd=round(cost_usd, 6),
        cached=False,
        guardrail_passed=guardrail.passed,
    )

    if metrics is not None:
        metrics["model"] = model_name
        metrics["provider"] = PROVIDER
        metrics["input_tokens"] = input_tokens
        metrics["output_tokens"] = output_tokens
        metrics["latency_ms"] = latency_ms
        metrics["cost_usd"] = cost_usd

    # Capture metrics for EstimationService to retrieve
    try:
        from app.services.estimation_service import capture_llm_metrics
        capture_llm_metrics({
            "tokens_in": input_tokens or 0,
            "tokens_out": output_tokens or 0,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "cache_hit_kind": "none",
        })
    except ImportError:
        pass  # estimation_service not imported yet


def stream_with_history(messages: list[dict], model_name: str | None = None) -> Generator[str, None, None]:
    """Stream a multi-turn completion from a pre-built messages list."""
    if model_name is None:
        model_name = MODEL_NAME

    log = logger.bind(model=model_name, turns=sum(1 for m in messages if m["role"] == "user"))
    log.info("history_streaming_started")

    gen = _stream_completion(messages, model_name=model_name)
    chunks: list[str] = []

    try:
        while True:
            chunk = next(gen)
            chunks.append(chunk)
            yield chunk
    except StopIteration as stop:
        result = stop.value or {}
        full_text = "".join(chunks)
        input_tokens = result.get("input_tokens")
        output_tokens = result.get("output_tokens")
        latency_ms = result.get("latency_ms", 0.0)
    except Exception:
        raise

    guardrail = parse_and_validate(full_text)
    if not guardrail.passed:
        log.warning("guardrail_violations", violations=guardrail.violations)

    cost_usd = 0.0
    if input_tokens and output_tokens:
        from app.services.llm_wrapper import calculate_cost
        cost_usd = calculate_cost(model_name, input_tokens, output_tokens)

    log.info(
        "history_streaming_complete",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=round(latency_ms, 2),
        cost_usd=round(cost_usd, 6),
        guardrail_passed=guardrail.passed,
    )


def estimate_project(system_prompt: str, user_prompt: str) -> str:
    return "".join(
        stream_project_estimation(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    )
