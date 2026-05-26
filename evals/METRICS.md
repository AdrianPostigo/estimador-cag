# Metrics Architecture

## Two-Tier Metric System

Métricas organizadas en dos módulos según su propósito y alcance:

### `evals/metrics.py` — Golden Dataset Metrics

Métricas generales para validar estimaciones contra golden cases.

| Metric | Evaluates | Returns |
|--------|-----------|---------|
| `SchemaAdherenceMetric` | EstimationOutput pasa Pydantic validation | `bool` |
| `CostBoundsMetric` | hours/weeks dentro de bounds realistas | `bool` |
| `ContentRecallMetric` | ≥70% de expected_keys mencionadas | `bool` |
| `LatencyBudgetMetric` | latency_ms ≤ budget_ms | `bool` |
| `CostBudgetMetric` | cost_usd ≤ budget_usd | `bool` |

**Used by**: `evals/runner.py` (golden dataset evals)

---

### `evals/stress/metrics.py` — Stress Test Metrics

Métricas específicas para escenarios multi-turno y stress.

| Metric | Evaluates | Returns |
|--------|-----------|---------|
| `MemoryDriftMetric` | Fact from turn k survives in turn N | `MetricResult` |
| `AttachmentRecallMetric` | Keywords del adjunto en summary | `MetricResult` |
| `MetadataCoherenceMetric` | Coherencia entre campos metadata | `MetricResult` |

**Used by**: `evals/stress/runner.py` (multi-turn scenarios)

---

## MetricResult Structure

```python
@dataclass
class MetricResult:
    name: str          # e.g., "MemoryDrift(Multi-tenant)"
    score: float       # 0.0 to 1.0
    passed: bool       # score >= 0.5
    details: str       # "Fact 'X' from turn 1 FOUND at turn 3. Found in: summary, metadata"
```

**Design principle**: Determinismo > sofisticación
- ✅ Exact match (case-insensitive)
- ❌ No embeddings, no LLM-as-judge, no fuzzy matching
- ❌ No hallucination risk

---

## Metric Usage Patterns

### Golden Dataset (evals/runner.py)

```python
metrics = [
    SchemaAdherenceMetric(),
    CostBoundsMetric(),
    ContentRecallMetric(),
    LatencyBudgetMetric(budget_ms=3000),      # 3s timeout
    CostBudgetMetric(budget_usd=0.01),        # 1 cent per call
]

for case in golden_cases:
    for metric in metrics:
        passed = metric.evaluate(output, golden_case)  # Returns bool
```

### Stress Test (evals/stress/runner.py)

```python
from evals.stress.scenarios import GROWING_PROJECT
from evals.stress.metrics import MemoryDriftMetric

# Track facts across turns
fact_metrics = [
    MemoryDriftMetric(
        fact="Next.js + Node.js + PostgreSQL",
        turn_introduced=1,
        where=["summary", "anchors", "metadata"]
    ),
    MemoryDriftMetric(
        fact="Multi-tenant",
        turn_introduced=2,
        where=["anchors", "summary"]
    ),
]

# Evaluate at final turn
for metric in fact_metrics:
    result = metric.evaluate(session_snapshot)  # Returns MetricResult
    print(f"{result.name}: {result.score:.2f} — {result.details}")
```

### Attachment Stress (evals/stress/attachment_runner.py)

```python
from evals.stress.metrics import AttachmentRecallMetric

attachment_metric = AttachmentRecallMetric(keywords=["lorem", "ipsum"])

for size_kb in [5, 20, 50, 100]:
    observation = {
        "project_summary": output["project_summary"],
        "attachment_size_kb": size_kb,
        "attachment_present": True,
    }
    result = attachment_metric.evaluate(observation)
    print(f"{size_kb}KB: {result.score:.2f} recall (keywords matched)")
```

---

## Justification: Two Modules

### ✅ Why separate `evals/metrics.py` and `evals/stress/metrics.py`?

| Aspect | Golden Dataset | Stress Test |
|--------|---|---|
| **Input** | EstimationOutput, golden_case dict | Observation dict, session snapshot |
| **Scope** | Single turn validation | Multi-turn fact retention |
| **Evaluation** | Stateless (output vs. expected) | Stateful (across turns) |
| **Result Type** | bool (pass/fail binary) | MetricResult (score + details) |
| **Integration** | evals/runner.py | evals/stress/runner.py |

### ✅ Why LatencyBudgetMetric and CostBudgetMetric in `evals/metrics.py`?

- **Generic**: work for any observation dict with latency_ms, cost_usd keys
- **Reusable**: used in both golden cases AND stress scenarios
- **Foundational**: budget constraints are baseline requirements

### ✅ Why MemoryDriftMetric in `evals/stress/metrics.py`?

- **Specific**: only meaningful in multi-turn scenarios
- **Stateful**: requires session snapshot with turn history
- **Not applicable**: to single-turn golden cases (no memory to drift)

---

## Design Principles

### 1. Determinism over sophistication
- ❌ No LLM eval ("does this summary capture the essence?")
- ✅ Exact string matching (case-insensitive)
- ✅ Keyword lists (declarative, auditable)

### 2. Transparency
- Every metric has `details` explaining WHY it passed/failed
- No black-box scores

### 3. Reusability
- Metrics work with generic dicts (observation, snapshot)
- No tight coupling to specific schemas
- Can be used in different contexts (runner.py, notebook, CLI)

### 4. Composability
- Multiple metrics can be evaluated on same observation
- Results aggregate for overall quality score

---

## Future Extensions

- `TokenEfficiencyMetric`: tokens_out / cost_usd (value per token)
- `TimelineAccuracyMetric`: estimated weeks vs. historical data
- `RiskCoverageMetric`: ≥2 risks listed for projects >100h
- `AssumeComplenessMetric`: ≥3 assumptions for vague inputs
- `TierStabilityMetric`: same tier resolved in repeated calls
