# Software Estimation Generator (CAG)

Sistema de estimación de proyectos software que utiliza IA para generar estimaciones detalladas basadas en descripciones de proyectos. Incluye soporte para conversaciones multi-turno, análisis de presupuestos y búsqueda semántica mediante embeddings.

## Stack Técnico

- **Backend:** FastAPI + Uvicorn
- **Frontend:** Streamlit
- **LLM:** Claude Haiku 4.5 vía LiteLLM
- **Embeddings:** OpenAI text-embedding-3-small
- **Dependencias:** Python 3.11+, UV

## Setup

### 1. Instalar dependencias

```bash
uv sync
```

### 2. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# LLM Configuration
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=anthropic/claude-haiku-4-5-20251001

# OpenAI Embeddings
OPENAI_API_KEY=sk-...
```

**Notas:**
- `ANTHROPIC_API_KEY`: Requerido para la funcionalidad de estimaciones
- `OPENAI_API_KEY`: Requerido para embeddings y script `compare.py`
- `LLM_MODEL`: Opcional; por defecto usa Sonnet 4.5 si no está configurado

## Ejecución

### Backend (FastAPI)

```bash
uv run python -m uvicorn app.main:app --reload
```

Backend disponible en: `http://localhost:8000`
- API: `http://localhost:8000/api/v1`
- Swagger UI: `http://localhost:8000/docs`

### Frontend (Streamlit)

```bash
uv run streamlit run frontend/streamlit_app.py
```

Frontend disponible en: `http://localhost:8501`

**Nota:** Ambos servicios (backend y frontend) deben estar corriendo para que la UI funcione correctamente.

### Tests

```bash
uv run python -m pytest tests/ -v
```

## Herramientas CLI

### compare.py — Similitud coseno entre textos

Compara la similitud semántica entre dos textos usando embeddings de OpenAI.

**Sintaxis:**
```bash
python scripts/compare.py --text-a "TEXTO_1" --text-b "TEXTO_2"
```

**Ejemplo:**
```bash
python scripts/compare.py \
  --text-a "OAuth 2.0 authentication backend for fintech" \
  --text-b "JWT-based authorization service for banking app"
```

**Salida esperada:**
```
Embedding texts...

Text A: OAuth 2.0 authentication backend for fintech
Text B: JWT-based authorization service for banking app
Cosine similarity: 0.8421

```

#### Ejecución dentro del contenedor

Si estás usando Docker Compose:

```bash
docker compose exec servicio_ia python scripts/compare.py \
  --text-a "OAuth 2.0 authentication backend for fintech" \
  --text-b "JWT-based authorization service for banking app"
```

#### Ejecución fuera del contenedor

Con `uv` (entorno local):

```bash
uv run python scripts/compare.py \
  --text-a "OAuth 2.0 authentication backend for fintech" \
  --text-b "JWT-based authorization service for banking app"
```

**Requisitos:**
- `OPENAI_API_KEY` configurada en `.env`
- Acceso a modelo `text-embedding-3-small` en cuenta de OpenAI

## API Endpoints

### POST /api/v1/estimate

Genera una estimación puntual sin historial de sesión.

**Request:**
```json
{
  "description": "Plataforma SaaS de gestión de proyectos",
  "project_type": "web_saas",
  "detail_level": "medium",
  "output_format": "phases_table"
}
```

**Response (200):**
```json
{
  "output": { ... EstimationOutput ... },
  "prompt_version": "v1",
  "model": "anthropic/claude-haiku-4-5-20251001",
  "provider": "anthropic",
  "cost_usd": 0.005234,
  "latency_ms": 7841.3,
  "tokens_in": 1743,
  "tokens_out": 980,
  "project_metadata": null
}
```

### POST /api/v1/sessions

Crea una nueva sesión multi-turno.

**Response (200):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### POST /api/v1/sessions/{session_id}/estimate

Genera una estimación dentro de una sesión existente, manteniendo historial.

**Request:** multipart/form-data
```
description: "..."
project_type: "web_saas"
detail_level: "medium"
output_format: "phases_table"
attachment: (opcional) PDF/DOCX/TXT
```

