# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Hybrid mana parsing and cost payment

### Implementation
- `engine/types.py` — Added HybridManaSymbol dataclass, updated ManaCost with hybrid field and parse() to handle {X/Y} tokens
- `engine/mana.py` — Updated ManaPool.can_pay() and pay() with backtracking hybrid symbol resolution; fixed pay() to reserve explicit generic choices before hybrid solving
- `tests/engine/test_types.py` — Removed thin hybrid test (covered by test_hybrid_mana.py)

## Item 2: Cost reduction during casting

### Implementation
- `engine/card.py` — Added `cost_reduction(game) -> int` hook method to CardImpl (default 0)
- `engine/casting.py` — Added `get_cost_reduction()` and `_apply_cost_reduction()` functions; integrated into `cast_spell()` before mana payment
- `tests/engine/test_cost_reduction.py` — Tests for cost reduction clamping, application, and cast_spell integration

## Item 3: Protection from qualities (keyword ability)

### Implementation
- `engine/protection.py` — New module: ProtectionAbility class, get_colors(), has_protection_from(), and DEBT helper functions
- `engine/combat.py` — Added protection check in _can_block() and _deal_damage() to prevent blocking and combat damage from protected-from sources
- `engine/casting.py` — Added protection check in cast_spell() to reject targets with protection from the spell (T in DEBT)
- `engine/game.py` — Added protection check in deal_damage() to prevent damage from protected-from sources
- `engine/state_based_actions.py` — Extended _sba_aura_unattached() to detach auras and equipment from permanents with protection from them
- `tests/engine/test_protection.py` — 34 tests covering DEBT mnemonic (damage, enchanting, blocking, targeting)

## Item 4: Extra turns infrastructure (stub)

### Implementation
- `engine/game_state.py` — Added `extra_turns: list[int]` FIFO queue, `_normal_next_index` for tracking normal rotation independently; modified `advance_phase()` to pop extra turns without advancing normal rotation
- `tests/engine/test_extra_turns.py` — 9 tests for extra turn granting, FIFO ordering, and normal turn order resumption (3 tests expected to be updated by Tester for inserted-turn semantics)

