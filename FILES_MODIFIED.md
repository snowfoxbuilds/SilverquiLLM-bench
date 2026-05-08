# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.


## Item 1: Fix is_aura default True in _sba_aura_unattached

### Implementation
- `engine/state_based_actions.py` — Changed getattr default for is_aura from True to False

## Item 2: Wire SBA trigger queueing in resolve_state_based_actions()

### Tests
- `tests/engine/test_state_based_actions.py` — Existing SBA tests (56 passed, no new test file from tester)

### Implementation
- `engine/state_based_actions.py` — Fire CREATURE_DIES/LEAVES_BATTLEFIELD events in _move_to_graveyard(); add trigger-aware outer loop in resolve_state_based_actions()

## Item 3: Centralize zone-transition hooks into move_to_zone()

### Implementation
- `engine/zones.py` — Added move_to_zone() function with replacement effects, event firing, and trigger registration/unregistration hooks
- `engine/game.py` — Refactored destroy(), sacrifice(), exile() to delegate to move_to_zone()
- `engine/state_based_actions.py` — Refactored _move_to_graveyard() to delegate to move_to_zone()
- `engine/casting.py` — Refactored _resolve_spell() to use move_to_zone() for both permanent (STACK→BATTLEFIELD) and non-permanent (STACK→GRAVEYARD) spells
