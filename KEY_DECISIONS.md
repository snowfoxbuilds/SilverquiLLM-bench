# Key Decisions

Persistent across runs. Records architectural decisions, conventions, and long-lived constraints.


## Package renamed from benchmark/ to silverquillm/
- **Context**: TODO item 1 required renaming the package directory.
- **Decision**: Package is now `silverquillm`. All imports use `from silverquillm.xxx import ...`. CLI entry point command name stays `benchmark`.
- **Reasoning**: The CLI command name is user-facing and doesn't need to match the internal package name. `tests/benchmark/` subdirectory was left as-is since it's a test helper directory, not the package being renamed.
- **Impact**: All source and test files updated. `_PROTECTED_DIRS` in `agent_session.py` now references `silverquillm`.

## Nested AgentConfig convention
- **Context**: Config was flat; needed nested `agent:` block per spec.
- **Decision**: Agent-related config lives under `agent:` in YAML and `config.agent.*` in code. Legacy flat access (`config.max_test_rounds`, `config.agent_tool`) works via deprecated properties. Field `agent_tool` renamed to `agent.adapter`.
- **Reasoning**: Backward-compatible properties allow gradual migration of consumers in the next TODO item.
- **Impact**: `silverquillm/config.py`, `config.example.yaml`, `silverquillm/results.py`.

## Deprecated flat config properties removed
- **Context**: After migrating all consumers, backward-compat properties were no longer needed.
- **Decision**: Removed deprecated properties from BenchmarkConfig. All code uses `config.agent.*`. YAML backward compat for flat keys is preserved in `load_config()`.
- **Reasoning**: Clean API surface; no more dual access patterns.
- **Impact**: All test fixtures use `agent=AgentConfig(...)`. New code must use `config.agent.*`.

## AgentAdapter pattern
- **Context**: Need pluggable agent adapters for different CLI tools.
- **Decision**: ABC with `run(prompt, workspace) -> str`, `setup()`, `teardown()`. Registry-based factory via `get_adapter(config)`. Concrete adapters call `register_adapter("name", cls)` at module level. `run_with_retries` uses a single overall deadline from `timeout_per_card`.
- **Reasoning**: Registry pattern allows adapter modules to self-register on import. Overall deadline prevents retry multiplication of timeouts.
- **Impact**: `silverquillm/adapters/base.py`, `silverquillm/adapters/__init__.py`.

## 6. Canonical tier key is `complexity_tier`
- **Context**: Codebase used both `tier` and `complexity_tier` inconsistently across classifier, scorer, evaluator, card specs, and JSON data files.
- **Decision**: Standardized on `complexity_tier` as the canonical key. All readers accept both keys with `complexity_tier` preferred. All writers emit `complexity_tier` (JSON data files emit both for backward compat).
- **Reasoning**: `complexity_tier` is more descriptive and self-documenting. Adding backward-compat fallback ensures older JSON files still work.
- **Impact**: `card_classifier.py`, `card_spec.py`, `cli.py`, `prototype.py`, `results.py`, `run_utils.py`, `sos_classified.json`, `prototype_cards.json`.

## 7. Persistent engine per run
- **Context**: Previously, each card workspace got a fresh read-only copy of `engine/` from the repo. Agents couldn't modify engine files, and no changes persisted between cards.
- **Decision**: Run-level engine directory created at run start via `init_run_engine()`. Each card gets a writable copy. After each card, `commit_engine_changes()` merges modifications back. `save_engine_final()` saves the final state as a run artifact. `engine/` removed from `_PROTECTED_DIRS`. `base_classes.py` extracted from run engine dir when available.
- **Impact**: `agent_session.py`, `cli.py`. Enables agents to extend the engine across cards within a single run.

## 8. Regression test runner design
- **Context**: After each card's test-informed phase, need to verify earlier cards still work with the current engine state.
- **Decision**: `run_regressions()` builds fresh temp workspaces per card combining current `run_engine_dir` + card's saved impl/test artifacts. Parses pytest `-v` output for individual `FAILED` test names. Results stored in card's `result.json` with `failed_tests` list. Regression failures fed back to agent if rounds remain.
- **Reasoning**: Using fresh workspaces avoids stale engine state. Storing individual test names enables precise feedback. Backward-compatible API (optional `run_engine_dir` param).
- **Impact**: `silverquillm/regression.py` (new module), `agent_session.py`, `cli.py`.