**Response (200):** EstimationResponse con metadata y observables de turno

### POST /api/v1/embeddings/ingest

Ingesta presupuestos, los fragmenta por componente y los embedea.

**Request (IngestRequest):**
```json
{
  "budgets": [
    {
      "budget_id": "BUD-2024-014",
      "client_metadata": { "name": "...", "sector": "finance", "country": "ES" },
      "project_summary": "...",
      "main_technology": "...",
      "year": 2024,
      "total_estimated_hours": 480,
      "components": [...]
    }
  ]
}
```

**Response (200, IngestResponse):**
```json
{
  "chunks": [
    {
      "chunk_id": "BUD-2024-014::AUTH-001",
      "text": "[Project: ...]\n[Client sector: ...]\n\nComponent: ...",
      "metadata": { "budget_id": "...", "component_id": "...", ... },
      "token_count": 127,
      "embedding": [0.002, -0.001, ..., 0.045]
    }
  ],
  "stats": {
    "total_chunks": 1,
    "total_tokens": 127,
    "estimated_cost_usd": 0.00000254
  }
}
```

## Stress Testing

Ejecutar suite de stress tests:

```bash
uv run python -m evals.stress.run \
    --scenarios growing,pivoting,contradicting \
    --attachment-sizes 0,5,20,50,100 \
    --repeats 2 \
    --output evals/stress/results.csv
```

Resultados y análisis en:
- `evals/stress/results.csv` — Datos de métricas
- `evals/stress/results_REPORT.md` — Análisis cuantitativo

**Nota:** Framework de stress testing requiere backend corriendo.

## Estructura del Proyecto

```
estimador-cag/
├── app/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # LLM config (LLM_MODEL env var)
│   ├── schemas.py              # Pydantic models
│   ├── observability.py        # structlog setup
│   ├── sessions.py             # Session store (in-memory)
│   ├── routers/
│   │   ├── estimations.py      # POST /estimate, /estimate/stream
│   │   └── sessions.py         # POST /sessions, GET /sessions/{id}
│   └── services/
│       ├── estimation_service.py
│       ├── llm_service.py
│       ├── tier_scoring.py
│       ├── guardrails.py
│       ├── metadata.py
│       └── attachments.py
├── embedding_pipeline/         # Sesión 07
│   ├── schemas.py              # Pydantic: Budget, Chunk, EmbeddedChunk, etc.
│   ├── chunker.py              # JSONStructuralChunker
│   ├── embedder.py             # OpenAIEmbedder
│   └── router.py               # POST /api/v1/embeddings/ingest
├── frontend/
│   └── streamlit_app.py        # Streamlit UI
├── tests/
│   ├── test_sessions.py
│   └── test_stress_metrics.py
├── evals/
│   ├── metrics.py
│   ├── stress/
│   │   ├── run.py              # CLI orchestrator
│   │   ├── scenarios.py        # Synthetic profiles
│   │   ├── metrics.py          # Stress metrics
│   │   ├── REPORT.md           # Quantitative analysis
│   │   └── fixtures/
│   │       └── build_pdfs.py   # Deterministic PDF generation
│   └── golden_dataset.json     # (planned)
├── scripts/
│   └── compare.py              # CLI: text similarity comparison
├── data/
│   ├── budgets_sample.json     # 15 historical budgets (Sesión 07)
│   └── budgets_normalized/     # Deprecated fixtures
├── .env                        # Environment variables (git-ignored)
├── pyproject.toml              # Dependencies & project config
└── README.md                   # This file
```

## Conceptos Clave

### Event-Driven Observability (Sesión 03+)

Cada turno de estimación emite evento `turn_observed` con 13 campos:
- `turn_index`, `session_id`
- `tokens_in`, `tokens_out`
- `cost_usd`, `latency_ms`
- `cache_hit_kind`, `last_resolved_tier`
- Y más...

Recuperable vía `GET /api/v1/sessions/{id}` → `last_turn_observables`

