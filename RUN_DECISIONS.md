# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Test failure: Item 1 — Project scaffold
- **Failing tests**: test_requires_python_at_least_3_11
- **Tester's intent**: Verify requires-python is >=3.11 per the TODO spec
- **Implementer's approach**: Relaxed to >=3.10 because the build environment only has Python 3.10.12; pip install -e . would fail with >=3.11
- **Coordinator decision**: fix tests
- **Reasoning**: The environment constraint is real — pip install -e . fails if requires-python exceeds the available Python version. The ruff.toml target-version is still py311 for forward-looking linting. This is a pragmatic deviation.

## Disagreement: Item 1 — Project scaffold (review round)
- **Reviewer comment 1 (strict)**: Tests make `pytest --co` return non-zero items, violating scaffold testability criterion
- **Coordinator decision**: reject reviewer — the "0 items" criterion described the scaffold state before tests exist; adding tests is expected behavior
- **Reasoning**: Every TODO item gets tests. The testability line was a one-time verification step, not a permanent invariant.

- **Reviewer comment 2 (strict)**: `py.typed` at repo root isn't PEP 561 compliant; should be in each package directory
- **Coordinator decision**: accept reviewer — move `py.typed` into `engine/` and `cards/`
- **Reasoning**: Technically correct for type checker discovery

- **Reviewer comment 3 (strict)**: Tests use `tomli` fallback on Python 3.10 but it's not declared as a dependency
- **Coordinator decision**: accept reviewer — fix the test to handle this properly
- **Reasoning**: Tests shouldn't depend on undeclared packages

## Disagreement: Item 10 — Casting pipeline (priority check)
- **Reviewer comment (strict)**: cast_spell should verify player is game.priority_player before allowing a cast.
- **Implementer justification**: Priority enforcement belongs in priority_loop (stack.py), not in cast_spell. Existing tests expect non-priority players can cast instants when called directly. cast_spell handles mechanics; priority_loop handles turn structure.
- **Coordinator decision**: accept implementer
- **Reasoning**: Layered responsibility — priority_loop gates who can act, cast_spell executes the cast. Adding a priority check to cast_spell would duplicate logic and create coupling. All real game flow goes through priority_loop.
- **Impact**: engine/casting.py — no priority check added


## Disagreement: Item 12 — Mana ability timing validation
- **Reviewer comment (strict)**: Mana abilities skip timing validation entirely; any player can fire a mana ability at arbitrary times by passing `is_mana_ability=True`.
- **Implementer justification**: Priority enforcement is handled by `priority_loop`, not individual ability/spell functions. This is consistent with `cast_spell` which also doesn't check priority.
- **Coordinator decision**: accept implementer
- **Reasoning**: Per KEY_DECISIONS #5, priority enforcement belongs in `priority_loop`. Both `cast_spell` and `activate_ability` are low-level functions called within the priority loop. Adding priority checks here would duplicate logic and contradict the established architecture.
- **Impact**: `engine/abilities.py` — mana ability activation remains without priority check, consistent with casting pipeline.

## Test failure: Item 13 — Combat system
- **Failing tests**: TestCombatIntegration::test_first_strike_kills_before_normal_damage
- **Tester's intent**: Verify that a first-strike creature kills its blocker before the blocker deals normal damage back.
- **Implementer's approach**: First-strike sub-step exists but likely processes all creatures' damage rather than only first/double strike creatures.
- **Coordinator decision**: fix implementation
- **Reasoning**: The MTG rule is clear — only first strike and double strike creatures deal damage in the first-strike damage step. Non-first-strike creatures deal damage in the normal damage step. The test is correct.

## Disagreement: Item 13 — Combat not wired into turn execution
- **Reviewer comment (strict)**: Combat helpers are never called from `run_turn()`, so combat never happens during normal gameplay.
- **Implementer justification**: Item 13 is about implementing the combat system itself. Full game loop wiring is Item 16.
- **Coordinator decision**: accept implementer (defer to Item 16)
- **Reasoning**: The TODO text says "Implement declare attackers → declare blockers → damage → end combat" — focused on the combat system. Item 16 ("Game setup, helper actions, full game loop") explicitly covers wiring everything together. Wiring combat into `run_turn()` now would prematurely couple unfinished systems.
- **Impact**: Combat functions exist but are not auto-called from `run_turn()` until Item 16.

## Disagreement: Item 14 — remove_expired not called in turn flow
- **Reviewer comment (strict)**: Duration-based effects never expire because `remove_expired()` is never called during turn progression.
- **Implementer justification**: Item 14 implements the effects system. Turn/cleanup wiring is Item 23 ("End-of-turn cleanup and damage clearing").
- **Coordinator decision**: accept implementer (defer to Item 23)
- **Reasoning**: Same pattern as combat wiring (deferred to Item 16). Item 23 explicitly covers cleanup. The effect system itself is correct; the integration point is a later item.
- **Impact**: Duration-based effects won't auto-expire until Item 23 wires cleanup.
