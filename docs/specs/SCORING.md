Status: DRAFT

Last updated: 2026-10-02

# Scoring

Three evaluation dimensions, scored independently with no composite score and raw scores only — no statistical significance tests or confidence intervals.

## Context

The evaluator runs audited tests against the agent's output after the container exits. Agent tests are harvested as artifacts but not used for scoring in v1. Blind vs. tested mode comparisons are made across separate runs (different images), not as separate scoring categories.

This spec covers SOS (V1) scoring: the complexity-tier weighting here applies to SOS only, while the HOB-generation benchmarks (hob-easy/medium/hard) drop complexity tiers and score raw pass/total (see [HOB-BENCHMARKS.md](HOB-BENCHMARKS.md) → Evaluation).

## Design

### Dimension 1: SOS Card Correctness

Measures how well the agent implemented the target cards.

| Metric | Definition |
| --- | --- |
| Audited test pass rate | % of SOS audited tests passed by `card_impl.py` across all cards |
| Card pass rate | % of SOS cards where `card_impl.py` passes ALL audited tests |
| Weighted score | Card pass rate weighted by complexity tier |

### Dimension 2: FDN Card Regression

Measures whether the agent's engine extensions broke existing card behavior. FDN audited tests (`tests/audited/fdn/`) are run against the pre-filled FDN `card_impl.py` files using the agent's final engine.

| Metric | Definition |
| --- | --- |
| FDN test pass rate | % of FDN audited tests that still pass against the agent's final engine |
| FDN card pass rate | % of FDN cards where ALL audited tests still pass |

### Dimension 3: Engine Regression

Measures whether the agent's engine extensions broke fundamental game mechanics. Engine tests are run against the agent's final engine.

| Metric | Definition |
| --- | --- |
| Engine test pass rate | % of core engine tests that still pass against the agent's final engine |
| Engine churn | Total lines changed in `engine_diff.patch` |

FDN Card Regression and Engine Regression are intertwined (both test the engine at different levels) but measure different things: Dimension 2 catches broken card behavior, Dimension 3 catches broken rules mechanics. An agent could pass all FDN card tests but fail engine tests if it hacked card-level workarounds that corrupt internal state.

These three dimensions were simplified from an earlier four-category scheme (grilling 2026-05-13): the former blind and tested categories merged into the single SOS Card Correctness dimension, the former test-quality category was deferred (see Future Work), and the former engine-extension category was split into FDN Card Regression and Engine Regression.

### Agent envelope (HOB-generation benchmarks)

For the HOB-generation benchmarks (hob-easy/medium/hard), the Writable Engine is **freely modifiable** — there is no additive-only rule and no diff policing (a departure from the SOS V1 contract; see [WORKSPACE-CONTRACT.md](WORKSPACE-CONTRACT.md) and [HOB-BENCHMARKS.md](HOB-BENCHMARKS.md) → Engine rules). The entire judgment is the same three audited dimensions, all run against the harvested engine, with **HOB Card Correctness** replacing SOS Card Correctness for this generation:

1. **HOB Card Correctness** — audited HOB tests against the agent's `card_impl.py` + harvested `/workspace/engine/`.
2. **FDN Card Regression** — audited FDN tests against the pre-filled FDN impls + harvested `/workspace/engine/`.
3. **Engine Regression** — core engine tests against the harvested `/workspace/engine/`.

Audited tests judge card behavior by simulating gameplay (Implementation-Agnostic Testing), so **any** engine change — including renames and refactors — is permitted; it is judged solely by its observable consequences on these three dimensions. Engine churn (`engine_diff.patch`) stays a **diagnostic** metric only: it is never scored and never policed. HOB-generation benchmarks score raw pass/total — the complexity weighting below is SOS-only.

### Regression reference scores

For benchmarks built from the Known-Best Workspace (smoke, fra-hard, and later), the FDN Card Regression and Engine Regression Audited Tests are pooled into one Combined Regression, reported as its raw pass/total next to two reference points (grilling 2026-10-02).
Each regression dimension keeps its own raw pass/total for diagnosis.

| Metric | Definition |
| --- | --- |
| Raw score | Audited Tests passed / total against the agent's final engine — the score itself |
| Baseline Score | The unmodified Workspace's pass/total, from the baseline reference grade for the same grading inputs and Workspace |
| Known-Best Score | Always total/total: the Test Oracle Workspace passes every regression Audited Test |
| Fixed | Audited Tests that fail on the baseline and pass for the agent |
| Regressed | Audited Tests that pass on the baseline and fail for the agent |

There is no normalized score: an agent can land below its Baseline Score, and fixing three Known Defects while breaking three cards is reported as exactly that, not as no change.
The Baseline Score and the per-test baseline outcomes come from [KNOWN-BEST-ENGINE.md](KNOWN-BEST-ENGINE.md) → Baseline reference grade.
Engine Regression grades the hidden Audited Engine Tests, never the Workspace's Engine Reference Tests; hob-medium and SOS, frozen before that split, grade from the host copy of their staged engine tests.