### Contextual Chunk Headers (Sesión 07)

Al embedear componentes de presupuestos, cada chunk incluye contexto del presupuesto padre:

```
[Project: {project_summary}]
[Client sector: {sector} | Year: {year} | Main tech: {main_technology}]

Component: {name}
Description: {description}
Tech stack: {tech_stack}
Complexity: {complexity}
Estimated hours: {estimated_hours}
```

Esto evita que componentes descontextualizados (ej. "Authentication backend") pierdan trazabilidad.

### Batching en Embeddings

OpenAI embeddings API acepta listas. El embedder procesa en batches de 100 chunks para evitar martillear la API con peticiones serializadas.

### Cálculo de Coseno Similitud

Formula implementada sin dependencias externas (math stdlib):
```
similitud = (a · b) / (||a|| * ||b||)
```

Donde `·` es producto escalar y `||v||` es norma L2.

## Troubleshooting

### Error: "OPENAI_API_KEY not set"

**Solución:** Configura la variable en `.env`:
```env
OPENAI_API_KEY=sk-...
```

### Error: "model not found" (embeddings)

**Solución:** Verifica que tu cuenta de OpenAI tenga acceso a `text-embedding-3-small`.

### Error 500 en /api/v1/embeddings/ingest

Revisa los logs del backend. Causas comunes:
- API de OpenAI no disponible
- Token limit excedido (chunks muy grandes)
- RateLimitError después de 3 reintentos

### Script compare.py no importa módulos

**Solución:** Ejecuta con `uv run` o asegúrate de que el `PYTHONPATH` incluye la raíz del proyecto.

## Decisiones de Diseño — Schema de Persistencia (Sesión 08)

### ¿Por qué dos tablas (`documents` + `chunks`) en lugar de una?

**Decisión:** Mantener relación 1:N normalizada con FK CASCADE.

**Justificación:** 
- Un presupuesto ingestado genera N chunks (componentes). Una tabla única duplicaría metadatos del documento en cada fila, rompiendo integridad referencial.
- Con dos tablas: eliminar un documento elimina automáticamente todos sus chunks vía `ON DELETE CASCADE`.
- Consultas más eficientes: filtrar por document_id está indexado.

**Trade-off:** Una tabla única sería más simple para pequeños volúmenes; dos tablas escala mejor.

### ¿Por qué `metadata JSONB` en lugar de columnas tipadas?

**Decisión:** Metadata estable (tipo de documento, tipo de chunk) en columnas; metadata variable (tags, tecnologías, scope) en JSONB.

**Justificación:**
- **Estable:** `document_type`, `chunk_type` son limitados y crecen lentamente → columnas tipadas con índices.
- **Variable:** `technologies`, `scope`, `client_sector` enriquecen en ingesta y querying sin requerir DDL.
- **Índices GIN:** Permiten queries arbitrarias (`WHERE metadata->>'sector' = 'fintech'`) sin migración de schema.
- **Flexibilidad:** Nuevos campos en metadata no requieren ALTER TABLE.

**Trade-off:** JSONB es más lento para queries simples vs columnas tipadas; ganancia en flexibilidad.

### ¿Por qué `cosine_distance` y no L2 ni `inner_product`?

**Decisión:** `Chunk.embedding.cosine_distance(query_vector)` para k-nearest neighbors.

**Justificación:**
- **Cosine:** Mide ángulo entre vectores (invariante a magnitud). Ideal para embeddings de texto donde magnitud no importa.
- **L2:** Distancia euclidiana; sensible a magnitud. Menos natural para semántica.
- **Inner product:** Más rápido pero require vectores normalizados y negativo para distancia.
- **Corpus fintech:** Cosine captura bien "OAuth 2.0" ≈ "JWT" porque ambos están en dirección similar del espacio, independientemente de su longitud.

**Trade-off:** Cosine es más interpretable; inner product sería ~5% más rápido si los vectores fuesen normalizados a priori.

### ¿Por qué deliberadamente NO hay índice vectorial (HNSW/IVFFlat)?

