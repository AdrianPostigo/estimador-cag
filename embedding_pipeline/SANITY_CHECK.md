# Embedding Pipeline Sanity Check

## Instrucciones de Ejecución

Para ejecutar el sanity check con las tres parejas de textos:

```bash
# Desde la raíz del proyecto, con uv:
uv run python scripts/compare.py \
  --text-a "OAuth 2.0 authentication backend with JWT tokens for fintech mobile app" \
  --text-b "Authorization service using JSON Web Tokens for a banking application"

uv run python scripts/compare.py \
  --text-a "OAuth 2.0 authentication backend with JWT tokens for fintech mobile app" \
  --text-b "Database migration from MySQL to PostgreSQL with zero downtime"

uv run python scripts/compare.py \
  --text-a "Backend services" \
  --text-b "API development"
```

O dentro del contenedor:

```bash
docker compose exec servicio_ia python scripts/compare.py --text-a "..." --text-b "..."
```

## Resumen de Parejas

| Pareja | Tipo | Expectativa | Comando |
|--------|------|-------------|---------|
| **A** | Semánticamente cercanos | > 0.6 | Pareja 1 arriba |
| **B** | No relacionados | < 0.4 | Pareja 2 arriba |
| **C** | Genéricos/ambiguos | Sin expectativa | Pareja 3 arriba |

---

## Pareja A — Textos Semánticamente Cercanos

**Expectativa:** Similitud alta (> 0.6)

**Texto 1:**
```
"OAuth 2.0 authentication backend with JWT tokens for fintech mobile app"
```

**Texto 2:**
```
"Authorization service using JSON Web Tokens for a banking application"
```

### Análisis Esperado

Ambos textos tratan sobre autenticación/autorización con JWT en contextos financieros. Los embeddings deberían capturar la semántica compartida:
- Autenticación y autorización (sinónimos conceptuales)
- JWT / JSON Web Tokens (mismo estándar)
- Contexto financiero: "fintech" ≈ "banking"

Se espera alta similitud porque comparten el mismo dominio y conceptos clave, aunque con variaciones léxicas.

---

## Pareja B — Textos No Relacionados

**Expectativa:** Similitud baja (< 0.4)

**Texto 1:**
```
"OAuth 2.0 authentication backend with JWT tokens for fintech mobile app"
```

**Texto 2:**
```
"Database migration from MySQL to PostgreSQL with zero downtime"
```

### Análisis Esperado

Estos textos pertenecen a dominios completamente diferentes:
- Texto 1: Autenticación, seguridad, identidad digital
- Texto 2: Infraestructura, base de datos, operaciones

No comparten:
- Tecnologías (OAuth/JWT vs MySQL/PostgreSQL)
- Problemas (autenticación vs migración de datos)
- Contextos (fintech/mobile vs infraestructura)

Se espera baja similitud porque el modelo debería discriminar dominios no relacionados.

---

## Pareja C — Textos Genéricos y Ambiguos

**Expectativa:** Sin expectativa fija (interesante para análisis)

**Texto 1:**
```
"Backend services"
```

**Texto 2:**
```
"API development"
```

### Análisis Esperado

Este es un caso de borde interesante:
- Ambos textos son muy cortos (2-3 palabras)
- Ambos están en el dominio de desarrollo de software backend
- Podrían considerarse "relacionados" o "diferentes" dependiendo de la interpretación

**Posibles interpretaciones del resultado:**

- **Si similitud > 0.6 (alta):** El modelo agrupa "backend services" y "API development" como conceptos relacionados. Esto sugiere que el embedder entiende que ambos hablan de desarrollo backend.

- **Si similitud 0.4-0.6 (media):** El modelo ve cierta relación pero considera que hay diferencia conceptual: servicios (=componentes) vs desarrollo (=proceso).

- **Si similitud < 0.4 (baja):** El modelo considera que hay diferencia significativa entre hablar de "servicios" (sustantivo, entidad) y "desarrollo" (verbo, actividad).

La brevedad del texto es notable: embeddings de textos cortos pueden ser menos estables que de textos largos con más contexto.

---

## Instrucciones de Registro

Después de ejecutar los tres comandos, registra los resultados aquí:

### Resultados Numéricos

```
Pareja A (cercanos): [EJECUTAR Y REGISTRAR]
Pareja B (no relacionados): [EJECUTAR Y REGISTRAR]
Pareja C (genéricos): [EJECUTAR Y REGISTRAR]
```

### Template de Resultados

Reemplaza `[RESULTADO]` con el valor obtenido:

| Pareja | Similitud | Cumple Expectativa |
|--------|-----------|-------------------|
| A (cercanos) | `[RESULTADO]` | ✓ si > 0.6, ✗ si ≤ 0.6 |
| B (no relacionados) | `[RESULTADO]` | ✓ si < 0.4, ✗ si ≥ 0.4 |
| C (genéricos) | `[RESULTADO]` | (sin expectativa) |

---

## Validación del Pipeline

Este sanity check valida:

1. ✓ **Funcionamiento end-to-end:** Texto → Embedder → Similitud
2. ✓ **Discriminación semántica:** El modelo diferencia textos cercanos de lejanos
3. ✓ **Comportamiento con edge cases:** Textos genéricos/cortos

**Criterios de éxito:**
- Pareja A: similitud > 0.6
- Pareja B: similitud < 0.4
- Pareja C: resultado interpretable (sin requerimiento específico)

---

## Notas para la Discusión

### Pareja A: Variaciones Léxicas

El modelo debería reconocer que:
- "OAuth 2.0" y "JWT" son mecanismos de autorización relacionados
- "fintech" y "banking" son dominios financieros sinónimos
- "backend" aparece en ambos (aunque implícitamente en la pareja 2)

Si la similitud es muy alta (> 0.8), sugiere que el modelo agrupa fuertemente los sinónimos.
Si es media (0.6-0.8), el modelo distingue entre variaciones léxicas.

### Pareja B: Desconexión de Dominios

Este es un test de "negativo controlado": validamos que el modelo NO confunde conceptos no relacionados. Muy importante para RAG: no queremos que una búsqueda sobre "autenticación" devuelva documentos sobre "migraciones de BD".

### Pareja C: Comportamiento con Textos Cortos

Relevant para la granularidad de chunks. Si el sistema produce chunks de 2-3 palabras (improbable pero posible), ¿cómo se comportan los embeddings? Este caso ayuda a documentar limitaciones.

---

## Cómo Usar Este Documento

1. Ejecuta los tres comandos arriba en una terminal con `.env` cargado
2. Registra los tres valores numéricos en la tabla de "Resultados Numéricos"
3. Añade comentarios sobre qué te sorprende o qué valida tus expectativas
4. Commit: `git add embedding_pipeline/SANITY_CHECK.md && git commit -m "Paso 7 — Sanity check results"`

---

## Referencias

- **Script:** `scripts/compare.py` — Reutiliza `OpenAIEmbedder` (Paso 4)
- **Embedder:** `embedding_pipeline/embedder.py` — OpenAI text-embedding-3-small
- **README.md:** "Herramientas CLI" → compare.py (sintaxis y ejemplos)

---

*Documento creado como template para Paso 7 — Sesión 07. Requiere ejecución manual con `.env` y `OPENAI_API_KEY` configurada.*
