# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Project scaffold

### Tests
- `tests/test_scaffold.py` — Verifies pyproject.toml metadata, directory structure, importability, py.typed markers, ruff config

### Implementation
- `pyproject.toml` — Project metadata, build config, deps, pytest/mypy tool config, package-data for py.typed
- `ruff.toml` — Ruff linter configuration (line-length 100, py311 target)
- `engine/py.typed` — PEP 561 typed package marker for engine package
- `cards/py.typed` — PEP 561 typed package marker for cards package
- `.gitignore` — Added standard Python ignores (__pycache__, egg-info, ruff_cache, etc.)
- `engine/__init__.py` — Engine package init
- `cards/__init__.py` — Cards package init
- `cards/foundations/__init__.py` — Cards foundations subpackage init
- `tests/__init__.py` — Tests package init
- `tests/engine/__init__.py` — Tests engine subpackage init
- `tests/cards/__init__.py` — Tests cards subpackage init

## Item 2: Core enums and type definitions

### Tests
- `tests/engine/test_types.py` — Verifies all enums, ManaCost construction/cmc/parse, TargetRequirement

### Implementation
- `engine/types.py` — All core enums (Color, ManaType, Zone, Phase, Step, CardType, Supertype, Keyword) and dataclasses (ManaCost, TargetRequirement); revised to reject unconsumed input and negative generic mana in ManaCost.parse()

## Item 3: Zone containers

### Tests
- `tests/engine/test_zones.py` — Verifies ZoneContainer add/remove/contains/get_all/top/bottom/shuffle, Zones.new_player(), move_zone round-trip, IllegalMoveError, same-zone no-op, position=shuffle

### Implementation
- `engine/zones.py` — ZoneContainer (ordered list wrapper with add/remove/shuffle/top/bottom), Zones (per-player Zone→ZoneContainer mapping), move_zone function, IllegalMoveError exception; revised: identity-based (`is`) lookups in contains/remove, atomic position validation in move_zone

## Item 4: Player ABC and DeterministicPlayer

### Tests
- `tests/engine/test_player.py` — Verifies Player ABC cannot be instantiated, default properties, DeterministicPlayer FIFO scripted choices, ScriptExhaustedError, remaining_choices tracking

### Implementation
- `engine/player.py` — Player(ABC) with name/life/zones/mana_pool/has_lost/land_plays_remaining properties and 5 abstract methods; DeterministicPlayer with deque-based script queue; ScriptExhaustedError exception

## Item 5: Mana pool and cost payment

### Tests
- `tests/engine/test_mana.py` — Verifies ManaPool construction, add/get/total, empty, can_pay, pay (with choices & auto-pay), Player integration
- `tests/engine/test_player.py` — Updated test_mana_pool_defaults_none to expect ManaPool instance instead of None

### Implementation
- `engine/mana.py` — ManaPool class with add/empty/total/get/can_pay/pay methods, auto-pay generic logic preferring colorless; rejects negative choices; TODO: hybrid/Phyrexian comments
- `engine/player.py` — Updated Player.__init__ to initialize mana_pool as ManaPool() instead of None

## Item 6: GameState scaffold and turn structure

### Tests
- `tests/engine/test_game_state.py` — Verifies GameState construction, 2-player validation, initial state, player properties, zone accessors, phase/step advancement, mana pool clearing, run_turn loop

### Implementation
- `engine/game_state.py` — GameState class with player properties, zone accessors, advance_phase() turn progression, empty_mana_pools(); _TURN_SEQUENCE constant; rejects != 2 players
- `engine/turn.py` — run_turn() loop iterating all phases/steps of a turn; priority_loop() stub; _NO_PRIORITY_STEPS set

## Item 7: The Stack — data structure, priority passing, and resolution

### Tests
- `tests/engine/test_stack.py` — Verifies StackObject dataclass, Stack LIFO push/pop/peek/objects, priority_loop auto-pass and resolution, priority passing with DeterministicPlayer scripts, mana ability immediate resolution, check_state_based_actions stub
- `tests/engine/test_game_state.py` — Updated test_initial_stack_is_none to test_initial_stack_is_stack_instance (Stack is now initialized)

### Implementation
- `engine/stack.py` — StackObject dataclass, Stack LIFO container, priority_loop with auto-pass and stack resolution, _handle_priority helper, _get_legal_actions placeholder, check_state_based_actions stub; **revised**: priority_loop now retains priority for acting player and keeps game.priority_player_index in sync
- `engine/game_state.py` — Updated self.stack from None to Stack() instance; added Stack import
- `engine/turn.py` — Removed stub priority_loop; now imports real priority_loop from engine.stack

