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
