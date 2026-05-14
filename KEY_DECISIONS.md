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

## Mode-based CardStrategy convention
- **Context**: Phase 7 refactors the benchmark harness away from harness-managed blind/test-informed rounds.
- **Decision**: Benchmark mode is a top-level `BenchmarkConfig.mode` field with valid values `blind` and `impl_test`, defaulting to `impl_test` for backward compatibility. Per-card execution is selected through `silverquillm.strategies.get_strategy(mode)`, returning a `CardStrategy` implementation. `AgentConfig.max_test_rounds` was removed because agents self-manage iteration inside a single mode prompt.
- **Reasoning**: Mode is a benchmark-run property, not an agent setting. Keeping strategy selection separate from adapter configuration preserves the nested `AgentConfig` convention while making the outer harness mode-agnostic.
- **Impact**: `silverquillm/config.py`, `silverquillm/strategies.py`, agent-session consumers, config tests, and strategy tests.

## AgentSession thin-wrapper convention
- **Context**: Phase 7 removes harness-managed implementation/test feedback rounds.
- **Decision**: `AgentSession.run_card()` is the canonical per-card execution path: setup workspace, delegate to `CardStrategy.run_card()`, run violation/postmortem bookkeeping, and harvest canonical `card_impl.py` plus optional `tests.py`. Harness-managed pytest loops, `_run_pytest()`, and per-round feedback prompts are removed.
- **Reasoning**: The benchmark harness treats agents as black boxes; mode-specific prompting and output expectations belong in strategies, while the session wrapper owns workspace, contamination checks, postmortem logging, and artifact harvest.
- **Impact**: `silverquillm/agent_session.py`, `silverquillm/cli.py`, agent-session tests, CLI orchestration tests, postmortem tests, violation wiring tests.

## Violation annotation does not block artifact harvest
- **Context**: Issue #15 showed a card with a contamination violation could lose its implementation artifacts.
- **Decision**: `harvest_results()` runs regardless of violation status and captures canonical `card_impl.py` plus optional `tests.py`. Violations are propagated through `CardRunResult.violations` and written as a top-level `violations` list in per-card `result.json`.
- **Reasoning**: Contamination should affect scoring/status annotations, not destroy diagnostic or evaluatable artifacts.
- **Impact**: `silverquillm/agent_session.py`, `silverquillm/cli.py`, `silverquillm/results.py`, harvest/violation/result tests.

## Engine snapshot rollback on timeout
- **Context**: Timed-out agents can leave partial engine modifications in the run-level engine, poisoning subsequent cards.
- **Decision**: `AgentSession.run_card()` snapshots the run engine before strategy execution. Timeout results or timeout exceptions restore the snapshot; successful runs delete the snapshot and preserve engine changes for the normal commit path.
- **Reasoning**: Timeouts are failure states for a card, so partial engine changes should not persist beyond that card. Successful cards still retain the persistent-engine behavior.
- **Impact**: `silverquillm/agent_session.py`, engine snapshot tests, timeout-result regression tests.

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

## Per-card audited eval persists to card result.json
- **Context**: `benchmark eval --audited-dir` runs audited tests per card, and downstream scoring reads audited data from each card's `result.json`.
- **Decision**: Per-card audited CLI runs write results both to the flat run-level `results.json` and to each card's nested `result.json` under `audited_eval.blind`, `audited_eval.tested`, and top-level `audited_eval.errors`.
- **Reasoning**: Keeping the existing per-card result shape avoids scorer/results changes and ensures missing implementation/test errors are visible to downstream consumers.
- **Impact**: `silverquillm/cli.py`, `silverquillm/evaluator.py`, `tests/test_audited_per_card.py`.

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

