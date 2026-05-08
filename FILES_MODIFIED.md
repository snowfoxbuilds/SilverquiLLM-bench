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
