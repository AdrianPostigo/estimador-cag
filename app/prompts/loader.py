from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined


BASE_DIR = Path(__file__).parent


def render_estimation_prompt(
    request: Any,
    version: str = "v1",
    project_metadata: Any = None,
) -> tuple[str, str]:
    env = Environment(
        loader=FileSystemLoader(BASE_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    system_template = env.get_template(f"estimation/{version}/system.j2")
    user_template = env.get_template(f"estimation/{version}/user.j2")

    system = system_template.render(request=request, project_metadata=project_metadata)
    user = user_template.render(request=request)

    return system, user


def render_grounded_estimation_prompt(
    description: str,
    sources: list[dict[str, Any]],
    version: str = "v1",
) -> tuple[str, str]:
    """
    Render the grounded estimation prompt (system, user).

    Args:
        description: Project description to estimate.
        sources: Retrieved chunks, each a dict with chunk_id, document_id,
            and content, propagated into the prompt with their ids so the
            model can cite each line by chunk_id.
        version: Prompt version directory under grounded_estimation/.

    Returns:
        (system_prompt, user_prompt)
    """
    env = Environment(
        loader=FileSystemLoader(BASE_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    system_template = env.get_template(f"grounded_estimation/{version}/system.j2")
    user_template = env.get_template(f"grounded_estimation/{version}/user.j2")

    system = system_template.render()
    user = user_template.render(description=description, sources=sources)

    return system, user