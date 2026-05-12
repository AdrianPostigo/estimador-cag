import hashlib

import litellm
import structlog
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "anthropic/claude-sonnet-4-5"
PROVIDER = "anthropic"

logger = structlog.get_logger(__name__)

# exact-match cache: sha256(system + user) -> {estimation, input_tokens, output_tokens}
_cache: dict[str, dict] = {}


def _cache_key(system_prompt: str, user_prompt: str) -> str:
    raw_prompt = f"{system_prompt.strip()}\n---\n{user_prompt.strip()}"
    return hashlib.sha256(raw_prompt.encode()).hexdigest()


def stream_project_estimation(
    system_prompt: str,
    user_prompt: str,
    metrics: dict | None = None,
):
    key = _cache_key(system_prompt, user_prompt)
    log = logger.bind(cache_key=key[:8], model=MODEL_NAME)

    if key in _cache:
        cached = _cache[key]
        log.info("cache_hit")

        if metrics is not None:
            metrics["model"] = MODEL_NAME
            metrics["provider"] = PROVIDER
            metrics["input_tokens"] = cached["input_tokens"]
            metrics["output_tokens"] = cached["output_tokens"]

        yield cached["estimation"]
        return

    log.info("cache_miss")

    response = litellm.completion(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1200,
        temperature=0.3,
        stream=True,
        stream_options={"include_usage": True},
    )

    log.info("streaming_started")

    chunks: list[str] = []
    usage = None

    for chunk in response:
        delta = chunk.choices[0].delta.content

        if delta:
            chunks.append(delta)
            yield delta

        if hasattr(chunk, "usage") and chunk.usage is not None:
            usage = chunk.usage

    full_estimation = "".join(chunks)

    input_tokens = usage.prompt_tokens if usage else None
    output_tokens = usage.completion_tokens if usage else None

    _cache[key] = {
        "estimation": full_estimation,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }

    log.info(
        "streaming_complete",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached=False,
    )

    if metrics is not None:
        metrics["model"] = MODEL_NAME
        metrics["provider"] = PROVIDER
        metrics["input_tokens"] = input_tokens
        metrics["output_tokens"] = output_tokens


def estimate_project(system_prompt: str, user_prompt: str) -> str:
    return "".join(
        stream_project_estimation(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    )