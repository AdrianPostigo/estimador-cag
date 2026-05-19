import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.schemas import EstimationOutput


@dataclass
class GuardrailResult:
    passed: bool
    output: EstimationOutput | None = None
    violations: list[str] = field(default_factory=list)


def _extract_json(text: str) -> str:
    """Strip markdown code fences and extract the JSON object."""
    stripped = text.strip()

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Drop first line (```json or ```) and last closing ```
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        stripped = "\n".join(inner).strip()

    # If there's stray text before/after the JSON object, find the boundaries
    if not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}") + 1
        if start != -1 and end > start:
            stripped = stripped[start:end]

    return stripped


def parse_and_validate(text: str) -> GuardrailResult:
    try:
        data = json.loads(_extract_json(text))
    except json.JSONDecodeError as exc:
        return GuardrailResult(passed=False, violations=[f"JSON inválido: {exc}"])

    try:
        output = EstimationOutput.model_validate(data)
        return GuardrailResult(passed=True, output=output)
    except ValidationError as exc:
        violations = [
            f"{' → '.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        return GuardrailResult(passed=False, violations=violations)
