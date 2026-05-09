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

