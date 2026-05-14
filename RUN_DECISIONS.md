# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Spec deviation: Item 2 — Chandra sacrifice uses game.sacrifice()
- **TODO spec expected**: Token sacrifice at end of turn.
- **Actual codebase state**: Implementation used `move_to_zone()` directly, skipping sacrifice triggers.
- **What was implemented instead**: Changed to `game.sacrifice()` for proper sacrifice semantics.
- **Impact**: `cards/fdn/fdn_81/card_impl.py`
