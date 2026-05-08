# Directory Summary — `engine/`

## Purpose

Core game engine for a Magic: The Gathering implementation. Contains 16 Python modules implementing MTG rules (types, zones, players, mana, cards, casting, stack, combat, triggers, abilities, continuous effects, replacement effects, state-based actions, and the game loop). This is the rules engine layer — card-specific implementations live in `cards/`.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `types.py` | 215 | **Foundation** — All enums (`Color`, `ManaType`, `Zone`, `Phase`, `Step`, `CardType`, `Supertype`, `Keyword`) and core dataclasses (`ManaCost` with `.parse()` and `.cmc`, `TargetRequirement`). Zero internal dependencies. |
| `zones.py` | 168 | `ZoneContainer` (ordered list with add/remove/shuffle/top/bottom), `Zones` (per-player Zone→ZoneContainer mapping), `move_zone()` function, `IllegalMoveError`. Uses identity-based (`is`) lookups. |
| `player.py` | 167 | `Player` (ABC) with life/zones/mana_pool/has_lost properties and 5 abstract methods (`choose`, `choose_card`, `choose_attackers`, `choose_blockers`, `choose_order`). `DeterministicPlayer` with FIFO scripted choices. `ScriptExhaustedError`. |
| `mana.py` | 175 | `ManaPool` class — add/empty/total/get/can_pay/pay methods. Auto-pay generic costs preferring colorless mana. `last_payment_colors` property and `_MANA_TO_COLOR` mapping for Converge mechanic support. |
| `card.py` | 465+ | `GameObject` (auto-increment ID), `CardImpl` interface (hook methods: `can_cast`, `get_targets`, `on_cast`, `on_resolve`, `get_mana_abilities`, `get_triggers`, `register_replacement_effects`). Concrete subclasses: `Creature` (with `_cant_be_blocked`, `_cant_activate` reset), `Instant`, `Sorcery`, `Enchantment`, `Aura`, `Artifact`, `ArtifactCreature`, `Planeswalker`, `Land`. Supporting dataclasses: `ActivatedAbility`, `LoyaltyAbility`, `ManaAbility`, `ContinuousEffect`, `Mode`. |
| `game_state.py` | 165 | `GameState` — central state container holding players, stack, trigger/effect/replacement managers, combat state, phase/step tracking, turn number, priority index. `_TURN_SEQUENCE` constant. `advance_phase()` for turn progression. |
| `stack.py` | 174 | `StackObject` dataclass, `Stack` (LIFO container), `priority_loop()` with auto-pass and stack resolution, `check_state_based_actions()` wrapper. |
| `casting.py` | 273 | `cast_spell()` (hand→stack→targets→pay mana→on_cast→push), `play_land()`, `is_sorcery_speed()`, `can_cast_at_instant_speed()`. Wires trigger/replacement-effect auto-registration on resolution. Stores `colors_spent` on card after mana payment for Converge mechanic. |
| `combat.py` | 539 | `CombatState` dataclass, `declare_attackers_step()`, `declare_blockers_step()`, `combat_damage_step()`, `end_combat_step()`. Handles first strike, double strike, trample, lifelink, deathtouch, flying/reach, menace, vigilance, summoning sickness. |
| `abilities.py` | 273 | `activate_ability()`, `tap_cost()`, `ActivatedAbilityInstance`, `LoyaltyAbilityInstance` (per-turn tracking), `AbilityError`. Mana abilities resolve immediately; non-mana go on stack. |
| `triggers.py` | 171 | `EventType` enum (13 events), `TriggerRegistration` dataclass, `TriggerManager` (register/unregister/fire_event with APNAP ordering). |
| `continuous_effects.py` | 247 | `Layer` (7 layers), `SubLayer` (7a–7d), `ContinuousEffect` dataclass, `EffectManager` (add/remove/apply_all with reset-then-reapply idempotency). Duration constants. |
| `replacement_effects.py` | 209 | `ReplacementEffect` dataclass, `ReplacementManager` (register/unregister/apply with self-replacement prevention and player-choice ordering). |
| `state_based_actions.py` | 334 | 8 SBAs: life≤0, toughness≤0, lethal damage (incl. deathtouch), empty library, legend rule, token cleanup, aura validity, counter annihilation. `check_state_based_actions()` (single pass), `resolve_state_based_actions()` (loop until stable, returns bool). |
| `turn.py` | 181 | `run_turn()` — full turn loop. Turn-based actions: untap step, draw step (skip turn 1 for starting player), combat delegation, cleanup (discard to hand size, clear damage/effects/mana, re-cleanup loop). |
| `game.py` | 597 | `create_game()` (life/library/shuffle/draw-7), 11 helper actions (`deal_damage`, `destroy`, `sacrifice`, `exile`, `draw_card`, `discard`, `create_token`, `add_counter`, `remove_counter`, `tap`, `untap`), `run_game()` loop with SBA checking and `MAX_TURNS` safety. |

## Important Classes / Functions

- **`GameState`** — The central authority; passed to nearly every function.
- **`CardImpl`** — Interface all cards implement; hook methods define card-specific behavior.
- **`Player` / `DeterministicPlayer`** — Player abstraction; deterministic variant for testing.
- **`priority_loop()`** — Core game flow: SBA check → priority pass → stack resolution.
- **`cast_spell()` / `play_land()`** — Entry points for playing cards.
- **`run_turn()` / `run_game()`** — Top-level game loop orchestration.

## Dependencies

- **External**: None (pure Python, stdlib only). Note: `mana.py` now references `Color` from `types.py` for the Converge color-tracking feature.
- **Internal**: `types.py` is the foundation with no internal deps. All other modules depend on `types.py`. `game_state.py` is the central hub importing from most modules. `game.py` and `turn.py` are top-level orchestrators.

## Testing

- Tests in `tests/engine/` — one test file per module (e.g., `test_types.py`, `test_card.py`).
- ~850 engine-specific tests covering all modules.
- Test utilities in `tests/test_utils.py` for convenient game setup.
