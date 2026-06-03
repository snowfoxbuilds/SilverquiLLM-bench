---
name: tdd
description: >-
  Test-driven development with the red-green-refactor loop. Use when implementing a
  feature or card behavior test-first: write one failing test through the public
  interface, make it pass with minimal code, then refactor. Covers vertical
  tracer-bullet slicing (not all-tests-first) and testing behavior, not
  implementation details.
---

Test-driven development: grow code one failing test at a time. Tests verify **behavior through the
public interface**, never implementation details — a good test reads as a specification and survives
refactoring.

## The loop: red → green → refactor

1. **Red.** Write ONE test for the next slice of behavior. Run it; watch it fail for the *right*
   reason — the behavior is missing, not an import error or a typo.
2. **Green.** Write the **minimal** code to make that one test pass. No speculative features, no
   abstractions the test doesn't force.
3. **Refactor.** Only once green: remove duplication, simplify, deepen the module. Re-run tests; they
   must stay green. Then return to step 1 for the next behavior.

## Go vertical, not horizontal

**Anti-pattern:** writing all the tests first, then all the implementation. Batched tests verify
hypothetical structure (signatures, data shapes) rather than real behavior, and they lock you into a
design before you understand it. Instead use **tracer bullets**: one test → make it pass → next test.
Each cycle learns from the last.

## Test behavior, through the public interface

A good test exercises the real code path the way a real caller would and asserts an observable
outcome. A bad test couples to internals — it stubs internal collaborators, reaches past the public
API, or asserts private state — and it breaks under refactoring even though behavior is unchanged.

**In this engine, the public interface is `test_utils`:** `create_game`, `set_board_state`,
`cast_spell`, `advance_to_phase`, `declare_attackers`, `declare_blockers`. A spell is cast and
resolved by going through that path, the same way a player would. **Do not** hand-construct internal
event objects and fire them, pop the stack and call `on_resolve()` directly, or script a player's
internal decision queue — those tests pass while the real path is broken, which is exactly how a
self-authored suite gives false confidence. Assert spec-derived observables: zone changes, life
totals, P/T, counters, keyword presence, legal / illegal-target handling.

## Per-cycle checklist

- The test describes a behavior, not an implementation detail.
- It drives the card through `test_utils` (the public interface), not engine internals.
- It would survive an internal refactor.
- The code added is the minimum for this test — no speculative features.
- After green (and after any `engine/` change), `python3 -m pytest engine_tests/ -q` still passes.