**Decisión:** Solo índices sobre columnas tipadas (`source_path`, `document_id`, `chunk_type`, `metadata` GIN). Sequential scan para k-NN.

**Justificación:**
- **Baseline measurement:** Primero medir el performance de sequential scan. Es el comportamiento de referencia.
- **Sesión 08 scope:** El índice vectorial se agrega en sesión posterior (es un directo colaborativo).
- **Understanding:** Sequential scan permite entender cómo pgvector maneja distance calculation sin capa de índice.
- **Trade-off:** Sequential scan es O(N) para cada query; HNSW sería O(log N) pero con overhead de construcción/mantenimiento.

**Próximo paso:** En sesión futura, medir impacto de HNSW en latency + índices filtrados (ej. `WHERE metadata->>'sector' = 'fintech'` THEN kNN).

---

## Endpoints de Búsqueda (Sesión 08-10)

### POST /api/v1/embeddings/ingest

Ingesta y persiste un presupuesto con sus embeddings.

**Request:**
```json
{
  "source_path": "data/budgets/budget_2024_q1.json",
  "document_type": "historical_budget",
  "content": { /* Budget JSON */ }
}
```

**Response (200):**
```json
{
  "document_id": 1,
  "chunks_created": 17,
  "embedding_dimension": 1536,
  "ingestion_time_ms": 1240.5
}
```

**Response (409 Conflict):**
```json
{
  "detail": "Document already ingested"
}
```

### POST /api/v1/embeddings/search (Hybrid Search ± Reranking)

Búsqueda en tres modos (semantic, lexical, hybrid) con reranking opcional.

**Patrón recall-then-rerank:**
1. **Recall stage:** Retrieve top-reranker_k (default 50) — amplia cobertura
2. **Rerank stage (opcional):** FlashRank cross-encoder reordena a top-k — relevancia fina

**Request:**
```json
{
  "query": "REST API with OAuth authentication for fintech sector",
  "k": 5,
  "search_mode": "hybrid",
  "enable_reranking": true,
  "reranker_k": 50
}
```

**Parámetros:**
- `search_mode`: `"semantic"` | `"lexical"` | `"hybrid"`
- `enable_reranking`: `true` — Apply FlashRank (ms-marco-MiniLM-L-12-v2) | `false` — Direct retrieval
- `reranker_k`: Número de docs a recuperar antes de reranking (min: 5, max: 200, default: 50)

**Response (200) — sin reranking:**
```json
{
  "query": "REST API with OAuth...",
  "k": 5,
  "search_mode": "hybrid",
  "enable_reranking": false,
  "search_time_ms": 142.8,
  "reranking_time_ms": 0.0,
  "results": [
    {
      "chunk_id": 156,
      "rank": 1,
      "rrf_score": 0.0315,
      "reranker_score": null,
      "chunk_type": "component",
      "content": "Backend service implementation with JWT-based authentication...",
      "metadata": { "scope": "backend", "technologies": ["python", "fastapi"] }
    }
  ]
}
```

**Response (200) — con reranking:**
```json
{
  "query": "REST API with OAuth...",
  "k": 5,
  "search_mode": "hybrid",
  "enable_reranking": true,
  "search_time_ms": 142.8,
  "reranking_time_ms": 18.5,
  "results": [
    {
      "chunk_id": 156,
      "rank": 1,
      "rrf_score": 0.0315,
      "reranker_score": 8.2,
      "chunk_type": "component",
      "content": "...",
      "metadata": { ... }
    }
  ]
}
```

**RRF Formula (Hybrid Fusion):**
```
RRF_score = 1/(60 + rank_semantic) + 1/(60 + rank_lexical)
```

**FlashRank (Cross-Encoder):**
- Modelo: `ms-marco-MiniLM-L-12-v2` (entrenado en MS MARCO)
- Score: 0-10 (10 = máxima relevancia)
- Latencia: ~10-20ms para reranking
- Patrón: Recupera 50 candidatos, reordena a top-5

### Script compare_search_modes.py (Sesión 10)

