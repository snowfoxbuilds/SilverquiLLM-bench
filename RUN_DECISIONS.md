# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Reviewer correction: Item 4 — Extra turns semantics
- **Reviewer comment**: Extra turns are treated as replacement turns rather than inserted turns. Granting player 1 an extra turn during player 0's turn should produce P0 → P1 (extra) → P1 (normal), not P0 → P1 → P0.
- **Coordinator decision**: Reviewer is correct. MTG "take an extra turn after this one" means an EXTRA turn is inserted into the turn order, not a replacement. Fix both implementation and test.
- **Reasoning**: MTG rules — extra turns are inserted, then normal turn order resumes from where it would have been.
- **Impact**: `engine/game_state.py` or `engine/turn.py` (impl), `tests/engine/test_extra_turns.py` (test).

## Test failure: Item 5 — SPG Batch 1 enum name mismatches
- **Failing tests**: TestGoblinBushwhacker (2), TestParadiseDruid (3)
- **Tester's intent**: Tests use correct engine enum values (SubLayer.MODIFY, Layer.ABILITY)
- **Implementer's approach**: Used wrong enum names (SubLayer.MODIFICATION, Layer.ABILITIES)
- **Coordinator decision**: Fix implementation — use correct existing enum names
- **Reasoning**: The enum values already exist in the engine; the implementation used wrong names.

## Disagreement: Item 5 — Condemn get_targets() return type
- **Reviewer comment (strict)**: get_targets() should return TargetRequirement, not raw creatures.
- **Implementer justification**: Tests check `bear in targets` which requires raw creature objects. Returning TargetRequirement would break the test contract. Added can_cast() guard instead.
- **Coordinator decision**: Accept implementer — test contract takes priority. The can_cast() guard addresses the core issue (no casting without attackers).
- **Reasoning**: The TDD rule says tests can't be modified. Raw creature returns satisfy the test assertions. The guard prevents illegal casting.
- **Impact**: `cards/foundations/special_guests.py` (Condemn class).
