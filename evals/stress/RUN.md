# Bloque 5: Stress Test Runner

Orquestador que ejecuta la suite completa de stress tests y genera reportes.

## Quick Start

```bash
# Run all scenarios, all attachment sizes, 1 repeat
uv run python -m evals.stress.run

# Run specific scenarios + attachment sizes, 3 repeats
uv run python -m evals.stress.run \
    --scenarios growing,pivot \
    --attachment-sizes 0,5,20,50 \
    --repeats 3

# Verbose mode (see every turn)
uv run python -m evals.stress.run --verbose

# Custom backend URL
uv run python -m evals.stress.run --http http://localhost:9000/api/v1

# Save to custom output file
uv run python -m evals.stress.run --output my_results.csv
```

## What It Does

### Phase 1: Scenario Stress Tests

Ejecuta cada escenario (`growing`, `pivot`, `contradiction`) con N repeats:

```
Scenario: growing
  Turn 1: 142.3ms, $0.000876, techs=3
  Turn 2: 168.5ms, $0.001234, techs=4
  Turn 3: 189.2ms, $0.001567, techs=5
  ...
```

**Metrics per turn**:
- `tokens_in`, `tokens_out`: consumo de tokens
- `cost_usd`: costo de esa estimación
- `latency_ms`: tiempo end-to-end
- `project_name`: nombre capturado (estabilidad)
- `tech_count`: número de tecnologías mencionadas (acumulación)
- `summary_len`: tamaño de project_summary

### Phase 2: Attachment Stress Tests

Ejecuta baseline con adjuntos de creciente tamaño (0, 5, 20, 50, 100 KB):

```
Attachment size: 0 KB
  125.3ms, $0.000234, summary=145 chars
Attachment size: 5 KB
  142.1ms, $0.000876, summary=182 chars
Attachment size: 20 KB
  178.5ms, $0.003456, summary=219 chars
...
```

### Output: CSV + Report

1. **results.csv**: Una fila por turno/attachment, todas las métricas
2. **results_REPORT.md**: Análisis con:
   - Tabla resumen (P50/P95 latencia, costo acumulado)
   - Curvas (latencia trend, cost accumulation)
   - Dos párrafos sobre dónde se rompe

## CSV Format

| scenario | repeat | turn | tokens_in | tokens_out | cost_usd | latency_ms | project_name | tech_count | summary_len |
|----------|--------|------|-----------|-----------|----------|-----------|--------------|-----------|------------|
| growing | 1 | 1 | 245 | 156 | 0.000876 | 142.3 | Plataforma SaaS... | 3 | 245 |
| growing | 1 | 2 | 289 | 178 | 0.001234 | 168.5 | Plataforma SaaS... | 4 | 289 |
| pivot | 1 | 5 | 312 | 198 | 0.001567 | 189.2 | Fitness app | 2 | 312 |
| attachment_5kb | 1 | 1 | 312 | 198 | 0.000876 | 142.1 | Plataforma SaaS... | 3 | 182 |
| attachment_100kb | 1 | 1 | 1245 | 567 | 0.015680 | 387.2 | Plataforma SaaS... | 3 | 412 |

## Report Structure

```markdown
# Stress Test Report

## Summary
- Total runs: 45
- Total cost: $0.245
- P50 latency: 168.5ms
- P95 latency: 312.4ms

## Results by Scenario
| Scenario | Runs | Total Cost | Avg Latency | Max Latency |
|----------|------|-----------|------------|------------|
| growing | 15 | $0.067 | 165.2ms | 289.4ms |
| pivot | 15 | $0.072 | 171.3ms | 298.1ms |
| contradiction | 15 | $0.106 | 189.2ms | 412.3ms |

## Latency Trend
[ASCII bar chart]

## Cost Accumulation
[Table with cumulative costs per turn]

## Analysis
Dos párrafos sobre:
- Dónde empieza a romperse
- Por qué
- Recomendaciones
```

## Interpreting Results

### Good Signs ✓
- P95 latency < 500ms (user-acceptable)
- Cost growth linear with tokens (no overhead surprises)
- project_name stable across turns (metadata coherence)
- Attachment recall > 80% for sizes < 50KB

### Red Flags ✗
- P95 latency > 1000ms (slow for real-time)
- tech_count grows unbounded (metadata drift)
- Cost 10x+ higher than expected (inefficiency)
- Attachment recall < 50% (content loss)

## Integration with Metrics

The runner implicitly evaluates these metrics:

| Metric | Measured | Threshold |
|--------|----------|-----------|
| LatencyBudgetMetric | latency_ms per row | P95 < 500ms |
| CostBudgetMetric | cost_usd per row | < $0.01/call |
| MemoryDriftMetric | project_name stability | stable across repeats |
| AttachmentRecallMetric | summary_len vs. attachment_kb | > 0.5 correlation |

## Advanced Usage

### Run in CI/CD

```yaml
# .github/workflows/stress-test.yml
- name: Run stress tests
  run: |
    uv run python -m evals.stress.run \
      --scenarios growing,pivot,contradiction \
      --repeats 2 \
      --output stress_results.csv
  
- name: Check latency budget
  run: |
    python -c "
    import csv
    with open('stress_results.csv') as f:
        reader = csv.DictReader(f)
        p95 = sorted([float(r['latency_ms']) for r in reader])[int(0.95 * len(list(reader)))]
    assert p95 < 500, f'P95 latency {p95}ms exceeds budget 500ms'
    "
```

### Compare Runs

```bash
# Baseline
uv run python -m evals.stress.run --output baseline.csv

# After optimization
uv run python -m evals.stress.run --output optimized.csv

# Compare (external tool)
python compare_csv.py baseline.csv optimized.csv
```

## Troubleshooting

**ERROR: Connection refused**
- Make sure backend is running: `uv run python -m uvicorn app.main:app --reload`

**ERROR: Session not found**
- Backend and client might be out of sync; restart both

**CSV is empty**
- Check verbose output for specific error messages
- Validate backend responses with curl

**Report not generated**
- Check if results.csv exists and has data
- Ensure write permissions in evals/stress/

## Next Steps

1. Run baseline: `uv run python -m evals.stress.run --output baseline.csv`
2. Analyze report: `cat baseline.csv_REPORT.md`
3. Identify bottlenecks
4. Optimize and re-run: `uv run python -m evals.stress.run --output optimized.csv`
5. Compare metrics
