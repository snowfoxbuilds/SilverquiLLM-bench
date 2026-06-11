# Directory Summary — `benchmarks/sos/workspace/engine/`

## Purpose

Core game engine for a Magic: The Gathering implementation, now located within the canonical agent workspace at `benchmarks/sos/workspace/engine/`. Contains **17 Python modules** implementing MTG rules (types, zones, players, mana, cards, casting, stack, combat, triggers, abilities, continuous effects, replacement effects, state-based actions, protection, and the game loop). This is the rules engine layer — card-specific implementations live in `benchmarks/sos/workspace/cards/`. Imported as `benchmarks.sos.workspace.engine`.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `types.py` | 250+ | **Foundation** — All enums (`Color`, `ManaType`, `Zone`, `Phase`, `Step`, `CardType`, `Supertype`, `Keyword`) and core dataclasses (`ManaCost` with `.parse()` and `.cmc`, `HybridManaSymbol`, `TargetRequirement` with lazy `filter_fn` convention). `ManaCost.parse()` handles `{X/Y}` hybrid mana tokens. Zero internal dependencies. |
| `zones.py` | 168 | `ZoneContainer` (ordered list with add/remove/shuffle/top/bottom), `Zones` (per-player Zone→ZoneContainer mapping), `move_zone()` function, `move_to_zone()` (centralized zone-transition with replacement effects, event firing, trigger registration/unregistration hooks), `IllegalMoveError`. Uses identity-based (`is`) lookups. |
| `player.py` | 167 | `Player` (ABC) with life/zones/mana_pool/has_lost properties and 5 abstract methods (`choose`, `choose_card`, `choose_attackers`, `choose_blockers`, `choose_order`). `DeterministicPlayer` with FIFO scripted choices. `ScriptExhaustedError`. |
| `mana.py` | 200+ | `ManaPool` class — add/empty/total/get/can_pay/pay methods. Auto-pay generic costs preferring colorless mana. Backtracking hybrid mana symbol resolution in `can_pay()`/`pay()`. `last_payment_colors` property and `_MANA_TO_COLOR` mapping for Converge mechanic support. |
| `card.py` | 490+ | `GameObject` (auto-increment ID), `CardImpl` interface (hook methods: `can_cast`, `get_targets`, `on_cast`, `on_resolve`, `get_mana_abilities`, `get_triggers`, `register_replacement_effects`, `cost_reduction(game) -> int`). Concrete subclasses: `Creature` (with `_cant_be_blocked`, `_cant_activate`, `protections` list reset in `_reset_characteristics()`), `Instant`, `Sorcery`, `Enchantment`, `Aura`, `Artifact`, `ArtifactCreature`, `Planeswalker`, `Land`. Supporting dataclasses: `ActivatedAbility`, `LoyaltyAbility`, `ManaAbility`, `ContinuousEffect`, `Mode`. |
| `game_state.py` | 180+ | `GameState` — central state container holding players, stack, trigger/effect/replacement managers, combat state, phase/step tracking, turn number, priority index. `extra_turns: list[int]` FIFO queue for extra turn management. `_normal_next_index` for tracking normal rotation independently. `_TURN_SEQUENCE` constant. `advance_phase()` for turn progression (pops extra turns without advancing normal rotation). |
| `stack.py` | 174 | `StackObject` dataclass, `Stack` (LIFO container), `priority_loop()` with auto-pass and stack resolution, `check_state_based_actions()` wrapper. |
| `casting.py` | 340+ | `cast_spell()` (hand→stack→targets→cost reduction→pay mana→on_cast→push), `play_land()`, `is_sorcery_speed()`, `can_cast_at_instant_speed()`. Cost reduction via `get_cost_reduction()` / `_apply_cost_reduction()`. Protection targeting check (rejects targets with protection from the spell). Wires trigger/replacement-effect auto-registration on resolution. Uses `move_to_zone()` for spell resolution. Stores `colors_spent` on card after mana payment for Converge mechanic. `_resolve_spell()` reads targets from `StackObject.targets` (single source of truth) and sets `card.chosen_targets` at resolve time. Validates `filter_fn` on targets at cast time. |
| `combat.py` | 560+ | `CombatState` dataclass, `declare_attackers_step()`, `declare_blockers_step()`, `combat_damage_step()`, `end_combat_step()`. Handles first strike, double strike, trample, lifelink, deathtouch, flying/reach, menace, vigilance, summoning sickness. Protection checks in `_can_block()` and `_deal_damage()`. |
| `protection.py` | 166 | **Protection from qualities** — `ProtectionAbility` class (color/type/quality matching), `get_colors()`, `get_protections()`, `has_protection_from()`. DEBT helper functions: `_is_illegal_target_due_to_protection()`, `_is_illegal_block_due_to_protection()`, `_should_prevent_damage()`, `_aura_illegal_due_to_protection()`. |
| `abilities.py` | 273 | `activate_ability()`, `tap_cost()`, `ActivatedAbilityInstance`, `LoyaltyAbilityInstance` (per-turn tracking), `AbilityError`. Mana abilities resolve immediately; non-mana go on stack. |
| `triggers.py` | 175+ | `EventType` enum (14 events including `END_STEP`), `TriggerRegistration` dataclass, `TriggerManager` (register/unregister/fire_event with APNAP ordering). |
| `continuous_effects.py` | 247 | `Layer` (7 layers), `SubLayer` (7a–7d), `ContinuousEffect` dataclass, `EffectManager` (add/remove/apply_all with reset-then-reapply idempotency). Duration constants. |
| `replacement_effects.py` | 209 | `ReplacementEffect` dataclass, `ReplacementManager` (register/unregister/apply with self-replacement prevention and player-choice ordering). |
| `state_based_actions.py` | 350+ | 8 SBAs: life≤0, toughness≤0, lethal damage (incl. deathtouch), empty library, legend rule, token cleanup, aura validity (extended for protection), counter annihilation. `check_state_based_actions()` (single pass), `resolve_state_based_actions()` (loop until stable with trigger queueing, returns bool). Fires `CREATURE_DIES`/`LEAVES_BATTLEFIELD` events in `_move_to_graveyard()`. Detaches auras/equipment from permanents with protection from them. |
| `turn.py` | 181 | `run_turn()` — full turn loop. Turn-based actions: untap step, draw step (skip turn 1 for starting player), combat delegation, cleanup (discard to hand size, clear damage/effects/mana, re-cleanup loop). |
| `game.py` | 610+ | `create_game()` (life/library/shuffle/draw-7), 11 helper actions (`deal_damage`, `destroy`, `sacrifice`, `exile`, `draw_card`, `discard`, `create_token`, `add_counter`, `remove_counter`, `tap`, `untap`), `run_game()` loop with SBA checking and `MAX_TURNS` safety. `destroy()`, `sacrifice()`, `exile()` delegate to `move_to_zone()`. `deal_damage()` checks protection before applying damage. Tracks `cards_drawn_this_turn` in `draw_card()`. |

