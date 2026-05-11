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

## Cost reduction: controller must be set before hook
- **Context**: Cards in hand may not have `controller` set. The cost_reduction hook needs to know the casting player.
- **Decision**: `get_cost_reduction()` temporarily sets `card.controller = controller` before calling the hook, then restores. `cast_spell()` also sets `card.controller = player` early in the pipeline.
- **Reasoning**: Belt-and-suspenders — safe for both standalone calls and pipeline usage.
- **Impact**: `engine/casting.py`.

## Protection from qualities: DEBT integration points
- **Context**: Protection keyword requires integration at four points (Damage, Enchanting/Equipping, Blocking, Targeting).
- **Decision**: Protection checks integrated in: `combat.py:_deal_damage()` and `game.py:deal_damage()` for damage; `casting.py:cast_spell()` for targeting (post-target-selection validation); `combat.py` for blocking legality; `state_based_actions.py` for aura/equipment detachment.
- **Reasoning**: Each DEBT aspect needs enforcement at its actual game mechanic integration point, not just in isolated helpers.
- **Impact**: `engine/protection.py` (new), `engine/combat.py`, `engine/casting.py`, `engine/game.py`, `engine/state_based_actions.py`.

## Equipment detachment vs aura detachment on protection
- **Context**: When a creature gains protection from a color, both auras and equipment with that color must detach.
- **Decision**: Auras go to graveyard (existing behavior). Equipment sets `attached_to = None` but stays on battlefield per MTG rules.
- **Impact**: `engine/state_based_actions.py`.

## Extra turns: insertion semantics with independent normal rotation
- **Context**: Extra turns must be truly inserted, not replacements for the next normal turn.
- **Decision**: Added `_normal_next_index` to track normal rotation independently. Extra turns pop from FIFO queue without advancing normal rotation. When extras are consumed, normal rotation resumes from `_normal_next_index`.
- **Reasoning**: Matches MTG rules — "take an extra turn after this one" inserts a turn; normal turn order is unaffected.
- **Impact**: `engine/game_state.py`, `engine/turn.py`.

## SPG cards: set_code="spg", all in special_guests.py
- **Context**: Special Guest cards needed a home and metadata convention.
- **Decision**: All SPG cards live in `cards/foundations/special_guests.py` with `set_code="spg"` in CardMetadata. Registered via `register_special_guests()`.
- **Impact**: `cards/foundations/special_guests.py`, `cards/registry.py`.

## ETB effects: use on_resolve() not triggers for same-card ETB
- **Context**: `register_triggers()` is called AFTER `ENTERS_BATTLEFIELD` fires, so same-card ETB triggers never match during normal resolution.
- **Decision**: For cards that need to do something when they ETB (like Embercleave auto-attach), perform the action directly in `on_resolve()` rather than relying on a self-ETB trigger.
- **Reasoning**: Per existing KEY_DECISIONS "ETB event ordering: fire event before registering triggers".
- **Impact**: Cards with self-ETB effects should use `on_resolve()` pattern.

## Continuous effects: P/T bonuses in Layer 7c, keywords in Layer 6
- **Context**: Embercleave's +1/+1 was being applied in Layer 6 (ABILITY) which gets overwritten by Layer 7a CDAs.
- **Decision**: Equipment/aura P/T bonuses go in Layer 7 with SubLayer.MODIFY_PT (7c). Keywords go in Layer 6.
- **Impact**: Equipment cards with P/T bonuses.

## protections cleared during _reset_characteristics()
- **Context**: Granted protections persisted after the source left because `_reset_characteristics()` didn't clear them.
- **Decision**: Added `protections` clearing to `Creature._reset_characteristics()` so protections are properly recalculated each cycle.
- **Impact**: `engine/card.py`, any card granting protection via continuous effects.

## Card ID mapping: synthetic SPG grpIds marked with "synthetic": true
- **Context**: SPG cards don't have real Arena grpIds yet. Synthetic IDs (94700-94709) were needed for testing.
- **Decision**: Synthetic entries marked with `"synthetic": true` flag in the primary mapping. Separate `card_name_to_grpIds` (plural) preserves all printings per card name.
- **Reasoning**: Consumers can filter synthetics; tests can still resolve SPG cards.
- **Impact**: `data/replays/card_id_map.json`, `scripts/build_card_id_map.py`.

## GRE diff gameObjects: merge, don't replace
- **Context**: GRE diffs can be sparse — only sending changed fields for a gameObject.
- **Decision**: When processing diff gameObjects, merge onto existing object using field-by-field `setattr`. New objects created from full dict. `_merge_game_object()` helper handles the mapping.
- **Reasoning**: Wholesale replacement via `from_dict()` zeros out omitted fields, corrupting state.
- **Impact**: `silverquillm/replay/state.py`.

