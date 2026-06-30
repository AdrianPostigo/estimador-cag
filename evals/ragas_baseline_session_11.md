# RAGAS Generation-Quality Baseline (Session 11)

Judge: `gpt-4o-mini` | Embeddings: `text-embedding-3-small` | Pipeline: grounded estimation

| Query | faithfulness | answer_relevancy | context_precision | context_recall |
|---|---|---|---|---|
| Q1 | 0.1000 | 0.0000 | 1.0000 | 0.5000 |
| Q2 | 0.5000 | 0.4999 | 1.0000 | 0.5000 |
| Q3 | 0.2667 | 0.4565 | 0.0000 | 0.5000 |
| Q4 | 0.5385 | 0.0000 | 1.0000 | 0.5000 |
| Q5 | 0.3333 | 0.5962 | 0.9167 | 0.5000 |
| **Average** | **0.3477** | **0.3105** | **0.7833** | **0.5000** |

> Baseline de calidad de generación del pipeline grounded (recuperación semántica k=5 +
> generación con citación verificable). Se trae al directo para extenderlo midiendo el
> efecto de la detección de alucinaciones y del pipeline de evaluación completo.

**Notas de lectura (no son conclusiones del ejercicio):**
- `context_precision` alta (0.78): la recuperación coloca lo relevante arriba salvo en Q3 (data/ETL), el punto débil del corpus ya visto en la Sesión 10.
- `faithfulness` baja (0.35): hay afirmaciones del `answer` que el contexto no respalda; Q1 (0.10) es el extremo, ligado a que el generador marcó 4/5 líneas como `insufficient_data`.
- `answer_relevancy` baja con 0.00 en Q1 y Q4: respuestas dominadas por líneas "sin datos suficientes" se desvían de "estima este proyecto".
- `context_recall` = 0.50 constante en las 5 queries: casi seguro un artefacto (valor plano sospechoso), no una medida real; pendiente de revisar antes de usarlo como señal.
