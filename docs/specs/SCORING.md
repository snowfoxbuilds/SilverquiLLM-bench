Status: SETTLED

Last updated: 2026-04-28

# Scoring

Three independent scoring categories. No composite score.

## Context

SilverquiLLM-bench evaluates three distinct skills — implementation from spec, iterative debugging, and test writing — so each gets its own leaderboard.

## Design

### Category 1: Blind Implementation

Measures pure spec-to-code ability (no tests to guide the agent).

| Metric | Definition |
| --- | --- |
| Audited test pass rate | % of audited tests passed by `blind_impl.py` across all cards |
| Card pass rate | % of cards where `blind_impl.py` passes ALL audited tests |
| Cross-eval pass rate | Average pass rate of `blind_impl.py` against other agents' tests |
| Weighted score | Card pass rate weighted by complexity tier |

### Category 2: Implementation with Tests

Measures improvement through test-driven iteration. Delta from Category 1 reveals debugging ability.

| Metric | Definition |
| --- | --- |
| Audited test pass rate | % of audited tests passed by `tested_impl.py` across all cards |
| Card pass rate | % of cards where `tested_impl.py` passes ALL audited tests |
| Cross-eval pass rate | Average pass rate of `tested_impl.py` against other agents' tests |
| Weighted score | Card pass rate weighted by complexity tier |
| Improvement delta | Category 2 audited pass rate − Category 1 audited pass rate |

### Category 3: Test Quality

Measures how good the agent's tests are. Ideal tests are valid and not every agent passes them.

| Metric | Definition |
| --- | --- |
| Audit survival rate | % of agent's tests that survived human audit (correct + non-trivial) |
| Discrimination score | Variance in pass rates across agents' implementations (high = good differentiation) |
| Difficulty calibration | Fraction of tests passed by some but not all agents (the "sweet spot") |
| Coverage | % of audited test behaviors covered by agent's test suite |

A test passed by all agents is trivial. A test failed by all agents is likely wrong. The most valuable tests differentiate between strong and weak implementations.

### Complexity Weighting

| Tier | Criteria | Weight |
| --- | --- | --- |
| Trivial | Vanilla creatures, basic lands, no rules text | 1x |
| Simple | Single keyword or one straightforward ability | 2x |
| Medium | Multiple abilities, triggers, or targeting | 3x |
| Complex | Multi-step abilities, replacement effects, modal spells | 4x |
| Expert | Planeswalkers, complex state machines, unusual mechanics | 5x |

Weighted Score = Σ(w_c × pass(c)) / Σ(w_c), where pass(c) = 1 if all audited tests pass, 0 otherwise. Applied to both Category 1 and Category 2.

Tiers assigned via automated heuristics: rules text length, keyword count, ability count, target requirements, zone interactions, card type. Thresholds calibrated from target set distribution.

### Category 4: Engine Extension Quality

Measures the agent's ability to extend the shared engine without breaking existing cards. Only applies when the persistent-engine model is used (cards processed sequentially with a shared writable engine per run).

| Metric | Definition |
| --- | --- |
| Regression rate | % of cards whose tests broke due to engine changes made for a later card |
| Regression-free streak | Longest consecutive sequence of cards completed without any regression |
| Engine churn | Total lines changed in engine/ across all cards (lower = cleaner extensions) |
| Mechanic reuse rate | % of cards that reused an engine mechanic added by a previous card (vs. adding a new one) |

A perfect score means the agent extended the engine for every card that needed it, and no engine change ever broke a previously-passing test. High churn with low regression = acceptable (the agent extended a lot but cleanly). High regression = the agent writes brittle, card-specific hacks.

### Secondary Metrics

**Per-category breakdown**: Pass rates by test category (basic, ability, edge, interaction, rules).

**Complexity tier breakdown**: Card pass rates per tier per model.

**Error classification**: Syntax errors, import errors, logic errors, missing implementation, rules misunderstanding.

**Efficiency metrics**: Tokens per card, cost per card, time per card, pass rate per dollar.

**Regression details**: Per-card list of which earlier cards' tests broke and what engine change caused it.

### Leaderboard Format

```javascript
Category 1: Blind Implementation
| Rank | Model          | Audited | Card Pass | Cross-Eval | Weighted |
|------|----------------|---------|-----------|------------|----------|
| 1    | Claude Opus 4  | 72.3%   | 48.1%     | 68.5%      | 44.2%    |
| 2    | GPT-5          | 69.8%   | 44.0%     | 65.2%      | 40.8%    |

Category 2: Implementation with Tests
| Rank | Model          | Audited | Card Pass | Cross-Eval | Weighted | Delta |
|------|----------------|---------|-----------|------------|----------|-------|
| 1    | Claude Opus 4  | 84.7%   | 65.2%     | 80.1%      | 61.5%    | +12.4 |
| 2    | GPT-5          | 81.3%   | 60.8%     | 76.8%      | 57.2%    | +11.5 |

Category 3: Test Quality
| Rank | Model          | Audit Survival | Discrimination | Difficulty Cal. | Coverage |
|------|----------------|----------------|----------------|-----------------|----------|
| 1    | Claude Opus 4  | 82%            | 0.71           | 64%             | 68%      |
| 2    | GPT-5          | 78%            | 0.65           | 58%             | 63%      |
```

(Example format — not real results)

## Decisions

- **Three independent categories**: Blind impl, tested impl, and test quality scored separately. No composite. [SETTLED]
- **Raw scores only**: No statistical significance tests or confidence intervals. [SETTLED]
- **Difficulty calibration metric**: Rewards tests in the sweet spot (some agents pass, others don't). [SETTLED]
- **Self-serving bias tracked**: Self-eval pass rate − cross-eval pass rate. High bias = agent writes easy tests. [SETTLED]
- **Category 4 (Engine Extension Quality)**: Measures regression rate, engine churn, and mechanic reuse when agents extend the shared engine across cards. [SETTLED]
