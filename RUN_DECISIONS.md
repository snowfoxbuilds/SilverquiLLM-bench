# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Disagreement: Item 3 — Card complexity classifier (keyword-only tier)
- **Reviewer comment (strict)**: Test encodes wrong heuristic — keyword-only creature should be "simple" not "trivial", citing "Single keyword or one straightforward ability" in Simple tier.
- **Implementer justification**: The Trivial tier definition explicitly includes "just keyword abilities" — a creature with only keywords (e.g., Flying) is trivial.
- **Coordinator decision**: accept implementer
- **Reasoning**: The TODO text under Trivial says "No rules text or just keyword abilities, vanilla creatures, basic lands." The word "just" distinguishes keyword-only cards from cards with substantive abilities. The Simple tier's "single keyword" refers to cards that also have a non-keyword ability. The test correctly asserts keyword-only → trivial.
- **Impact**: benchmark/card_classifier.py, tests/test_card_classifier.py — keyword-only creatures remain trivial tier.

## Test failure potential: Item 3 — Targeted spells classification
- **Issue**: Targeted spells falling through to "simple" instead of "medium"
- **Coordinator decision**: fix implementation (targeted spells should be "medium") and fix the test that was too permissive
- **Reasoning**: TODO explicitly lists "targeting" as a Medium-tier signal.

## Spec deviation: Item 13 — Scoring calculator discrimination/difficulty granularity
- **TODO spec expected**: "variance in pass rates across agents' implementations for each test" and "fraction of tests passed by some but not all agents" — per-test granularity.
- **Actual codebase state**: `EvalResult` from item 12 only stores aggregate counts (`blind_passed`, `blind_failed`, `blind_total`), not per-test pass/fail vectors. Per-test discrimination is impossible with the current data model.
- **What was implemented instead**: Per-card approximation using suite-level pass ratios. This is the best possible with the current `EvalResult` contract.
- **Impact**: `benchmark/scorer.py` — discrimination_score and difficulty_calibration are card-level approximations. When `EvalResult` is extended with per-test vectors, these metrics should be updated.

## Disagreement: Item 15 — Gap analysis scope
- **Reviewer comment (strict)**: analyze_engine_gaps should always check all 4 mechanics (Prepared, Converge, Miracle, Opus) regardless of selected cards.
- **Implementer justification**: Function contract takes `cards` as input, scoping analysis to those cards' mechanics. Test `test_no_gaps_for_vanilla_cards` asserts `[]` for vanilla cards. Improved card selection now scores for mechanic coverage, so all 4 mechanics are naturally represented.
- **Coordinator decision**: accept implementer
- **Reasoning**: The function's contract is to analyze gaps for provided cards. The improved tier-scoring ensures complex/expert selections exercise Prepared/Converge/Miracle/Opus, so the prototype set naturally covers all mechanics. Always checking all 4 regardless of input would change the function's semantics.
- **Impact**: benchmark/prototype.py — gap analysis remains card-scoped.

## Disagreement: Item 16 — Converge generic mana choice
- **Reviewer comment (strict)**: cast_spell() doesn't let the caster choose how generic mana is spent, so Converge color count is wrong when multiple payment mixes exist.
- **Implementer justification**: N/A (no disagreement filed)
- **Coordinator decision**: Accept as known limitation, add # TODO comment
- **Reasoning**: The TODO explicitly says "Do NOT over-engineer: only implement what the 5 prototype cards require. Leave stubs with # TODO for unused branches." Supporting player mana choice for generic costs would require significant casting pipeline changes beyond prototype scope. The auto-pay correctly records colors for the common case. Full mana choice support is a Phase 3 concern.
- **Impact**: engine/casting.py — Converge color count may be suboptimal with generic mana.
