_ESTIMATION_KEYWORDS = [
    "hora", "horas", "dia", "dias", "semana", "semanas", "mes", "meses",
    "equipo", "desarrollador", "developer", "qa", "qas", "tester",
    "presupuesto", "costo", "budget", "recursos", "recurso",
    "timeline", "deadline", "plazo", "entrega",
    "sprint", "iteración", "ciclo", "fase", "fases",
    "estimación", "estimado", "estimada", "alcance", "scope",
    "requisito", "requisitos", "funcionalidad", "funcionalidades",
    "componente", "módulo", "módulos", "feature", "features",
]

_TECH_SPECIFICITY = [
    "django", "fastapi", "flask", "node", "express", "nestjs", "rails",
    "react", "vue", "angular", "svelte", "next.js", "nuxt",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "dynamodb",
    "aws", "gcp", "azure", "kubernetes", "docker", "lambda",
    "api", "rest", "graphql", "websocket", "grpc",
    "base de datos", "database", "sql", "nosql",
    "autenticación", "auth", "oauth", "jwt", "keycloak",
    "caché", "cache", "cdn", "cdn", "storage", "almacenamiento",
    "testing", "test", "unit test", "e2e", "integration",
    "ci/cd", "deployment", "deployment", "despliegue",
]


def score_input(description: str) -> dict:
    """Analyze description and return tier classification with scoring."""
    if not description:
        return {"tier": 2, "score": 0.0, "keywords_found": [], "reason": "Empty description"}

    lower = description.lower()

    # Count keyword matches
    estimation_count = sum(1 for kw in _ESTIMATION_KEYWORDS if kw in lower)
    tech_count = sum(1 for kw in _TECH_SPECIFICITY if kw in lower)
    total_keywords = estimation_count + tech_count

    # Length factor: longer descriptions score higher (baseline: 50+ words = 0.5)
    words = len(description.split())
    length_score = min(words / 50, 1.0)

    # Keyword density: reward high density but with diminishing returns
    # Up to ~10 keywords is excellent, beyond that gives diminishing returns
    keyword_density = min(total_keywords / 10, 1.0)

    # Calculate weighted score
    # Emphasis: keywords (50%) > length (30%) > detail level (20%)
    raw_score = (keyword_density * 0.5 + length_score * 0.3 + (estimation_count / max(1, estimation_count + tech_count) if total_keywords > 0 else 0) * 0.2)
    score = min(raw_score, 1.0)

    # Detect keywords for feedback
    found_keywords = []
    for kw in _ESTIMATION_KEYWORDS:
        if kw in lower:
            found_keywords.append(kw)
    for kw in _TECH_SPECIFICITY:
        if kw in lower and kw not in found_keywords:
            found_keywords.append(kw)

    # Classify into tier based on score thresholds
    if score >= 0.55:
        tier = 3
        reason = "Alta especificidad: palabras clave de estimación y tecnología detectadas"
    elif score >= 0.25:
        tier = 2
        reason = "Especificidad media: descripción con detalles moderados"
    else:
        tier = 1
        reason = "Baja especificidad: descripción vaga o muy general"

    return {
        "tier": tier,
        "score": round(score, 3),
        "keywords_found": found_keywords[:10],  # Top 10 keywords
        "reason": reason,
    }


def get_model_for_tier(tier: int) -> str:
    """Return LiteLLM model string for given tier."""
    models = {
        3: "anthropic/claude-haiku-4-5-20251001",      # High specificity → Haiku (fast, cheap)
        2: "anthropic/claude-sonnet-4-6-20250514",     # Medium → Sonnet (balanced)
        1: "anthropic/claude-opus-4-7-20250805",       # Low specificity → Opus (powerful)
    }
    return models.get(tier, models[2])
