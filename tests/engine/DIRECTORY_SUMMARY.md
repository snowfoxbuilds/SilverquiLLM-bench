# Directory Summary — `tests/engine/`

## Purpose

Unit tests for all `engine/` modules. Each engine module has a corresponding test file. Contains ~850 test functions providing thorough coverage of the game engine's rules implementation.

## Key Files

| File | Tests | Covers |
|------|-------|--------|
| `test_types.py` | 56 | All enums (`Color`, `ManaType`, `Zone`, `Phase`, `Step`, `CardType`, `Supertype`, `Keyword`), `ManaCost` (construction, `.cmc`, `.parse()`, rejection of invalid input), `TargetRequirement` |
| `test_zones.py` | 43 | `ZoneContainer` (add/remove/contains/get_all/top/bottom/shuffle), `Zones.new_player()`, `move_zone` round-trip, `IllegalMoveError`, identity-based lookups |
| `test_player.py` | 33 | `Player` ABC enforcement, default properties, `DeterministicPlayer` FIFO choices, `ScriptExhaustedError`, `remaining_choices` tracking, mana pool integration |
| `test_mana.py` | 45 | `ManaPool` construction, add/get/total, empty, `can_pay`, `pay` (with choices & auto-pay), generic cost payment, Player integration |
| `test_card.py` | 87 | `GameObject` IDs, `CardImpl` fields/hooks, all card subtypes (`Creature`, `Instant`, `Sorcery`, `Enchantment`, `Aura`, `Artifact`, `ArtifactCreature`, `Planeswalker`, `Land`), counters, keywords, supporting dataclasses |
| `test_game_state.py` | 51 | `GameState` construction, 2-player validation, initial state, player/zone accessors, phase/step advancement, mana pool clearing |
| `test_stack.py` | 39 | `StackObject`, `Stack` LIFO operations, `priority_loop` auto-pass/resolution, priority passing with scripts, mana ability immediate resolution |
| `test_casting.py` | 69 | Timing helpers, `cast_spell` (all card types, timing checks, mana, hooks, stack zone), `play_land` (timing, limits), permanent type detection |
| `test_state_based_actions.py` | 50 | All 8 SBAs, `check`/`resolve` API, cascading, multi-SBA passes |
| `test_triggers.py` | 44 | `EventType` enum, `TriggerRegistration`, `TriggerManager` register/unregister/fire_event, condition filtering, APNAP ordering, ETB flow |
| `test_abilities.py` | 51 | Ability construction, mana/non-mana activation, `tap_cost`, timing, loyalty abilities (positive/negative/zero cost, once-per-turn), land tap integration |
| `test_combat.py` | 52 | `CombatState`, attackers, blockers, combat damage (first strike, double strike, trample, lifelink, deathtouch, flying/reach, menace, vigilance), end combat |
| `test_continuous_effects.py` | 71 | Layer enum, `ContinuousEffect`, `EffectManager` add/remove/apply_all, layer ordering, sublayers, duration expiry, idempotent recalculation |
| `test_replacement_effects.py` | 46 | `ReplacementEffect`, `ReplacementManager` register/unregister/apply, conditions, self-replacement prevention, instead semantics, SBA unregistration |
| `test_game.py` | 64 | `create_game`, all 11 helper actions, `run_game` loop, multi-turn integration |
| `test_cleanup.py` | 39 | Discard-to-hand-size, EOT effect removal, damage clearing, combat flag clearing, mana pool emptying, SBA check, re-cleanup loop |
| `test_test_utils.py` | 37 | Meta-tests for `tests/test_utils.py` helpers: `create_game`, `set_board_state`, `cast_spell`, `advance_to_phase`, `declare_attackers`, `declare_blockers` |
| `test_test_utils_extra.py` | 41 | Additional test_utils coverage: edge cases, error handling |

## Dependencies

- All test files import from `engine/` modules.
- Many tests use `DeterministicPlayer` for scripted choices.
- Some tests use `tests/test_utils.py` helpers.

## Testing Approach

- **Isolated unit tests**: Each file focuses on one engine module.
- **Fixture pattern**: `_make_game()`, `_make_player()`, `_make_creature()` local helpers create minimal test fixtures.
- **Class-based grouping**: Related tests grouped in `Test<Feature>` classes (e.g., `TestCastSpellCreature`, `TestCombatDamage`).
- **Deterministic**: All player decisions scripted via `DeterministicPlayer`.
