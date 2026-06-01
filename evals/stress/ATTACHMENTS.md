# Bloque 3: Stress Test de Adjuntos Grandes

Mide el impacto de adjuntos en latencia, costo, y coherencia de respuesta.

## Tamaños Calibrados

| Label | Size | Pages | Use Case |
|-------|------|-------|----------|
| `baseline` | 0 KB | N/A | Control (sin adjunto) |
| `small` | 5 KB | ~2 | Especificación técnica corta |
| `medium` | 20 KB | ~8 | Documento de requisitos típico |
| `large` | 50 KB | ~20 | RFP o caso de uso detallado |
| `huge` | 100 KB | ~40 | Documento completo (near cap) |

**Cap actual**: `MAX_ATTACHMENT_CHARS = 60,000` caracteres (≈ 60 KB de texto puro)

## Metodología

Para cada tamaño:

1. **Genera un PDF sintético** usando Lorem Ipsum repetido (tamaño calibrado)
2. **Ejecuta la misma estimación** con el mismo baseline transcript
3. **Adjunta el PDF** al request `/sessions/{id}/estimate`
4. **Mide tres curvas**:
   - **Latencia**: tiempo de respuesta (ms)
   - **Costo**: USD de tokens consumidos
   - **Recall**: ¿mencionó el resumen contenido del adjunto?

## Métricas Generadas

### Por cada tamaño:
- `tokens_in`: tokens consumidos por input (transcript + adjunto)
- `tokens_out`: tokens generados en respuesta
- `cost_usd`: costo total de esa estimación
- `latency_ms`: tiempo end-to-end
- `attachment_mentioned`: booleano (¿aparecen keywords del PDF en el summary?)
- `summary_length`: caracteres en project_summary

### Análisis de curvas:
- **Latency growth**: % de aumento de 0KB→100KB
- **Cost growth**: % de aumento de 0KB→100KB
- **Mention rate**: en cuántos summaries aparecen referencias al adjunto

## Expectativas

### Latencia
- Esperable: **sublineal** (no se dobla con cada 5KB)
- Problema: **exponencial** (significa token parsing ineficiente)

### Costo
- Esperable: **lineal** (más tokens = más costo)
- Problema: **supralineal** (overhead de procesamiento de adjuntos)

### Content Recall
- Esperable: **alta** en sizes small/medium, **degradación** en huge (info loss)
- Problema: **nula** en todos (adjunto ignorado completamente)

## Uso

```bash
# Run all sizes, simple output
python -m evals.stress.attachment_runner

# Verbose mode (show summaries)
python -m evals.stress.attachment_runner --verbose

# Save results to CSV
python -m evals.stress.attachment_runner --output attachment_results.csv

# Custom backend
python -m evals.stress.attachment_runner --backend http://localhost:9000/api/v1
```

## Salida Esperada

```
SUMMARY
═══════════════════════════════════════════════════════════════
Size Label    Size KB  Latency   Cost        Summary  Mentioned
─────────────────────────────────────────────────────────────────
baseline      0        125.3 ms  $0.000234   145      ✗
small         5        142.1 ms  $0.000876   182      ✓
medium        20       178.5 ms  $0.003456   219      ✓
large         50       245.3 ms  $0.008234   298      ✓
huge          100      387.2 ms  $0.015680   412      ✗ (truncated)
═══════════════════════════════════════════════════════════════

CURVE ANALYSIS:
Latency growth (0→100KB): 209.1%
Cost growth (0→100KB): 6685.5%
Attachment mentioned in 3/5 summaries
```

## Interpretación

- **Latency 209%**: razonable (más contenido = más procesamiento)
- **Cost 6685%**: alto pero esperado (tokens = cost)
- **Mention 3/5**: degradación en `huge` → info loss en tamaño máximo

## Integración con Bloque 4

Los resultados se reportan como:
- `attachment_latency_metric`: crece con tamaño
- `attachment_cost_metric`: exponencial con tamaño
- `attachment_recall_metric`: binario por tamaño

Estos alimentan `AttachmentStressMetric` para validar que el sistema
maneja adjuntos sin degradación crítica en coherencia.