## Process-group termination for adapter timeouts
- **Context**: Item 7 enforces `timeout_per_card` at the subprocess level. Adapters must terminate not just the direct Popen process, but all child processes spawned by the agent CLI tool.
- **Decision**: All subprocess-based adapters use `start_new_session=True` in Popen and `os.killpg()` in their `kill()` method to terminate the entire process group. SIGTERM→SIGKILL escalation with 5s grace period. `run_with_retries()` calls `self.kill()` before raising TimeoutError.
- **Reasoning**: Agent CLI tools (opencode, claude, aider, pi) may fork worker processes. Only process-group termination ensures all descendants are terminated.
- **Impact**: All adapters in `silverquillm/adapters/`, `silverquillm/strategies.py`, `silverquillm/adapters/base.py`.

## TESTING-CONVENTIONS.md established
- **Context**: PR #11 demonstrated a critical failure where `os.killpg()` with auto-MagicMock PID sent SIGTERM to PID group 1, terminating the container.
- **Decision**: Created `docs/specs/TESTING-CONVENTIONS.md` with hard rules: explicit mock PIDs, patched os.killpg/os.getpgid, Event.wait instead of while-True, pytest-timeout safety net.
- **Reasoning**: Prevent tests from terminating real processes or hanging forever.
- **Impact**: All tests involving subprocess/timeout/signal must comply.

## Per-card filesystem paths use card_id (collector number)
- **Context**: Harness used both `card_name` (display name) and `card_dir_name` (collector number) for per-card subdirectories, creating duplicate directories.
- **Decision**: All filesystem path construction uses `card_id` (collector number). `AgentSession._path_id` is the canonical accessor, falling back to `card_name` if `card_id` is empty. `card_name` remains for log messages and JSON content.
- **Reasoning**: Collector numbers are unique, filesystem-safe, and already used by `save_card_result()`.
- **Impact**: `silverquillm/agent_session.py`, `silverquillm/cli.py`.

## Strategies use run_with_retries for timeout enforcement
- **Context**: Strategies previously used ThreadPoolExecutor for timeout; needed replacement.
- **Decision**: Strategies call `adapter.run_with_retries(prompt, workspace, timeout=timeout, retries=0)` instead of bare `adapter.run()`. Timeout enforcement is the adapter layer's responsibility via `run_with_retries`.
- **Reasoning**: `run_with_retries` already implements timeout via SIGALRM (main thread) or threading fallback, plus calls `adapter.kill()`. Using it directly avoids duplicating timeout logic in each strategy.
- **Impact**: `silverquillm/strategies.py`, all strategy tests use mock adapters with `run_with_retries`.

## Lazy target filters with game-state evaluation
- **Context**: Target filter closures in `get_targets()` captured game state at definition time, not evaluation time.
- **Decision**: Target filter predicates now accept `game` as a parameter and evaluate state lazily. Card implementations use property-based predicates that check current controller, zone, and card type at evaluation time. `engine/casting.py` wires `filter_fn` into target validation.
- **Reasoning**: MTG rules require target legality to be checked at resolution time using current game state, not the state when the spell was cast.
- **Impact**: `engine/casting.py`, 6 card implementation files in `cards/foundations/`.

## StackObject.targets is single source of truth for chosen targets
- **Context**: `card.chosen_targets` was set at cast time, creating mutable state on the card instance that could leak to copies.
- **Decision**: `chosen_targets` assignment moved from cast-time to resolve-time. Between cast and resolve, `StackObject.targets` is the single source of truth. At resolution, `card.chosen_targets = obj.targets` is set for backward compat with `on_resolve()` callbacks.
- **Reasoning**: Prevents target leakage on card copy/clone. Aligns with MTG rules where targets are stored on the stack object.
- **Impact**: `engine/casting.py` (cast_spell and _resolve_spell).

## Utility functions moved to card_spec.py
- **Context**: Deleting template_gen.py orphaned `card_name_to_class_name` and `_determine_base_class` which are still used by scripts and test helpers.
- **Decision**: Moved both functions to `silverquillm/card_spec.py` since they are card-related utilities and card_spec.py is the kept module.
- **Reasoning**: card_spec.py is the natural home for card-related utilities. Avoids creating a new module just for two functions.
- **Impact**: `silverquillm/card_spec.py`, `scripts/generate_audited_stubs.py`, `tests/test_integration_helpers.py`, `tests/benchmark/test_helpers.py`.