Combined Regression is a report pooled over two dimensions, not a fourth dimension, so it sits beside the scores rather than in them: at `run_metadata["combined_regression"]` in a Run Record, and as a top-level `combined_regression` in each regrade output.
A Run Record carries it only for a benchmark with a Known Defect manifest whose grading ran; every regrade output of such a benchmark carries it.

```json
{
  "available": true,
  "tests_passed": 1821,
  "tests_total": 1831,
  "pass_rate": 0.99454,
  "baseline_score":   {"tests_passed": 1820, "tests_total": 1831},
  "known_best_score": {"tests_passed": 1831, "tests_total": 1831},
  "fixed": {
    "count": 2,
    "test_nodes": {
      "fdn_regression": ["fdn_66/tests.py::test_dies_returns_with_one_fewer_revival"],
      "engine_regression": ["zone_change/test_lki.py::test_counters_reset"]
    }
  },
  "regressed": {
    "count": 1,
    "test_nodes": {"fdn_regression": [], "engine_regression": ["test_combat.py::test_first_strike_damage"]}
  },
  "baseline": {
    "grading_inputs_digest": "sha256:…",
    "grading_code_digest": "sha256:…",
    "workspace_digest": "sha256:…",
    "grader_image_id": "sha256:…"
  }
}
```

- `tests_passed` and `tests_total` are the sums of the two dimensions' raw counts; `baseline_score` sums the baseline reference grade's, and `known_best_score` is its total over its total.
- `fixed` and `regressed` list, per suite and sorted, the Audited Tests whose outcome moved from the baseline's; a baseline-passing test the run no longer executes counts as Regressed, and a test the baseline never ran is ignored.
- `baseline` names the baseline reference grade's key.

When the block cannot be computed it is `{"available": false, "reason": "<reason>"}`, with the first reason that applies:

| Reason | When |
| --- | --- |
| `grading_inputs_changed_during_grading` | The grading inputs changed while the run was graded |
| `regression_not_evaluated` | Either regression dimension executed no test for the run |
| `baseline_workspace_incomplete` | The unmodified Workspace could not be copied in full |
| `baseline_grading_failed:<reason>` | Grading the unmodified Workspace failed |
| `baseline_incomplete` | The baseline reference grade is incomplete for any reason but the FDN coverage gap every run shares |

### Complexity Weighting

| Tier | Criteria | Weight |
| --- | --- | --- |
| Trivial | Vanilla creatures, basic lands, no rules text | 1x |
| Simple | Single keyword or one straightforward ability | 2x |
| Medium | Multiple abilities, triggers, or targeting | 3x |
| Complex | Multi-step abilities, replacement effects, modal spells | 4x |
| Expert | Planeswalkers, complex state machines, unusual mechanics | 5x |

Weighted Score = Σ(w_c × pass(c)) / Σ(w_c), where pass(c) = 1 if all audited tests pass, 0 otherwise. Applied to Dimension 1 only; FDN and engine regression are pass/fail and need no weighting.

Tiers assigned via automated heuristics: rules text length, keyword count, ability count, target requirements, zone interactions, card type. Thresholds calibrated from target set distribution.

### Secondary Metrics

**Per-category breakdown**: Pass rates by test category (basic, ability, edge, interaction, rules).

**Complexity tier breakdown**: Card pass rates per tier per model.

**Error classification**: Syntax errors, import errors, logic errors, missing implementation, rules misunderstanding.

**Efficiency metrics**: Tokens per card, cost per card, time per card, pass rate per dollar.

**FDN regression details**: List of FDN audited tests that fail against the agent's final engine, with failure messages.

**Engine regression details**: List of core engine tests that fail against the agent's final engine, with failure messages.

### Leaderboard Format

```javascript
SOS Card Correctness
| Rank | Image                          | Audited | Card Pass | Weighted |
|------|--------------------------------|---------|-----------|----------|
| 1    | opencode-tested (opus-4)       | 72.3%   | 48.1%     | 44.2%    |
| 2    | opencode-blind (opus-4)        | 65.1%   | 40.0%     | 36.8%    |
| 3    | claude-code-tested (opus-4)    | 69.8%   | 44.0%     | 40.8%    |

Regression Summary
| Image                          | FDN Card Pass | Engine Pass | Engine Churn |
|--------------------------------|---------------|-------------|-------------|
| opencode-tested (opus-4)       | 100%          | 98.5%       | 342 lines   |
| opencode-blind (opus-4)        | 100%          | 100%        | 128 lines   |
| claude-code-tested (opus-4)    | 97.2%         | 95.0%       | 891 lines   |
```

(Example format — not real results)

### Future Work

**Cross-eval**: Run each agent's tests against every other agent's implementations (N×N matrix). Requires a test harvester to collect and validate agent-written tests.

**Self-eval**: Run each agent's tests against its own implementations. Useful for measuring self-serving test bias.

**Test Quality scoring**: Audit survival rate, discrimination score, difficulty calibration, coverage. Requires cross-eval infrastructure.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-016](../adr/ADR-016-baseline-engines-may-carry-known-defects.md) | Baseline engines may carry Known Defects, scored against a separate Known-Best Engine |
