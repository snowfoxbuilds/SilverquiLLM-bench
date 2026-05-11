# Directory Summary — `tests/engine/`

## Purpose

Unit tests for all engine modules in `engine/`. One test file per engine module, covering types, zones, players, mana, cards, casting, stack, combat, triggers, abilities, continuous effects, replacement effects, state-based actions, protection, game state, extra turns, and the game loop. ~1,050+ test functions.

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package init. |
| `test_types.py` | Enums (Color, ManaType, Zone, Phase, Keyword, etc.), ManaCost parsing and CMC. |
| `test_zones.py` | ZoneContainer operations, identity-based lookups, move_zone. |
| `test_player.py` | Player ABC, DeterministicPlayer scripted choices, ScriptExhaustedError. |
| `test_mana.py` | ManaPool — add, pay, can_pay, auto-pay generic, last_payment_colors (Converge). |
| `test_hybrid_mana.py` | Hybrid mana symbol parsing (`{W/U}`, `{R/G}`, etc.), `can_pay()`/`pay()` with backtracking hybrid resolution. |
| `test_card.py` | GameObject IDs, CardImpl hook methods, Creature/Instant/Sorcery/Enchantment/Artifact/Planeswalker subclasses, Mode, ActivatedAbility, LoyaltyAbility, cost_reduction hook. |
| `test_game_state.py` | GameState construction, phase/step tracking, advance_phase. |
| `test_extra_turns.py` | Extra turns FIFO queue, granting, ordering, normal turn order resumption. |
| `test_stack.py` | StackObject, Stack LIFO, priority_loop, SBA checking. |
| `test_casting.py` | cast_spell, play_land, mana payment, target selection, auto-registration, cost reduction integration. |
| `test_cost_reduction.py` | Cost reduction clamping, application, cast_spell integration. |
| `test_combat.py` | Declare attackers/blockers, combat damage, first strike, double strike, trample, lifelink, deathtouch, flying/reach, menace, vigilance, protection blocking/damage checks. |
| `test_protection.py` | 34 tests covering DEBT mnemonic (Damage, Enchanting/Equipping, Blocking, Targeting), protection from colors/types. |
| `test_abilities.py` | activate_ability, tap cost, mana abilities (immediate resolve), non-mana (stack). |
| `test_triggers.py` | EventType, TriggerRegistration, TriggerManager, APNAP ordering. |
| `test_continuous_effects.py` | Layer system, EffectManager, reset-then-reapply, timestamp ordering. |
| `test_replacement_effects.py` | ReplacementEffect, ReplacementManager, self-replacement prevention. |
| `test_state_based_actions.py` | 8 SBAs — lethal damage, toughness ≤ 0, life ≤ 0, legend rule, aura validity (incl. protection), etc. |
| `test_game.py` | create_game, helper actions (deal_damage, destroy, draw_card, etc.), run_game loop. |
| `test_move_to_zone.py` | Centralized zone transition tests. |
| `test_cleanup.py` | End-of-turn cleanup, discard to hand size, damage clearing. |
| `test_test_utils.py` | Validates test helper API correctness. |
| `test_test_utils_extra.py` | Additional test utility edge cases. |

## Dependencies

- `tests/test_utils.py` — Shared test helpers.
- `engine/` — All engine modules under test.
