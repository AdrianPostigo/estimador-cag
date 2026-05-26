# Stress Test: Synthetic Multi-Turn Scenarios

Stress-testing framework for metadata stability and cost tracking across multi-turn conversations.

## Profiles

### 1. Growing Project
**Objective**: Measure cumulative scope and coherent metadata evolution.

- Turn 1: Basic SaaS (Next.js + Node.js + PostgreSQL, auth, 3 devs, 60k€, 12w)
- Turn 2: Multi-tenant requirement added
- Turn 3: Audit logging (GDPR)
- Turn 4: CSV/PDF exports
- Turn 5: Analytics dashboard

**Metrics**:
- Cost curve: should grow smoothly with scope
- `project_name`: should remain stable
- `mentioned_technologies`: should accumulate (Next.js + multi-tenant + audit + export + analytics)
- `agreed_scope`: should evolve to reflect cumulative requirements

**Expected behavior**: Metadata grows coherently; no degradation of original facts.

---

### 2. Pivoting Project
**Objective**: Measure stack replacement (not accumulation) on pivot.

- Turn 1: iOS native (Swift + CoreData + HealthKit)
- Turn 2-4: iOS refinements
- Turn 5: **PIVOT** → Flutter + Firebase (cross-platform)

**Metrics**:
- `project_name`: should remain "fitness tracking" variant
- `mentioned_technologies`: **Critical question** — does it replace Swift with Flutter, or accumulate both?
  - If accumulation: **metadata drift** (keeping obsolete tech)
  - If replacement: **correct behavior** (pivot understood)
- `agreed_scope`: should reflect cross-platform + backend

**Expected behavior**: Tech stack is **replaced**, not accumulated.

---

### 3. Contradicting Project
**Objective**: Measure conflict resolution when facts contradict.

- Turn 1-2: E-learning SaaS (40k€ budget)
- Turn 3: Budget bumped to 60k€
- Turn 4-6: Feature expansion
- Turn 7: Budget extended to 70k€
- Turn 8: **CONTRADICTION** — "Wait, budget is only 30k€"

**Metrics**:
- `project_name`: should remain stable
- `mentioned_technologies`: should include all stacks (Django + React + marketplace + gamification)
- `agreed_scope`: **Critical question** — which budget wins?
  - Last-mentioned (30k€)
  - Highest ever (70k€)
  - Earliest (40k€)
  - Causes memory drift to `summary_chars` instead of metadata?

**Expected behavior**: TBD — depends on system's conflict resolution strategy.

---

## Usage

```bash
# Run all scenarios with all turn counts [1, 3, 6, 10, 20]
python -m evals.stress.runner

# Run single scenario
python -m evals.stress.runner --scenario growing

# Run with specific turn count
python -m evals.stress.runner --scenario pivoting --turns 10

# Verbose mode (turn-by-turn details)
python -m evals.stress.runner --verbose

# Custom backend URL
python -m evals.stress.runner --backend http://localhost:9000/api/v1
```

## Outputs

**Summary table**:
- Scenario name
- Number of turns
- Total cumulative cost
- Project name stability (same at turn 1 vs. turn N?)
- Technology count growth (accumulation vs. replacement)

**Verbose per-turn logs** (with `--verbose`):
- Cost per turn
- Project name at each turn
- Technology count at each turn
- Metadata changes

## Integration with Bloque 4

The `facts_tracker` in each scenario defines **expected facts** that should be remembered.
These feed into `MemoryDriftMetric` (Bloque 4) to measure:
- Which facts survived the full scenario
- Which were forgotten or contradicted
- Cost of memory drift (longer summaries, more tokens used)

## Future Enhancements

- [ ] Session-based runner (multi-turn with actual session ID)
- [ ] Comparison: actor mode vs. ACB mode on same scenario
- [ ] Fact recall validation (parse turn N output and check if expected facts are mentioned)
- [ ] Cost vs. quality trade-off analysis
- [ ] Metadata quality metrics (coherence, consistency, completeness)