## Item 8: State-based actions

### Tests
- `tests/engine/test_state_based_actions.py` — 50 tests covering all 8 SBAs, check/resolve API, cascading, multi-SBA passes

### Implementation
- `engine/state_based_actions.py` — New module with check_state_based_actions (single-pass, returns bool) and resolve_state_based_actions (loop until stable); implements 8 SBAs: life<=0, toughness<=0, lethal damage, empty library draw, legend rule, token cleanup, aura validity, counter annihilation; revised: _move_to_graveyard uses obj.owner (duck-typed) for owner-based graveyard routing; token cleanup covers STACK and COMMAND zones
- `engine/stack.py` — Replaced check_state_based_actions stub with wrapper delegating to resolve_state_based_actions from the new module
- `engine/player.py` — Added drawn_from_empty_library: bool = False attribute to Player.__init__ and docstring

## Item 9: Card base classes and CardImpl interface

### Tests
- `tests/engine/test_card.py` — 87 tests covering GameObject IDs, CardImpl fields/hooks, all card subtypes, counters, keywords, supporting dataclasses

### Implementation
- `engine/card.py` — GameObject base class (auto-increment object_id), CardImpl interface with hook methods, concrete subclasses: Creature, Instant, Sorcery, Enchantment (is_aura=False), Aura(Enchantment, is_aura=True), Artifact, ArtifactCreature, Planeswalker, Land; all subclass constructors enforce mandatory card types via union; supporting dataclasses: ActivatedAbility, LoyaltyAbility, ManaAbility, ContinuousEffect, Mode
- `engine/state_based_actions.py` — Updated _sba_aura_unattached to check getattr(obj, 'is_aura', True) so non-aura enchantments are not killed by the unattached-aura SBA

## Item 10: Casting and resolution pipeline

### Tests
- `tests/engine/test_casting.py` — 69 tests covering timing helpers, cast_spell (all card types, timing checks, mana, hooks, stack zone), play_land (timing, limits), permanent type detection, integration

### Implementation
- `engine/casting.py` — cast_spell reordered: hand→stack zone→targets→pay mana (with rollback)→on_cast→push StackObject; card placed in Zone.STACK; resolved instants/sorceries go to card.owner's graveyard (fallback to caster); resolution removes card from stack zone

## Item 11: Triggered abilities system

### Tests
- `tests/engine/test_triggers.py` — 37 tests covering EventType enum, TriggerRegistration dataclass, TriggerManager register/unregister/fire_event, condition filtering, APNAP ordering, GameState integration, ETB trigger flow

### Implementation
- `engine/triggers.py` — New module with EventType enum (13 events), TriggerRegistration dataclass, TriggerManager class with register/unregister/fire_event (APNAP ordering), get_triggers/get_triggers_for_source/clear helpers
- `engine/game_state.py` — Added trigger_manager: TriggerManager attribute to GameState.__init__(), imported TriggerManager
- `engine/casting.py` — Wired automatic register_triggers call on permanent resolution (_resolve_spell) and land play (play_land)
- `engine/state_based_actions.py` — Wired automatic trigger_manager.unregister call when permanents leave battlefield via _move_to_graveyard

## Item 12: Activated abilities system

### Tests
- `tests/engine/test_abilities.py` — 51 tests covering ability construction, mana/non-mana activation, tap_cost, timing, loyalty abilities, integration

### Implementation
- `engine/abilities.py` — New module with ActivatedAbilityInstance/LoyaltyAbilityInstance dataclasses, activate_ability() entry point, tap_cost() helper, loyalty per-turn tracking, AbilityError exception; revised: removed sorcery-speed timing check for regular activated abilities (kept only for loyalty abilities)
- `engine/card.py` — Added is_tapped: bool = False to Land and Artifact classes for tap-cost support

## Item 13: Combat system

### Tests
- `tests/engine/test_combat.py` — 52 tests covering CombatState, attackers, blockers, combat damage, end combat, integration, edge cases

### Implementation
- `engine/combat.py` — Combat system with CombatState, declare_attackers_step, declare_blockers_step, combat_damage_step, end_combat_step; fixes: first-strike checks blockers too, deathtouch damage tracking, was_blocked set for blocked-stays-blocked rule, attacker/blocker eligibility validation
- `engine/state_based_actions.py` — Updated _sba_creature_lethal_damage to also destroy creatures dealt deathtouch damage (rule 704.5h)
- `engine/card.py` — Added dealt_deathtouch_damage: bool = False to Creature class for deathtouch SBA tracking
- `engine/game_state.py` — Added combat_state: CombatState attribute to GameState.__init__(), imported CombatState from engine.combat

