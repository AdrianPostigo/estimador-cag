"""Logfire configuration for the estimation graph (Session 13)."""

from __future__ import annotations

import logfire
import structlog

logger = structlog.get_logger()

_configured = False


def configure_logfire(service_name: str = "estimador-cag") -> None:
    """Configure Logfire once per process.

    send_to_logfire="if-token-present" keeps this working without credentials:
    spans are still created and printed to the console, so the per-node trace is
    available. Setting LOGFIRE_TOKEN in the environment is enough to also ship
    the trace to the Logfire dashboard, with no code change.
    """
    global _configured
    if _configured:
        return

    logfire.configure(
        service_name=service_name,
        send_to_logfire="if-token-present",
    )

    # Optional instrumentations: each needs its own extra. Never let a missing
    # one break the run — the per-node spans are what the trace requires.
    for name, instrument in (
        ("httpx", logfire.instrument_httpx),  # captures the OpenAI Responses API calls
        ("asyncpg", logfire.instrument_asyncpg),
    ):
        try:
            instrument()
        except Exception as e:  # pragma: no cover - depends on installed extras
            logger.warning(
                "logfire_instrumentation_skipped",
                target=name,
                error=str(e),
            )

    _configured = True
