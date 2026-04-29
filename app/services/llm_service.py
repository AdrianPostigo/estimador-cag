import os
from anthropic import Anthropic
from dotenv import load_dotenv

from app.data.estimation_examples import ESTIMATION_EXAMPLES

load_dotenv()

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


def estimate_project_from_transcription(meeting_transcription: str) -> str:
    examples_context = build_examples_context()

    system_prompt = f"""
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

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1200,
        temperature=0.3,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"""
Analiza la siguiente transcripción de reunión y genera una estimación de proyecto:

{meeting_transcription}
"""
            }
        ],
    )

    return response.content[0].text