## Item 14: Continuous effects and layer system

### Tests
(No pre-written test file — verified via 704 existing tests passing + manual validation)

### Implementation
- `engine/continuous_effects.py` — New module with Layer enum (7 layers), SubLayer enum (7a–7d), ContinuousEffect dataclass, EffectManager class (add/remove/remove_expired/apply_all in layer+timestamp order), duration constants; revised: apply_all() now resets battlefield objects via _reset_objects() before reapplying effects for idempotency
- `engine/card.py` — Added _original_card_types/_original_keywords to CardImpl and _original_base_power/_original_base_toughness/_original_plus_one_counters/_original_minus_one_counters to Creature; added _reset_characteristics() methods for continuous-effect reset
- `engine/game_state.py` — Added effect_manager: EffectManager attribute to GameState.__init__(), imported EffectManager from engine.continuous_effects

## Item 15: Replacement effects engine

### Tests
- `tests/engine/test_replacement_effects.py` — 40 tests covering ReplacementEffect dataclass, ReplacementManager register/unregister/apply, conditions, self-replacement prevention, instead semantics, GameState integration, SBA unregistration

### Implementation
- `engine/replacement_effects.py` — New module with ReplacementEffect dataclass (event_type, source, condition, replacement, controller) and ReplacementManager class (register/unregister/apply with self-replacement prevention and player-choice ordering)
- `engine/game_state.py` — Added replacement_manager: ReplacementManager attribute to GameState.__init__(), imported ReplacementManager from engine.replacement_effects
- `engine/casting.py` — Wired automatic register_replacement_effects call on permanent resolution (_resolve_spell) and land play (play_land)
- `engine/state_based_actions.py` — _move_to_graveyard now consults replacement_manager.apply() before deciding destination zone; added _DESTINATION_ZONE_MAP for string→Zone mapping; supports exile/hand/library redirection via replacement effects

## Item 16: Game setup, helper actions, and the full game loop

### Tests
- `tests/engine/test_game.py` — 64 tests for create_game, helper actions, run_game loop, integration (2 tests fail awaiting Tester update for draw-skip rule)

### Implementation
- `engine/game.py` — New module: create_game (life/library/shuffle/draw-7/active-player), 11 helper actions (deal_damage, destroy, sacrifice, exile, draw_card, discard, create_token, add_counter, remove_counter, tap, untap), run_game loop with SBA checking and MAX_TURNS limit; **revised**: destroy() distinguishes creature vs non-creature for event types; sacrifice() now consults replacement_manager.apply() before zone move
- `engine/turn.py` — Wired turn-based actions into run_turn: untap step (untap/clear summoning sickness/reset land plays), draw step (active player draws), combat steps (delegates to combat.py), cleanup step (clear damage/remove expired effects); **revised**: _do_draw_step skips draw on turn 1 for starting player (MTG rule §103.7a)

## Item 17: test_utils module for engine validation

### Tests
- `tests/engine/test_test_utils.py` — 37 meta-tests covering create_game, set_board_state, cast_spell, advance_to_phase, declare_attackers, declare_blockers, error handling, and integration

### Implementation
- `tests/test_utils.py` — Test helper API with create_game (convenience wrapper with DeterministicPlayer), set_board_state (direct zone/life/mana manipulation), cast_spell (find-in-hand + cast + resolve), advance_to_phase (safe fast-forward), declare_attackers (name-based combat setup), declare_blockers (name-mapping combat setup), TestSetupError exception; **revised**: create_game resets drawn_from_empty_library after empty-deck setup; cast_spell feeds targets into DeterministicPlayer script

## Item 18: Card registry and Scryfall data pipeline

### Tests
(No pre-written test file — verified via 963 existing tests passing + manual validation)