## Exact Scryfall subset cache validation
- **Context**: SOS Draft Set composition pulls fixed collector-number subsets from related sets, such as SOA Mystical Archives and SPG Special Guests, without needing or representing the full source set.
- **Decision**: Cache collector-number subset queries in query-specific files (for example `soa_cn1-65.json` or `spg_cn149-158.json`) rather than generic whole-set cache names like `soa.json`. Freshness checks for fixed Draft Set subsets use exact sorted collector-number equality: one row for every expected collector number, no gaps, duplicates, or extra rows.
- **Reasoning**: Generic cache names can read unrelated full-set data or overwrite caches other callers expect to contain the full set. Presence/count-only checks can return stale or corrupted pools that violate the fixed 346-card SOS Draft Set invariant.
- **Impact**: `benchmarks/sos/fetch_data.py`; future Scryfall subset fetches should use query-specific cache names and exact subset validation.

## SOS specs use set-prefixed directories for multi-set collisions
- **Context**: The SOS Draft Set now combines SOS, SOA, and SPG cards whose collector numbers overlap.
- **Decision**: Per-card SOS benchmark specs use plain numeric directories for base SOS cards and set-prefixed directories such as `soa_1` and `spg_149` for non-SOS cards.
- **Reasoning**: Collector-number-only directories collide across sets and can overwrite specs.
- **Impact**: `benchmarks/sos/cards/`, `silverquillm/card_spec.py`; generated non-SOS spec directories may need force-adding because benchmark artifact paths are ignored by default.

## Audited test card_impl injection is per collector directory
- **Context**: Per-card audited tests import from a synthetic `card_impl` module during development, but the evaluator can provide an explicit `card_impl.py`.
- **Decision**: Audited conftests detect the current `tests/audited/<set>/<collector>/` directory and expose only that card's implementation class through `card_impl`. Wrong-card imports raise clear errors. SOS subset directories use set-prefixed collector keys such as `soa_1` and `spg_149`.
- **Reasoning**: Global registry fallbacks can make wrong-card tests pass and hide broken collector mappings.
- **Impact**: `tests/audited/fdn/conftest.py`, `tests/audited/sos/conftest.py`; future audited tests should live under the correct collector directory and import only the class for that card.

## SOS audited stubs approximate unsupported mana symbols
- **Context**: The SOS audited stub generator must preserve basic mana attributes even when the engine cannot represent every Magic mana symbol exactly.
- **Decision**: Supported simple hybrid symbols use the engine's hybrid mana representation. Unsupported hybrid-like symbols are approximated without dropping the whole cost: two-brid symbols such as `{2/R}` become generic `{2}`, and Phyrexian symbols such as `{B/P}` become the colored pip.
- **Reasoning**: Audited stubs should not make nonzero-cost cards free; preserving mana value is more useful for tests than omitting unsupported symbols.
- **Impact**: `scripts/generate_audited_stubs.py`, generated `cards/stubs/sos_stubs.py`.

## SOS audited behavior tests may fail against stubs
- **Context**: SOS audited tests run against generated stubs during repository development, but stubs intentionally include only basic card attributes and no oracle behavior.
- **Decision**: Keep meaningful behavior tests for SOS cards even when they fail against stubs. Treat import, syntax, collection, and basic-attribute failures as test/setup bugs; treat missing oracle behavior failures as expected stub failures.
- **Reasoning**: Audited tests define the contract for benchmarked agent implementations. Watering down behavior tests to pass stubs would remove the signals the evaluation suite is meant to provide.
- **Impact**: `tests/audited/sos/`; future SOS audited batches should document expected stub failures rather than weakening behavior assertions.

## SOS moderate TODO tier maps to classifier `medium`
- **Context**: Phase 6 TODO prose uses "moderate" complexity, while `benchmarks/sos/data/sos_classified.json` stores the corresponding classifier value as `medium`.
- **Decision**: Treat TODO "moderate" as `complexity_tier == "medium"` when selecting SOS audited Batch 2 cards.
- **Reasoning**: The repository data uses `medium`; using the prose label literally would miss every intended card.
- **Impact**: `tests/audited/sos/` Batch 2 coverage and future SOS tier-based tooling.

## SOS extreme TODO tier maps to classifier `expert`
- **Context**: Phase 6 TODO prose uses "extreme" complexity, while `benchmarks/sos/data/sos_classified.json` stores the highest classifier value as `expert`.
- **Decision**: Treat TODO "complex and extreme" as `complexity_tier in {"complex", "expert"}` when selecting SOS audited Batch 3 cards.
- **Reasoning**: The repository data has no `extreme` tier; using `expert` covers all remaining high-complexity cards and completes 346/346 coverage.
- **Impact**: `tests/audited/sos/` Batch 3 coverage and future SOS tier-based tooling.

## Damage wording: "deals damage" is one-way, "fight" is mutual
- **Context**: Felling Blow adds a +1/+1 counter, then says that creature deals damage equal to its power to an opponent's creature.
- **Decision**: Implement one-way damage for "deals damage" wording; only cards that use "fight" should deal reciprocal damage.
- **Reasoning**: MTG's fight keyword implies mutual damage, while one-way damage effects do not.
- **Impact**: `cards/foundations/simple_spells_batch3.py`, audited tests for fight-like spell wording.

