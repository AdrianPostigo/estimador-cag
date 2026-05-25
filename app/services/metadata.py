import re
from app.schemas import EstimationOutput, ProjectMetadata

_TECH_BY_CATEGORY = {
    "frontend": ["react", "vue", "angular", "next.js", "nuxt", "svelte", "ember"],
    "backend": ["django", "fastapi", "flask", "rails", "laravel", "spring", "node", "express", "nestjs", "java"],
    "database": ["postgres", "postgresql", "mysql", "mongodb", "redis", "sqlite", "dynamodb"],
    "cloud": ["aws", "gcp", "azure", "heroku", "vercel", "netlify"],
    "infrastructure": ["docker", "kubernetes", "terraform", "cloudformation"],
    "api": ["graphql", "rest", "grpc", "websocket"],
    "auth": ["auth0", "oauth", "jwt", "keycloak"],
    "payment": ["stripe", "paypal", "square"],
    "mobile": ["swift", "kotlin", "flutter", "react native", "ionic"],
    "language": ["python", "typescript", "javascript", "java", "go", "rust", "c#", "php"],
}

_ALL_TECHS = [tech for techs in _TECH_BY_CATEGORY.values() for tech in techs]


def _extract_project_name(description: str, summary: str, existing_name: str | None) -> str | None:
    """Extract real project name from description or summary."""
    if existing_name:
        return existing_name

    # Try to find quoted names: "ProjectName" or 'ProjectName'
    quoted = re.search(r'["\']([A-Z][a-zA-Z0-9\s]*?)["\']', description)
    if quoted:
        return quoted.group(1).strip()

    # Try patterns: "proyecto/app/aplicación X" or "de X para" or "X para"
    patterns = [
        r'(?:proyecto|app|aplicación|plataforma)\s+(?:de\s+)?["\']?([A-Z][a-zA-Z0-9\s]+?)["\']?(?:\s+para|\.)',
        r'["\']?([A-Z][a-zA-Z0-9\s]{3,}?)["\']?\s+(?:para|es una)',
    ]
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name and len(name.split()) <= 4:  # Reasonable name length
                return name

    return None


def _extract_tech_stacks(description: str, existing: list[str]) -> list[str]:
    """Extract technologies and detect common stacks."""
    lower = description.lower()
    found = [tech for tech in _ALL_TECHS if tech in lower]

    # Detect common stacks
    stacks = []
    frontend_match = [t for t in found if t in _TECH_BY_CATEGORY["frontend"]]
    backend_match = [t for t in found if t in _TECH_BY_CATEGORY["backend"]]
    db_match = [t for t in found if t in _TECH_BY_CATEGORY["database"]]
    cloud_match = [t for t in found if t in _TECH_BY_CATEGORY["cloud"]]

    if frontend_match and backend_match:
        stacks.append(f"{backend_match[0]}+{frontend_match[0]}")
    if cloud_match and any(t in lower for t in ["lambda", "ec2", "serverless"]):
        stacks.append(f"{cloud_match[0]}+Lambda")

    # Combine: stacks + individual techs, remove duplicates, preserve order
    all_techs = stacks + found
    return list(dict.fromkeys(existing + all_techs))


def _summarize_scope(summary: str) -> str:
    """Create executive summary from project summary."""
    if not summary:
        return ""

    # Take first sentence or first ~200 chars
    sentences = re.split(r'(?<=[.!?])\s+', summary)
    first_sent = sentences[0]

    if len(first_sent) <= 200:
        return first_sent
    else:
        # Truncate at word boundary if too long
        truncated = first_sent[:200]
        last_space = truncated.rfind(' ')
        if last_space > 100:
            return truncated[:last_space] + "."
        return truncated + "."


def update_metadata(
    existing: ProjectMetadata,
    output: EstimationOutput,
    description: str,
) -> ProjectMetadata:
    team_size = len(output.recommended_team)
    project_name = _extract_project_name(description, output.project_summary, existing.project_name)
    technologies = _extract_tech_stacks(description, existing.mentioned_technologies)
    agreed_scope = _summarize_scope(output.project_summary)

    return ProjectMetadata(
        project_name=project_name,
        assumed_team_size=team_size,
        mentioned_technologies=technologies,
        agreed_scope=agreed_scope,
    )