## SBA event firing order: events before unregister
- **Context**: `_move_to_graveyard()` in SBAs needs to fire CREATURE_DIES and LEAVES_BATTLEFIELD events. Order relative to trigger unregistration matters.
- **Decision**: Fire events BEFORE `unregister()` so self-referencing death triggers ("when this creature dies") can match. Gate `CREATURE_DIES` on `dest_zone == Zone.GRAVEYARD` so replacement-effect redirections (to exile/hand) don't incorrectly fire death events.
- **Reasoning**: MTG rules 603.10 — death triggers use last-known-information and must fire. A creature only "dies" if it reaches the graveyard (not if redirected by replacement effects).
- **Impact**: `engine/state_based_actions.py` (`_move_to_graveyard`).

## ETB event ordering: fire event before registering triggers
- **Context**: When a permanent enters the battlefield via `move_to_zone()`, should `ENTERS_BATTLEFIELD` event fire before or after registering the permanent's own triggers?
- **Decision**: Fire `ENTERS_BATTLEFIELD` BEFORE calling `register_triggers()`. This prevents a permanent's own ETB trigger from retroactively matching its own entry event.
- **Reasoning**: The permanent's triggers become active after it has fully entered the battlefield, not during the entry process. Other already-registered triggers watching for ETB still fire correctly. This also matches existing test expectations.
- **Impact**: `engine/zones.py` (`move_to_zone`).

## move_to_zone() is the single entry point for all zone transitions
- **Context**: Zone transitions were duplicated across casting.py, game.py, and state_based_actions.py.
- **Decision**: All zone transitions go through `move_to_zone(game, card, from_zone, to_zone)` in `engine/zones.py`. This includes spell resolution (stack→battlefield/graveyard), destruction, sacrifice, exile, SBA deaths, and bouncing.
- **Reasoning**: Centralizes event firing, trigger registration/unregistration, and replacement effect consultation. New zone-transition paths (flicker, mill, reanimate) just call `move_to_zone()`.
- **Impact**: `engine/zones.py`, `engine/casting.py`, `engine/game.py`, `engine/state_based_actions.py`.

## cards_drawn_this_turn tracking in engine
- **Context**: Fractal Anomaly needs to know how many cards the controller drew this turn.
- **Decision**: Added `cards_drawn_this_turn` counter increment in `engine/game.py`'s `draw_card()` function using `hasattr` guard.
- **Reasoning**: Simple, engine-level tracking that any card can query via `getattr(controller, "cards_drawn_this_turn", 0)`.
- **Impact**: `engine/game.py` (`draw_card`).

## ENGINE LIMITATION comment convention
- **Context**: Several aura cards require engine features that don't exist yet (untap prevention, controller change, name/subtype reset, dynamic mana abilities).
- **Decision**: Mark such code with `# ENGINE LIMITATION:` comments explaining what's missing and what would be needed.
- **Reasoning**: These comments serve as a TODO list for future engine work and prevent future contributors from thinking the stubs are complete implementations.
- **Impact**: Established in `cards/foundations/auras_batch2.py`, applicable project-wide.

## ZoneContainer.shuffle() for library shuffling
- **Context**: Burnished Hart needed to shuffle library after searching. `random.shuffle(list(library))` shuffles a copy, not the zone.
- **Decision**: Use `library.shuffle()` — ZoneContainer has a built-in shuffle method.
- **Reasoning**: Discovered during Item 12 review fix.
- **Impact**: Any card that shuffles a library should use this API.

## Hybrid mana payment: reserve explicit choices before solving
- **Context**: `pay()` with hybrid + generic costs could conflict when explicit generic `choices` were provided. Hybrid solver might consume mana the caller reserved for generic.
- **Decision**: When explicit `choices` are provided, deduct generic mana from the working pool BEFORE running `_solve_hybrid()`. The solver only sees genuinely available mana.
- **Reasoning**: Prevents the solver from stealing reserved mana. Auto-pay (choices=None) still works as before.
- **Impact**: `engine/mana.py` (`pay()` method).
