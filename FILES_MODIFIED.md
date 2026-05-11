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

## Item 5: SPG Batch 1 — Simple spells and utility creatures

### Tests
- `tests/cards/test_special_guests.py` — Tests for all 5 Special Guest cards and registration

### Implementation
- `cards/foundations/special_guests.py` — Implemented 5 Special Guest cards; revised: added can_cast guard and attacking validation for Condemn, choose_card API for Grim Tutor, has_kicker flag for Bushwhacker, functional continuous effect apply for Bushwhacker buff, removed hexproof from Paradise Druid base keywords

## Item 6: SPG Batch 2 — Complex permanents and spells

### Implementation
- `cards/foundations/special_guests.py` — Added 5 complex SPG cards (Sphinx's Tutelage, Embercleave, Akroma's Memorial, Temporal Manipulation, Fiend Artisan) with full registration; revised: Embercleave ETB attach via on_resolve() instead of trigger-only, P/T bonus moved to Layer 7c, extracted _do_etb_attach helper
- `engine/card.py` — Clear protections list in Creature._reset_characteristics() so granted protections don't persist after source leaves

## Item 7: Card ID mapping (grpId → card name)

### Tests
(no pre-written tests for this item)

### Implementation
- `data/replays/card_id_map.json` — grpId-to-card-name mapping with 592 entries (582 from Scryfall + 10 synthetic SPG #74-83); revised: added card_name_to_grpIds (plural, list-valued) for duplicate-name disambiguation, synthetic flag on SPG 94700-94709 entries
- `scripts/build_card_id_map.py` — Script to fetch card data from Scryfall API and build the mapping JSON; revised: reverse map preserves all grpIds via card_name_to_grpIds, synthetic entries flagged with "synthetic": true, error handling on curl/Scryfall API failures


## Item 8: 17lands GRE JSON parser

### Tests
tests/test_replay_parser.py — 39 tests for replay parsing: game setup, opening hands, state reconstruction, land plays, life totals, draws, ObjectIdChanged tracking, API methods

### Implementation
silverquillm/replay/__init__.py — Package init with public API exports
silverquillm/replay/types.py — Dataclasses for ReplayGame, GameSnapshot, ReplayAction, GameObject, Zone, Annotation, etc.
silverquillm/replay/state.py — GRE state reconstruction (full/diff merging with sparse gameObject merge), action inference, ObjectTracker for zone transition tracking
silverquillm/replay/parser.py — High-level parse_replay() function, card ID map loading
data/replays/sample_replay.json — Synthetic 5-turn replay data with real grpIds for testing

## Item 9: Replay executor (state-diff observer mode)

### Tests
tests/test_replay_executor.py — 23 tests for ReplayExecutor initialization, step execution, state comparison, seat 1/2 behavior, imports

### Implementation
silverquillm/replay/executor.py — ReplayExecutor class with state-diff observer mode, seat 1 full validation, seat 2 oracle injection, state comparison (life totals, zone contents, battlefield state)
silverquillm/replay/__init__.py — Added ReplayExecutor, StateMismatch, StepResult exports

## Item 10: Divergence detection and reporting

### Tests
tests/test_divergence_detection.py — 43 tests for DivergenceType, Divergence, ValidationReport, ValidatingExecutor, validate_replay

### Implementation
silverquillm/replay/validation.py — DivergenceType enum, Divergence dataclass, ValidationReport, ValidatingExecutor (MISSING_CARD not counted as successful, ILLEGAL_ACTION from skipped/skip_reason + keyword fallback, expected/actual state populated for ENGINE_ERROR/MISSING_CARD)
silverquillm/replay/__init__.py — Added Divergence, DivergenceType, ValidatingExecutor, ValidationReport, validate_replay exports

## Item 11: CLI `benchmark validate` command

### Tests
(no pre-written tests for this item)

### Implementation
silverquillm/replay/cli.py — CLI `validate` command with file/dir support, --cards, --verbose (per-step callback), --report, --stop-on-divergence; fixed divergence_rate to games_with_divergence/games_attempted; parse failures counted as attempted games
silverquillm/replay/validation.py — Added stop_on_first and step_callback params to execute_all() and validate_replay() for within-replay early exit and verbose output
silverquillm/cli.py — Imported and registered the `validate` subcommand from `silverquillm.replay.cli`
