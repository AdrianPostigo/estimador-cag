from app.schemas import EstimationOutput, ProjectMetadata

_TECH_KEYWORDS = [
    "react", "vue", "angular", "next.js", "nuxt",
    "django", "fastapi", "flask", "rails", "laravel", "spring",
    "node", "express", "nestjs",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "sqlite",
    "docker", "kubernetes", "aws", "gcp", "azure",
    "graphql", "rest", "grpc",
    "stripe", "auth0", "firebase",
    "python", "typescript", "javascript", "java", "go", "rust",
    "swift", "kotlin", "flutter", "react native",
]


def update_metadata(
    existing: ProjectMetadata,
    output: EstimationOutput,
    description: str,
) -> ProjectMetadata:
    agreed_scope = output.project_summary

    team_size = len(output.recommended_team)

    lower = description.lower()
    found = [kw for kw in _TECH_KEYWORDS if kw in lower]
    technologies = list(dict.fromkeys(existing.mentioned_technologies + found))

    project_name = existing.project_name
    if project_name is None:
        words = output.project_summary.split()
        project_name = " ".join(words[:5]) if words else None

    return ProjectMetadata(
        project_name=project_name,
        assumed_team_size=team_size,
        mentioned_technologies=technologies,
        agreed_scope=agreed_scope,
    )
