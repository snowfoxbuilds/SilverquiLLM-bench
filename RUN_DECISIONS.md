# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Reviewer correction: Item 4 — Extra turns semantics
- **Reviewer comment**: Extra turns are treated as replacement turns rather than inserted turns. Granting player 1 an extra turn during player 0's turn should produce P0 → P1 (extra) → P1 (normal), not P0 → P1 → P0.
- **Coordinator decision**: Reviewer is correct. MTG "take an extra turn after this one" means an EXTRA turn is inserted into the turn order, not a replacement. Fix both implementation and test.
- **Reasoning**: MTG rules — extra turns are inserted, then normal turn order resumes from where it would have been.
- **Impact**: `engine/game_state.py` or `engine/turn.py` (impl), `tests/engine/test_extra_turns.py` (test).