## Important Classes / Functions

- **`GameState`** — The central authority; passed to nearly every function. Now includes `extra_turns` queue.
- **`CardImpl`** — Interface all cards implement; hook methods define card-specific behavior. Includes `cost_reduction(game)` hook.
- **`Player` / `DeterministicPlayer`** — Player abstraction; deterministic variant for testing.
- **`move_to_zone()`** — Centralized zone-transition function handling replacement effects, event firing, and trigger auto-registration/unregistration.
- **`priority_loop()`** — Core game flow: SBA check → priority pass → stack resolution.
- **`cast_spell()` / `play_land()`** — Entry points for playing cards. `cast_spell()` applies cost reductions, protection checks, and `filter_fn` validation.
- **`run_turn()` / `run_game()`** — Top-level game loop orchestration.
- **`ProtectionAbility`** — Protection from color/type/quality with DEBT mnemonic helpers.
- **`HybridManaSymbol`** — Represents `{X/Y}` hybrid mana symbols in costs.
- **`TargetRequirement.filter_fn`** — Lazy filter evaluated at cast time (not snapshot-at-definition-time); enables dynamic target validation.

## Dependencies

- **External**: None (pure Python, stdlib only).
- **Internal**: `types.py` is the foundation with no internal deps. `protection.py` depends on `types.py`. All other modules depend on `types.py`. `game_state.py` is the central hub importing from most modules. `game.py`, `combat.py`, `casting.py`, and `state_based_actions.py` import from `protection.py`. `game.py` and `turn.py` are top-level orchestrators.

## Testing

- Tests in `tests/engine/` — one test file per module (e.g., `test_types.py`, `test_card.py`), plus `test_lazy_targets.py` (lazy filter evaluation) and `test_chosen_targets_refactor.py` (resolve-time target availability).
- ~1,140+ engine-specific tests covering all modules (including hybrid mana, cost reduction, protection, extra turns, lazy targets, chosen_targets refactor).
- Test utilities in `tests/test_utils.py` for convenient game setup.
