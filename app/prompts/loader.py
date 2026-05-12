from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined


BASE_DIR = Path(__file__).parent


def render_estimation_prompt(request: Any, version: str = "v1") -> tuple[str, str]:
    env = Environment(
        loader=FileSystemLoader(BASE_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    system_template = env.get_template(f"estimation/{version}/system.j2")
    user_template = env.get_template(f"estimation/{version}/user.j2")

    system = system_template.render(request=request)
    user = user_template.render(request=request)

    return system, user