Compara tres modos de búsqueda (semantic, lexical, hybrid) sin reranking:

```bash
docker compose run --rm ai_service python scripts/compare_search_modes.py
```

Muestra cómo RRF fusion mejora recall vs búsquedas puras.

**Modo de uso:**
- **semantic:** Cuando la consulta describe conceptos (no palabras clave)
- **lexical:** Cuando la consulta tiene palabras clave precisas (OAuth, PostgreSQL, etc.)
- **hybrid:** Por defecto (mejor recall combinando ambos)

### Script validate_reranking.py (Sesión 10)

Valida efectividad del reranking (FlashRank) en el patrón recall-then-rerank:

```bash
docker compose run --rm ai_service python scripts/validate_reranking.py
```

**Compara:**
1. Búsqueda hybrid SIN reranking (top-5 directo)
2. Búsqueda hybrid CON reranking (retrieve 50, rerank a top-5)

**Muestra:**
- RRF scores vs FlashRank scores
- Qué chunks se reordenan
- Cambios en top-1
- Latencia del reranking
- Chunks nuevos promovidos a top-5

**Ejemplo de output:**
```
WITHOUT RERANKING (Top-5 from hybrid fusion)
Retrieval time: 142.8ms | Results: 5
  [1] Chunk 156 | RRF Score: 0.0315
      OAuth 2.0 authentication backend...
  [2] Chunk 287 | RRF Score: 0.0298
      JWT-based authorization service...

WITH RERANKING (Recall-then-rerank: retrieve 50, rerank to 5)
Retrieval time: 142.8ms | Reranking time: 18.5ms | Total: 161.3ms
Results: 5
  [1] Chunk 287 | FlashRank Score: 8.9
      JWT-based authorization service...
  [2] Chunk 156 | FlashRank Score: 8.5
      OAuth 2.0 authentication backend...

ANALYSIS
  Ranking stability: 4/5 chunks in same position
  Chunks reordered by reranker: 1/5
  Top-1 changed: 156 → 287
  Latency increase: 18.5ms for reranking stage
```

### Script query_examples.py

Prueba la búsqueda semántica con cinco queries representativas:

```bash
docker compose run --rm ai_service python scripts/query_examples.py
```

Ejercita:
1. **Direct match** — Componente conocido (sanity check)
2. **Semantic reformulation** — Mismo concepto, vocabulario distinto
3. **Out-of-domain** — Query sobre algo no en el corpus
4. **Ambiguous query** — Corta y genérica, múltiples matches parciales
5. **Very specific** — Vocabulario técnico preciso

Ver `output_examples.txt` para ejemplo de salida.

## Evaluación de Búsqueda Híbrida + Reranking (Sesión 10)

### Workflow de Evaluación

```bash
# 1. Explorar chunks existentes y testear golden queries
docker compose run --rm ai_service python scripts/explore_chunks.py

# Output: Top-50 resultados para cada query, listo para anotar manualmente

# 2. Anotar golden_set_session_10.json con chunk IDs relevantes
# Edit: evals/golden_set_session_10.json
# Para cada query, llenar relevant_chunk_ids basado en explore_chunks.py

# 3. Ejecutar evaluación de 4 configuraciones
docker compose run --rm ai_service python scripts/evaluate_search_configs.py

# Output: 
# - Tabla comparativa (stdout)
# - CSV: evals/search_evaluation_session_10.csv
# - JSON detallado: evals/search_evaluation_session_10.json
```

### Configuraciones Evaluadas

| Código | Search Mode | Reranking | Descripción |
|--------|-------------|-----------|------------|
| **A** | Semantic | No | Vector similarity (baseline) |
| **B** | Hybrid | No | RRF fusion of semantic + lexical |
| **C** | Semantic | Yes | Vector similarity + FlashRank reranking |
| **D** | Hybrid | Yes | RRF + FlashRank reranking (best recall-then-rerank) |

### Métricas

- **Precisión@5 (P@5):** Porcentaje de top-5 que son realmente relevantes
  ```
  P@5 = (relevant chunks en top-5) / min(5, total relevant chunks)
  ```