## FDN audited collector collisions use suffix directories
- **Context**: Some FDN registry entries share collector numbers while per-card audited tests require one directory per implementation.
- **Decision**: Use suffixed collector directories such as `105b`, `61b`, `219b`, `228b`, `7b`, `129b`, `75b`, `76b`, and `81b` with explicit conftest overrides for colliding cards.
- **Reasoning**: This preserves per-card isolation without overwriting the canonical numeric directory for the other card.
- **Impact**: `tests/audited/fdn/conftest.py`, audited test directories for colliding FDN cards.

## FDN audited synthetic directories reserve 800-829
- **Context**: Some FDN card implementations lack collector numbers in registry metadata, but per-card audited tests still require stable collector-directory keys.
- **Decision**: Reserve synthetic FDN audited directories `800`-`829` for cards with empty collector numbers in registry metadata, using explicit conftest overrides.
- **Reasoning**: Stable synthetic keys preserve per-card isolation until registry metadata can provide real collector numbers.
- **Impact**: `tests/audited/fdn/conftest.py`, `tests/audited/fdn/800`-`tests/audited/fdn/829`.

## FDN audited coverage is scoped to registered CardRegistry entries
- **Context**: The Phase 6 TODO text describes 301 FDN Draft Set cards, but the current codebase CardRegistry exposes 264 unique FDN/SPG implementations after all FDN audited batches.
- **Decision**: Treat audited FDN coverage completeness as one test directory per registered FDN/SPG card implementation in the current registry, documenting the 264/264 state until the missing implementations are added.
- **Reasoning**: Audited tests cannot target implementations that are not registered; forcing 301 directories would create unmapped or duplicate test fixtures.
- **Impact**: `tests/audited/fdn/`, `tests/audited/fdn/conftest.py`, future FDN registry expansion must add corresponding audited tests.

## Replay executor: Seat 1 engine API with fallback
- **Context**: Seat 1 should use engine API for full validation, but some actions (spell casts) can't go through the full engine pipeline in replay mode.
- **Decision**: Seat 1 uses engine API where feasible (land plays via `play_land()`, deaths via `move_to_zone()`). Falls back to direct zone mutation on engine rejection. Spell casts use direct mutation with correct destination routing (permanents→battlefield, instants/sorceries→graveyard). Stack simulation marked ENGINE LIMITATION.
- **Impact**: `silverquillm/replay/executor.py`.

## Replay executor: always compare state even on skip
- **Context**: Phase transitions and parser-missed changes can alter observable state.
- **Decision**: `execute_step()` always calls `compare_state()` before returning, even for no-action steps.
- **Impact**: `silverquillm/replay/executor.py`.

## Divergence detection: wrapper pattern over executor
- **Context**: Need structured divergence recording without modifying the tested ReplayExecutor.
- **Decision**: ValidatingExecutor wraps ReplayExecutor, intercepting execute_step() to classify results into Divergence records. Four types: MISSING_CARD, ILLEGAL_ACTION, STATE_MISMATCH, ENGINE_ERROR.
- **Impact**: `silverquillm/replay/validation.py`.

## Per-card divergence rates are float ratios, not counts
- **Context**: TODO spec says "per-card divergence rates." Implementer initially returned raw counts.
- **Decision**: Track card appearances (how many comparisons each grpId participates in) and return divergences/appearances as a float ratio. Fallback rate 1.0 if appearances not tracked.
- **Impact**: `silverquillm/replay/validation.py`, `tests/test_divergence_detection.py`.

## ILLEGAL_ACTION classification uses StepResult.skipped
- **Context**: Initial implementation used keyword matching on mismatch descriptions, which is fragile.
- **Decision**: Primary classification uses StepResult.skipped + skip_reason. Keyword matching kept as fallback.
- **Impact**: `silverquillm/replay/validation.py`.

## CLI validate: divergence_rate is per-game, not per-divergence
- **Context**: divergence_rate could mean total divergences / games or games_with_divergence / games.
- **Decision**: Rate is fraction of games that had any divergence (games_with_divergence / games_attempted). This is more meaningful for benchmarking.
- **Impact**: `silverquillm/replay/cli.py`.

## CLI validate: step_callback and stop_on_first patterns
- **Context**: --verbose and --stop-on-divergence need per-step interaction during replay execution.
- **Decision**: Added `step_callback` and `stop_on_first` parameters to `validate_replay()` and `ValidatingExecutor.execute_all()`. Callback receives step index, game state ID, action, and result. stop_on_first breaks the loop after first divergence.
- **Impact**: `silverquillm/replay/validation.py`, `silverquillm/replay/cli.py`.

## CLI validate: parse failures count as attempted games
- **Context**: Replays that fail to parse were silently skipped, undercounting games_attempted.
- **Decision**: Parse failures generate a ValidationReport with a single ENGINE_ERROR divergence, counted in games_attempted and visible in summary.
- **Impact**: `silverquillm/replay/cli.py`.
