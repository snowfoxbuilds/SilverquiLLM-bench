# Dropped Coverage — MSH Task #1 (Player Query migration)

V1 `engine_tests/` coverage that could not be re-expressed under the Player Query
protocol because it tested behavior the protocol *deletes* (the positional choice
script, `ScriptExhaustedError`, the per-call `choose_*` methods, `remaining_choices`,
and priority-action *choice* scripting). Each entry names the dropped test(s), why
they cannot survive, and where equivalent coverage now lives.

## `engine_tests/test_player.py` — entire file (removed)
- **What it tested:** the V1 `DeterministicPlayer` two-channel API — the five
  abstract `choose_*` methods, the FIFO `script` deque, `remaining_choices`, and
  `ScriptExhaustedError` raised on an empty script.
- **Why dropped:** all of that surface is deleted by the spec (the `Player` ABC now
  exposes only `answer(query) -> Answer`; there is no script and no
  `ScriptExhaustedError`). The tests assert on classes/attributes that no longer
  exist.
- **Equivalent coverage now:** `engine_tests/test_intent_player.py` exercises the new
  concrete player (routing, preference answering, baseline, ambiguity, decline,
  ordering, postcondition, transcript). The `Player` ABC's state (life/zones/
  mana_pool/has_lost/land_plays_remaining/drawn_from_empty_library) is exercised by
  every test that constructs a player and the engine integration tests.

## `engine_tests/test_cleanup.py::TestDeterministicPlayerDiscard` (4 tests, removed)
- `test_discard_without_script_falls_back_to_last_card`,
  `test_discard_fallback_sends_cards_to_graveyard`,
  `test_discard_partial_script_then_fallback`,
  `test_discard_large_hand_without_script`.
- **Why dropped:** they asserted the V1 `ScriptExhaustedError`-driven auto-discard
  fallback in the cleanup step. Cleanup discard is now an OBJECT Player Query and the
  exception no longer exists.
- **Equivalent coverage now:** `test_cleanup.py::TestDiscardLargeHands` (Intent-driven
  discard reaching max hand size, 9→7 and 15→7).

## `engine_tests/test_stack.py` priority-choice tests (4 tests, removed)
- `TestPriorityLoopEmptyStack::test_does_not_consume_player_choices`,
  `TestPriorityPassing::{test_active_player_asked_first,
  test_both_players_asked_per_resolution_round,
  test_active_player_gets_priority_again_after_resolution}`.
- **Why dropped:** they subclassed/inspected the V1 `choose`/`remaining_choices`
  priority-choice channel and asserted per-round "the player was asked" ordering.
  Priority is now action-layer/directive-driven — `priority_loop` auto-passes and
  never raises a priority *choice* query.
- **Equivalent coverage now:** `test_stack.py::TestPriorityMultiObjectResolution`
  (full LIFO stack drain via `priority_loop`).

## `engine_tests/test_test_utils.py::TestCreateGame::test_scripts_passed_to_players` (removed)
- **Why dropped:** asserted `create_game(scripts=...)` wired a positional script into
  each player and exposed `remaining_choices`; both are deleted.
- **Equivalent coverage now:** `engine_tests/test_intent_test_utils.py` (the Intent
  channel through `create_game`/`cast_spell`).

## `engine_tests/test_test_utils_extra.py::TestCreateGameExtra::test_scripts_default_to_empty` (removed)
- **Why dropped:** asserted the default empty `script`/`remaining_choices`; deleted.
- **Equivalent coverage now:** as above.