## FDN card restructure: compatibility shims
- **Context**: 26 card test files import from `cards.foundations.*`. Updating all imports is high-risk and high-churn.
- **Decision**: Created package-based compatibility shims at `cards/foundations/{module}/__init__.py` that re-export card classes via importlib from `cards/fdn/{collector}/card_impl.py`. Actual code lives in per-card dirs.
- **Reasoning**: Shims allow gradual migration. Tests continue to work. New code should import from `cards.fdn.{num}.card_impl`.
- **Impact**: `cards/foundations/` still exists as a package but contains only re-export shims. Actual implementations are in `cards/fdn/`.

## FDN per-card layout conventions
- **Context**: Need consistent directory naming for per-card layout.
- **Decision**: `cards/fdn/{collector_number}/` with `card_impl.py` + `card_spec.json`. SPG cards use `spg_` prefix (e.g., `spg_74`). Collision suffixes: `7b`, `61b`, `105b`, etc. Synthetic IDs 800+ for cards without real collector numbers.
- **Reasoning**: Matches SOS structure. Directory name = collector number for easy lookup.
- **Impact**: 265+ directories under `cards/fdn/`.

## Aura on_resolve() must revalidate target types
- **Context**: Reviewer flagged that aura on_resolve() only checked battlefield presence, not target type validity.
- **Decision**: All aura implementations revalidate that the target still has the required type(s) at resolution time. If the type changed, the aura fizzles.
- **Reasoning**: MTG rules require target legality recheck at resolution. A creature that becomes a noncreature is no longer a valid target for "enchant creature."
- **Impact**: All aura card_impl.py files follow this pattern going forward.

## Continuous effect color changes belong in Layer 5
- **Context**: Imprisoned in the Moon was applying color removal (`perm.colors = set()`) inside the Layer 4 type-changing effect.
- **Decision**: Color changes must be in a separate `Layer.COLOR` (Layer 5) continuous effect, not bundled with type changes.
- **Reasoning**: MTG comprehensive rules layer system (CR 613) requires color changes in Layer 5, separate from type changes in Layer 4.
- **Impact**: Any future card that changes both types and colors needs separate effects.

## ENGINE LIMITATION: EffectManager._reset_objects() does not restore name/subtypes/colors
- **Context**: Witness Protection mutates name, subtypes, and colors directly. When the aura is removed, these mutations persist.
- **Decision**: Mark with ENGINE LIMITATION comment. Accept the limitation for now.
- **Reasoning**: The engine's reset-and-reapply mechanism doesn't cover name/subtypes/colors fields. A proper fix requires engine-level changes beyond card implementation scope.
- **Impact**: Cards that override name/subtypes/colors via continuous effects will have this limitation until the engine is updated.

## Planeswalker choose_card() for optional/multi-choice abilities
- **Context**: Reviewer flagged that Vivien's +1 and Chandra's +2 auto-selected cards instead of letting the controller choose.
- **Decision**: Use `controller.choose_card()` for any ability that lets a player pick from multiple options. Wrap in try/except for `ScriptExhaustedError` when `DeterministicPlayer` has no queued choice.
- **Reasoning**: MTG rules give the controller the choice. Auto-selection is incorrect behavior.
- **Impact**: All future card implementations with "you may" or "choose" effects must use `choose_card()`.

## EventType.END_STEP added to engine/triggers.py
- **Context**: Chandra's delayed sacrifice trigger fires at "the beginning of the next end step." The engine lacked an `END_STEP` event type.
- **Decision**: Added `END_STEP = "end_step"` to `EventType` enum.
- **Reasoning**: Multiple cards trigger at the beginning of the end step (delayed triggers, end-of-turn effects). This event type was missing.
- **Impact**: `engine/triggers.py`. Future cards with end-step triggers should use `EventType.END_STEP`.
