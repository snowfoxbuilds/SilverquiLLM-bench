# Directory Summary — `tests/`

## Purpose

Test root directory for the SilverquiLLM-bench project. Contains top-level test files, test utilities, and subdirectories for engine and card tests. Uses **pytest** as the test framework with ~1,119 test functions total.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `test_utils.py` | 474 | **Test helper API** — Convenience functions for tests: `create_game()` (wrapper with `DeterministicPlayer`), `set_board_state()` (direct zone/life/mana manipulation), `cast_spell()` (find-in-hand + cast + resolve), `advance_to_phase()` (safe fast-forward), `declare_attackers()` / `declare_blockers()` (name-based combat setup). `TestSetupError` exception. |
| `test_integration.py` | 775 | **End-to-end integration tests** — 9 tests exercising real engine APIs across multiple turns: 6-turn game, combat+SBAs, vigilance, land-tap mana, cleanup effect expiry, flying/reach blocking, summoning sickness, land play limits, triggered ability pipeline. |
| `test_scaffold.py` | 172 | **Project scaffold validation** — Verifies pyproject.toml metadata, directory structure, package importability, py.typed markers, ruff config. |
| `__init__.py` | — | Package init. |

## Important Functions (test_utils.py)

- **`create_game(p1_deck, p2_deck, ...)`** — Creates `GameState` from card lists with `DeterministicPlayer`s. Handles empty decks, mana pool setup.
- **`set_board_state(game, ...)`** — Directly sets zone contents, life totals, and mana pools for mid-game test scenarios.
- **`cast_spell(game, player_idx, card_name)`** — Finds card in hand by name, casts it, resolves the stack. Feeds targets into player script.
- **`advance_to_phase(game, phase, step)`** — Fast-forwards game state to a specific phase/step safely.
- **`declare_attackers(game, attacker_names)` / `declare_blockers(game, blocker_map)`** — Name-based combat setup for readable tests.

## Subdirectories

- **`engine/`** — Unit tests for all engine modules (~850 tests). See `tests/engine/DIRECTORY_SUMMARY.md`.
- **`cards/`** — Unit tests for card implementations (~270 tests). See `tests/cards/DIRECTORY_SUMMARY.md`.

## Testing Approach

- **Deterministic**: All tests use `DeterministicPlayer` with scripted FIFO choices for full reproducibility.
- **Unit + Integration**: Each engine module has its own test file; integration tests validate cross-module interactions.
- **Conventions**: Test classes named `Test<Feature>`, test methods `test_<behavior>`. Fixtures use `_make_game()`, `_make_player()` patterns.
