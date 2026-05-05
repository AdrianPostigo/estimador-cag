import os
from anthropic import Anthropic
from dotenv import load_dotenv

from app.context.examples import ESTIMATION_EXAMPLES

load_dotenv()

MODEL_NAME = "claude-sonnet-4-5"
PROVIDER = "anthropic"

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def build_examples_context() -> str:
    examples_text = ""

    for index, example in enumerate(ESTIMATION_EXAMPLES, start=1):
        examples_text += f"""
### Ejemplo {index}

Resumen de reunión:
{example["meeting_summary"]}

Estimación generada:
{example["estimation"]}
"""
    return examples_text


def build_system_prompt() -> str:
    examples_context = build_examples_context()

    return f"""
Eres un consultor senior experto en estimación de proyectos software.

Tu tarea es analizar transcripciones de reuniones con clientes y generar una estimación técnica clara, estructurada y realista.

Debes basarte en los ejemplos previos proporcionados como referencia de estilo, formato y nivel de detalle.

Reglas:
- Responde siempre en español.
- Genera una estimación en formato Markdown.
- Incluye desglose de tareas.
- Incluye horas estimadas por bloque.
- Incluye total estimado.
- Incluye equipo recomendado.
- Incluye duración aproximada.
- Si falta información crítica, indica supuestos razonables.
- No inventes detalles demasiado específicos si no aparecen en la transcripción.

Ejemplos de referencia:

{examples_context}
"""


def stream_project_estimation(meeting_transcription: str, metrics: dict | None = None):
    system_prompt = build_system_prompt()

    with client.messages.stream(
        model=MODEL_NAME,
        max_tokens=1200,
        temperature=0.3,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"""
Analiza la siguiente transcripción de reunión y genera una estimación de proyecto:

{meeting_transcription}
""",
            }
        ],
    ) as stream:
        for text in stream.text_stream:
            yield text

        final_message = stream.get_final_message()

        if metrics is not None:
            metrics["model"] = MODEL_NAME
            metrics["provider"] = PROVIDER
            metrics["input_tokens"] = final_message.usage.input_tokens
            metrics["output_tokens"] = final_message.usage.output_tokens