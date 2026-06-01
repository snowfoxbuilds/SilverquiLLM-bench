Status: DRAFT (rewritten for container architecture)

Last updated: 2026-05-13

# Scoring

Three evaluation dimensions. No composite score.

## Context

The evaluator runs audited tests against the agent's output after the container exits. Agent tests are harvested as artifacts but not used for scoring in v1. Blind vs. tested mode comparisons are made across separate runs (different images), not as separate scoring categories.

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

### Complexity Weighting

| Tier | Criteria | Weight |
| --- | --- | --- |
| Trivial | Vanilla creatures, basic lands, no rules text | 1x |
| Simple | Single keyword or one straightforward ability | 2x |
| Medium | Multiple abilities, triggers, or targeting | 3x |
| Complex | Multi-step abilities, replacement effects, modal spells | 4x |
| Expert | Planeswalkers, complex state machines, unusual mechanics | 5x |

Weighted Score = Σ(w_c × pass(c)) / Σ(w_c), where pass(c) = 1 if all audited tests pass, 0 otherwise. Applied to Dimension 1 only.

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

## Decisions

- **Three evaluation dimensions**: SOS card correctness, FDN card regression, engine regression. Each measured independently. [SETTLED]
- **Audited tests only for v1**: Agent tests are harvested as artifacts but not used for scoring. Cross-eval and self-eval deferred to future test harvester. [SETTLED]
- **No blind vs. tested scoring categories**: Mode is baked into the image. Compare modes by running different images and comparing Dimension 1 results. [SETTLED]
- **Complexity weighting on Dimension 1 only**: FDN and engine regression are pass/fail — no weighting needed. [SETTLED]
- **Raw scores only**: No statistical significance tests or confidence intervals. [SETTLED]
- **Grilling 2026-05-13: Simplified from 4 categories**: Former Category 1 (blind) and Category 2 (tested) merged into single SOS correctness dimension. Former Category 3 (test quality) deferred. Former Category 4 (engine extension) split into FDN regression + engine regression. [SETTLED]