- **Latencia (ms):** Tiempo total de búsqueda + reranking

### Golden Set

Archivo: `evals/golden_set_session_10.json`

5 queries representativas del dominio, con `relevant_chunk_ids` anotados **a nivel de componente** (un chunk es relevante solo si su componente coincide con la intención de la query, no solo su presupuesto padre):
1. **Q1:** REST API with OAuth (Fintech/Auth)
2. **Q2:** E-commerce with payments (Retail)
3. **Q3:** Data warehouse with ETL (Analytics)
4. **Q4:** ML model deployment (ML/AI)
5. **Q5:** Internal collaboration tool (Productivity)

### Resultados (corpus: 60 chunks de 16 presupuestos)

| Config | Búsqueda | Reranking | P@5 medio | Latencia media |
|--------|----------|-----------|-----------|----------------|
| **A** | Vectorial | No | **83.3%** | **323 ms** |
| **B** | Híbrida (RRF) | No | 68.3% | 201 ms |
| **C** | Vectorial | Sí (FlashRank) | 58.3% | 1164 ms |
| **D** | Híbrida (RRF) | Sí (FlashRank) | 58.3% | 1091 ms |

Desglose por query (P@5):

| Query | A | B | C | D |
|-------|-----|-----|-----|-----|
| Q1 fintech auth | 100% | 100% | 100% | 100% |
| Q2 e-commerce | 75% | 75% | 75% | 75% |
| Q3 data/ETL | 75% | 50% | 25% | 25% |
| Q4 ML deployment | 67% | 67% | 67% | 67% |
| Q5 colaboración | 100% | 50% | 25% | 25% |

El daño se concentra en **Q3 y Q5**: la rama léxica y el reranking degradan la precisión que la búsqueda vectorial ya resolvía bien.

### Conclusiones

**Usaríamos la Configuración A (búsqueda vectorial pura, sin reranking).** En este caso de uso concreto es la opción que gana en las dos métricas a la vez: máxima precisión (83.3% P@5) y mínima latencia (~323 ms). Cada capa de complejidad que añadimos —fusión léxica (RRF) y luego reranking— **empeora** la relevancia en lugar de mejorarla, y el reranking además multiplica la latencia por ~3.5×. **La ganancia de relevancia del reranking no existe aquí: es una pérdida, y encima cara.** Hay tres razones concretas que lo explican y que delimitan cuándo *sí* compensaría: (1) el contenido está en inglés pero la columna full-text usa configuración `spanish`, así que la rama léxica con términos en OR matchea palabras comunes ("real-time", "system", "management") e inyecta ruido; (2) el patrón recall-then-rerank no aporta cuando recuperas 50 candidatos de un corpus de solo 60 —el reranker reordena casi todo, sin que la recuperación filtre nada—, mientras que su valor real aparece al recuperar 50 de miles; y (3) el cross-encoder `ms-marco-MiniLM` optimiza una noción de relevancia web genérica, no "qué presupuesto sirve para estimar", de modo que promociona chunks textualmente parecidos pero ajenos al golden set. La lección no es "el reranking es malo", sino que **una técnica solo compensa si su supuesto de diseño se cumple**: reranking y búsqueda híbrida pagarían su coste sobre un corpus grande, con el idioma de FTS alineado al contenido y, idealmente, un reranker afín al dominio. Mientras el corpus sea pequeño y homogéneo, la simplicidad vectorial es la decisión correcta —y la mantendríamos hasta que el volumen de presupuestos crezca lo suficiente para volver a medir.

## Más Información

- **CLAUDE.md:** Instrucciones detalladas para Claude Code (arquitectura, decisiones de diseño)
- **evals/stress/REPORT.md:** Análisis de stress testing y recomendaciones
- **evals/stress/RUN.md:** Guía de uso del runner de stress tests
- **Swagger UI:** `http://localhost:8000/docs` (cuando backend está corriendo)

## Licencia

Ver CLAUDE.md para contexto de desarrollo.
