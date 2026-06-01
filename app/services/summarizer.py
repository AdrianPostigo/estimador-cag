import litellm
import structlog

logger = structlog.get_logger(__name__)

SUMMARIZER_MODEL = "anthropic/claude-haiku-4-5-20251001"

_SUMMARIZATION_PROMPT = """Eres un asistente de compresión de contexto de estimaciones software.

Tu tarea: Resume el siguiente historial de turnos de estimación en 1-2 oraciones concisas.
Mantén decisiones clave: nombres de proyecto, tecnologías acordadas, equipo, restricciones, timeline.

Resume ÚNICAMENTE en texto plano, sin JSON, sin markup. Máximo 150 palabras."""


def summarize_turns(turns: list[dict]) -> str:
    """Compress conversation turns into a concise summary."""
    if not turns:
        return ""

    # Build the conversation text to summarize
    conversation_text = "\n".join(
        f"{turn['role'].upper()}: {turn['content'][:200]}..."
        if len(turn.get("content", "")) > 200
        else f"{turn['role'].upper()}: {turn.get('content', '')}"
        for turn in turns
    )

    messages = [
        {"role": "system", "content": _SUMMARIZATION_PROMPT},
        {
            "role": "user",
            "content": f"Historial para resumir:\n\n{conversation_text}",
        },
    ]

    try:
        response = litellm.completion(
            model=SUMMARIZER_MODEL,
            messages=messages,
            max_tokens=200,
            temperature=0.3,
        )
        summary = response.choices[0].message.content.strip()
        logger.info("turns_summarized", turns_count=len(turns), summary_length=len(summary))
        return summary
    except Exception as exc:
        logger.error("summarization_failed", error=str(exc), error_type=type(exc).__name__)
        # Return placeholder on failure so conversation doesn't break
        return f"[Resumen previo de {len(turns)} mensajes no disponible]"