### Implementation
- `cards/registry.py` — CardMetadata dataclass (11 fields from Scryfall), CardRegistry class (register/get/create_instance/list_all), default_registry module-level singleton
- `cards/scryfall.py` — fetch_set() with Scryfall API pagination, 100ms rate limiting, file-based JSON cache in data/sets/, _parse_card() helper
- `data/sets/.gitkeep` — Placeholder to keep cache directory in git
- `.gitignore` — Added data/sets/*.json to exclude cached Scryfall data

## Item 19: Basic land implementations (Plains, Island, Swamp, Mountain, Forest)

### Tests
(No pre-written test file — verified via 1023 existing tests passing + manual smoke tests)

### Implementation
- `cards/foundations/basic_lands.py` — Plains, Island, Swamp, Mountain, Forest subclasses of Land with Supertype.BASIC, land-type subtypes, and ManaAbility tap-for-mana; register_basic_lands(registry) registration helper

## Item 20: Vanilla and French vanilla creatures from Foundations (~15 cards)

### Tests
`tests/cards/test_simple_creatures.py` — Tests for creature stats, keywords, registry, combat integration (will be rewritten by Tester to match new creature list)

### Implementation
- `cards/foundations/simple_creatures.py` — Replaced all 15 creatures with Scryfall-verified FDN cards: 5 vanilla (Aegis Turtle, Savannah Lions, Bear Cub, Swab Goblin, Highborn Vampire) + 10 French vanilla (Healer's Hawk, Bishop's Soldier, Leonin Skyhunter, Thornweald Archer, Raging Redcap, Brazen Scourge, Vampire Nighthawk, Magnigoth Sentry, Serra Angel, Tajuru Pathwarden); fixed registry metadata with correct rarity, oracle_text, type_line, collector_number

## Item 21: Simple instants and sorceries from Foundations (~10 cards)

### Tests
`tests/cards/test_simple_spells.py` — Tests for spell attributes, targeting, resolution, registry, metadata (will be rewritten by Tester for new FDN card names)

### Implementation
- `cards/foundations/simple_spells.py` — 10 Scryfall-verified FDN spells: Burst Lightning, Incinerating Blast (damage); Giant Growth (buff, layer 7c); Quick Study (draw); Hero's Downfall (removal); Negate, Cancel (counter with can_cast guard); Disenchant, Pilfer, Cemetery Recruitment (utility); shared _get_chosen_target() helper; backward-compatible aliases for old names
- `engine/casting.py` — Store chosen_targets on card object during cast_spell() so targets survive stack pop and are accessible in on_resolve()

## Item 22: Simple enchantments and artifacts from Foundations (~5 cards)

### Tests
`tests/cards/test_simple_permanents.py` — Tests for permanent attributes, aura attachment, continuous effects, combat restrictions, SBAs, mana abilities, registry, metadata

### Implementation
- `cards/foundations/simple_permanents.py` — 5 Scryfall-verified FDN permanents: Pacifism (aura debuff, can't attack/block, layer 6); Untamed Hunger (aura buff, +2/+1 and menace, layer 7c/6); Unflinching Courage (aura buff, +2/+2 trample lifelink, layer 7c/6); Hedron Archive (mana rock, {T}: Add {C}{C}); Goblin Oriflamme (non-aura enchantment, attacking creatures +1/+0, layer 7c); all aura apply functions check aura is on battlefield before applying
- `engine/combat.py` — Added _cant_attack/_cant_block flag checks to _can_attack() and _can_block() so Pacifism actually prevents combat participation
- `engine/card.py` — Added _cant_attack/_cant_block reset to Creature._reset_characteristics() for clean continuous-effect recalculation

## Item 23: End-of-turn cleanup and damage clearing

### Tests
`tests/engine/test_cleanup.py` — 27 tests covering discard-to-hand-size, EOT effect removal, damage clearing, combat flag clearing, mana pool emptying, SBA check, re-cleanup loop, integration scenarios

### Implementation
- `engine/turn.py` — Enhanced _do_cleanup_step: discard loop catches exceptions and discards deterministically instead of breaking (fix 514.1 violation); re-cleanup check uses SBA return value + stack emptiness per rule 514.3a; MAX_HAND_SIZE constant
- `engine/state_based_actions.py` — resolve_state_based_actions() now returns bool indicating whether any SBAs were performed
- `tests/engine/test_game.py` — Fixed test_create_game_and_run_two_turns assertion to verify draw via library shrinkage (accounts for correct cleanup discard behavior)

## Item 24: Integration test: multi-turn game with Foundations cards

### Tests
`tests/test_integration.py` — 9 end-to-end integration tests: 6-turn multi-turn game, combat+SBAs, vigilance, land-tap mana+damage, cleanup-step effect expiry, flying/reach blocking, summoning sickness, land play limits, triggered ability pipeline

### Implementation
- `tests/test_integration.py` — Revised integration smoke test: mana via activate_ability (land tap), stack resolution via priority_loop, cleanup via _do_cleanup_step, new triggered ability test; 9 tests exercising real engine APIs end-to-end
