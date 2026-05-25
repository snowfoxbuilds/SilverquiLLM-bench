"""Tests for engine/game_state.py and engine/turn.py — GameState scaffold and turn structure.

Verifies:
- GameState construction with 2 DeterministicPlayers.
- Initial state correctness (turn_number=1, phase=BEGINNING, step=UNTAP, etc.).
- Requires at least 2 players.
- active_player, priority_player, non_active_player properties.
- Zone accessor methods (get_battlefield, get_hand, get_graveyard, get_library, get_exile).
- advance_phase full turn sequence through all 12 phase/step pairs.
- At CLEANUP end: turn_number incremented, active_player_index swapped.
- empty_mana_pools clears all player mana pools.
- run_turn executes a full turn cycle.
- Multiple run_turn calls alternate active player.
"""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.engine.game_state import GameState
from benchmarks.sos.workspace.engine.mana import ManaPool
from benchmarks.sos.workspace.engine.player import DeterministicPlayer
from benchmarks.sos.workspace.engine.turn import run_turn
from benchmarks.sos.workspace.engine.types import ManaType, Phase, Step, Zone
from benchmarks.sos.workspace.engine.zones import ZoneContainer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_game() -> GameState:
    """Create a standard 2-player GameState for testing."""
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    return GameState([p1, p2])


# The canonical MTG turn sequence as a list of (Phase, Step|None).
_EXPECTED_TURN_SEQUENCE: list[tuple[Phase, Step | None]] = [
    (Phase.BEGINNING, Step.UNTAP),
    (Phase.BEGINNING, Step.UPKEEP),
    (Phase.BEGINNING, Step.DRAW),
    (Phase.PRECOMBAT_MAIN, None),
    (Phase.COMBAT, Step.BEGIN_COMBAT),
    (Phase.COMBAT, Step.DECLARE_ATTACKERS),
    (Phase.COMBAT, Step.DECLARE_BLOCKERS),
    (Phase.COMBAT, Step.COMBAT_DAMAGE),
    (Phase.COMBAT, Step.END_COMBAT),
    (Phase.POSTCOMBAT_MAIN, None),
    (Phase.ENDING, Step.END),
    (Phase.ENDING, Step.CLEANUP),
]


# ---------------------------------------------------------------------------
# GameState — construction
# ---------------------------------------------------------------------------
class TestGameStateConstruction:
    """Tests for GameState construction and initial state."""

    def test_construction_with_two_players(self) -> None:
        """GameState should accept a list of 2 players."""
        game = _make_game()
        assert len(game.players) == 2

    def test_players_stored_in_order(self) -> None:
        """Players should be stored in the order provided."""
        game = _make_game()
        assert game.players[0].name == "Alice"
        assert game.players[1].name == "Bob"

    def test_requires_at_least_two_players(self) -> None:
        """GameState should raise ValueError if fewer than 2 players are provided."""
        p1 = DeterministicPlayer("Alice", [])
        with pytest.raises(ValueError, match="at least 2"):
            GameState([p1])

    def test_requires_at_least_two_players_empty_list(self) -> None:
        """GameState should raise ValueError for an empty player list."""
        with pytest.raises(ValueError, match="at least 2"):
            GameState([])


# ---------------------------------------------------------------------------
# GameState — initial state
# ---------------------------------------------------------------------------
class TestGameStateInitialState:
    """Tests that all initial attributes are correct after construction."""

    def test_initial_turn_number(self) -> None:
        """Turn number should start at 1."""
        game = _make_game()
        assert game.turn_number == 1

    def test_initial_phase(self) -> None:
        """Initial phase should be BEGINNING."""
        game = _make_game()
        assert game.phase == Phase.BEGINNING

    def test_initial_step(self) -> None:
        """Initial step should be UNTAP."""
        game = _make_game()
        assert game.step == Step.UNTAP

    def test_initial_active_player_index(self) -> None:
        """Active player index should start at 0."""
        game = _make_game()
        assert game.active_player_index == 0

    def test_initial_priority_player_index(self) -> None:
        """Priority player index should start at 0."""
        game = _make_game()
        assert game.priority_player_index == 0

    def test_initial_is_game_over(self) -> None:
        """is_game_over should be False at game start."""
        game = _make_game()
        assert game.is_game_over is False

    def test_initial_winner_is_none(self) -> None:
        """winner should be None at game start."""
        game = _make_game()
        assert game.winner is None

    def test_initial_stack_is_stack_instance(self) -> None:
        """stack should be an empty Stack instance."""
        game = _make_game()
        from benchmarks.sos.workspace.engine.stack import Stack

        assert isinstance(game.stack, Stack)
        assert game.stack.is_empty()


# ---------------------------------------------------------------------------
# GameState — player properties
# ---------------------------------------------------------------------------
class TestGameStatePlayerProperties:
    """Tests for active_player, priority_player, non_active_player properties."""

    def test_active_player_is_first_player(self) -> None:
        """active_player should return the player at active_player_index (initially player 0)."""
        game = _make_game()
        assert game.active_player is game.players[0]
        assert game.active_player.name == "Alice"

    def test_priority_player_is_first_player(self) -> None:
        """priority_player should return the player at priority_player_index (initially player 0)."""
        game = _make_game()
        assert game.priority_player is game.players[0]
        assert game.priority_player.name == "Alice"

    def test_non_active_player_is_second_player(self) -> None:
        """non_active_player should return the player who is NOT the active player."""
        game = _make_game()
        assert game.non_active_player is game.players[1]
        assert game.non_active_player.name == "Bob"

    def test_active_player_changes_after_full_turn(self) -> None:
        """After advancing through all phases, active_player should swap."""
        game = _make_game()
        # Advance through all 12 steps (11 advances to get to CLEANUP, 1 more to wrap)
        for _ in range(len(_EXPECTED_TURN_SEQUENCE)):
            game.advance_phase()
        # Now should be turn 2 with player 1 (Bob) as active
        assert game.active_player is game.players[1]
        assert game.active_player.name == "Bob"

    def test_non_active_player_after_swap(self) -> None:
        """After full turn, non_active_player should be the original active player."""
        game = _make_game()
        for _ in range(len(_EXPECTED_TURN_SEQUENCE)):
            game.advance_phase()
        assert game.non_active_player is game.players[0]
        assert game.non_active_player.name == "Alice"

    def test_priority_player_tracks_active_after_turn_swap(self) -> None:
        """After a full turn wrap, priority_player_index should follow active_player_index."""
        game = _make_game()
        for _ in range(len(_EXPECTED_TURN_SEQUENCE)):
            game.advance_phase()
        assert game.priority_player is game.active_player


# ---------------------------------------------------------------------------
# GameState — zone accessors
# ---------------------------------------------------------------------------
class TestGameStateZoneAccessors:
    """Tests for get_battlefield, get_hand, get_graveyard, get_library, get_exile."""

    def test_get_battlefield_returns_zone_container(self) -> None:
        """get_battlefield should return a ZoneContainer."""
        game = _make_game()
        bf = game.get_battlefield(game.players[0])
        assert isinstance(bf, ZoneContainer)

    def test_get_hand_returns_zone_container(self) -> None:
        """get_hand should return a ZoneContainer."""
        game = _make_game()
        hand = game.get_hand(game.players[0])
        assert isinstance(hand, ZoneContainer)

    def test_get_graveyard_returns_zone_container(self) -> None:
        """get_graveyard should return a ZoneContainer."""
        game = _make_game()
        gy = game.get_graveyard(game.players[0])
        assert isinstance(gy, ZoneContainer)

    def test_get_library_returns_zone_container(self) -> None:
        """get_library should return a ZoneContainer."""
        game = _make_game()
        lib = game.get_library(game.players[0])
        assert isinstance(lib, ZoneContainer)

    def test_get_exile_returns_zone_container(self) -> None:
        """get_exile should return a ZoneContainer."""
        game = _make_game()
        exile = game.get_exile(game.players[0])
        assert isinstance(exile, ZoneContainer)

    def test_zone_accessors_return_correct_player_zones(self) -> None:
        """Zone accessors should return zones belonging to the specified player, not the other."""
        game = _make_game()
        p1, p2 = game.players

        # Add a sentinel to player 1's hand
        sentinel = object()
        game.get_hand(p1).add(sentinel)

        # Player 1's hand should contain the sentinel
        assert game.get_hand(p1).contains(sentinel)
        # Player 2's hand should NOT
        assert not game.get_hand(p2).contains(sentinel)

    def test_zone_accessors_map_to_correct_zone_enum(self) -> None:
        """Each accessor should delegate to the correct Zone enum on the player."""
        game = _make_game()
        p = game.players[0]

        assert game.get_battlefield(p) is p.zones[Zone.BATTLEFIELD]
        assert game.get_hand(p) is p.zones[Zone.HAND]
        assert game.get_graveyard(p) is p.zones[Zone.GRAVEYARD]
        assert game.get_library(p) is p.zones[Zone.LIBRARY]
        assert game.get_exile(p) is p.zones[Zone.EXILE]


# ---------------------------------------------------------------------------
# GameState — advance_phase full turn sequence
# ---------------------------------------------------------------------------
class TestAdvancePhaseSequence:
    """Tests for advance_phase walking the full MTG turn structure."""

    def test_initial_state_is_beginning_untap(self) -> None:
        """Before any advance, state should be (BEGINNING, UNTAP)."""
        game = _make_game()
        assert (game.phase, game.step) == (Phase.BEGINNING, Step.UNTAP)

    def test_full_turn_sequence(self) -> None:
        """advance_phase should walk through all 12 phase/step pairs in MTG order.

        Starting from (BEGINNING, UNTAP), each call to advance_phase should
        move to the next expected pair. After 11 advances we should be at
        (ENDING, CLEANUP). The 12th advance wraps to the next turn.
        """
        game = _make_game()

        # We start at index 0. Each advance moves to the next index.
        for i in range(1, len(_EXPECTED_TURN_SEQUENCE)):
            game.advance_phase()
            expected_phase, expected_step = _EXPECTED_TURN_SEQUENCE[i]
            assert game.phase == expected_phase, (
                f"After {i} advance(s): expected phase {expected_phase}, got {game.phase}"
            )
            assert game.step == expected_step, (
                f"After {i} advance(s): expected step {expected_step}, got {game.step}"
            )

        # Still on turn 1 at (ENDING, CLEANUP)
        assert game.turn_number == 1

    def test_advance_from_beginning_untap_to_upkeep(self) -> None:
        """First advance should move from UNTAP to UPKEEP (same phase)."""
        game = _make_game()
        game.advance_phase()
        assert game.phase == Phase.BEGINNING
        assert game.step == Step.UPKEEP

    def test_advance_from_upkeep_to_draw(self) -> None:
        """Second advance: UPKEEP → DRAW."""
        game = _make_game()
        game.advance_phase()  # UPKEEP
        game.advance_phase()  # DRAW
        assert game.phase == Phase.BEGINNING
        assert game.step == Step.DRAW

    def test_advance_from_draw_to_precombat_main(self) -> None:
        """Third advance: DRAW → PRECOMBAT_MAIN (step=None)."""
        game = _make_game()
        for _ in range(3):
            game.advance_phase()
        assert game.phase == Phase.PRECOMBAT_MAIN
        assert game.step is None

    def test_advance_through_combat_phase(self) -> None:
        """Advances 4-8 should walk through the 5 combat steps."""
        game = _make_game()
        for _ in range(4):
            game.advance_phase()
        assert (game.phase, game.step) == (Phase.COMBAT, Step.BEGIN_COMBAT)

        game.advance_phase()
        assert (game.phase, game.step) == (Phase.COMBAT, Step.DECLARE_ATTACKERS)

        game.advance_phase()
        assert (game.phase, game.step) == (Phase.COMBAT, Step.DECLARE_BLOCKERS)

        game.advance_phase()
        assert (game.phase, game.step) == (Phase.COMBAT, Step.COMBAT_DAMAGE)

        game.advance_phase()
        assert (game.phase, game.step) == (Phase.COMBAT, Step.END_COMBAT)

    def test_advance_to_postcombat_main(self) -> None:
        """After combat, advance to POSTCOMBAT_MAIN (step=None)."""
        game = _make_game()
        for _ in range(9):
            game.advance_phase()
        assert game.phase == Phase.POSTCOMBAT_MAIN
        assert game.step is None

    def test_advance_through_ending_phase(self) -> None:
        """Advances 10-11 walk through END and CLEANUP."""
        game = _make_game()
        for _ in range(10):
            game.advance_phase()
        assert (game.phase, game.step) == (Phase.ENDING, Step.END)

        game.advance_phase()
        assert (game.phase, game.step) == (Phase.ENDING, Step.CLEANUP)

    def test_cleanup_wraps_to_next_turn(self) -> None:
        """Advancing from CLEANUP should wrap to BEGINNING/UNTAP of next turn."""
        game = _make_game()
        # Advance through all 12 steps (starts at 0, 12 advances wraps)
        for _ in range(len(_EXPECTED_TURN_SEQUENCE)):
            game.advance_phase()
        assert game.phase == Phase.BEGINNING
        assert game.step == Step.UNTAP

    def test_turn_number_increments_at_cleanup(self) -> None:
        """turn_number should be 2 after advancing through an entire turn."""
        game = _make_game()
        for _ in range(len(_EXPECTED_TURN_SEQUENCE)):
            game.advance_phase()
        assert game.turn_number == 2

    def test_active_player_swaps_at_cleanup(self) -> None:
        """active_player_index should swap from 0 to 1 at end of turn."""
        game = _make_game()
        assert game.active_player_index == 0
        for _ in range(len(_EXPECTED_TURN_SEQUENCE)):
            game.advance_phase()
        assert game.active_player_index == 1

    def test_turn_number_stays_same_within_turn(self) -> None:
        """turn_number should remain 1 throughout all steps before the wrap."""
        game = _make_game()
        for i in range(len(_EXPECTED_TURN_SEQUENCE) - 1):
            game.advance_phase()
            assert game.turn_number == 1, f"turn_number changed after {i + 1} advance(s)"

    def test_two_full_turns_return_to_original_active_player(self) -> None:
        """After 2 complete turns, active_player should be back to player 0."""
        game = _make_game()
        steps_per_turn = len(_EXPECTED_TURN_SEQUENCE)
        for _ in range(steps_per_turn * 2):
            game.advance_phase()
        assert game.active_player_index == 0
        assert game.turn_number == 3

    def test_three_full_turns_active_player_alternation(self) -> None:
        """active_player_index should alternate: 0 → 1 → 0 → 1 over 3 turns."""
        game = _make_game()
        steps_per_turn = len(_EXPECTED_TURN_SEQUENCE)
        for turn in range(3):
            for _ in range(steps_per_turn):
                game.advance_phase()
            expected_index = (turn + 1) % 2
            assert game.active_player_index == expected_index, (
                f"After turn {turn + 1}: expected active index {expected_index}"
            )


# ---------------------------------------------------------------------------
# GameState — empty_mana_pools
# ---------------------------------------------------------------------------
class TestEmptyManaPools:
    """Tests for empty_mana_pools clearing all players' mana pools."""

    def test_empty_mana_pools_clears_both_players(self) -> None:
        """empty_mana_pools should set both players' mana pools to zero."""
        game = _make_game()
        game.players[0].mana_pool.add(ManaType.RED, 3)
        game.players[1].mana_pool.add(ManaType.BLUE, 2)
        game.players[1].mana_pool.add(ManaType.GREEN, 5)

        game.empty_mana_pools()

        assert game.players[0].mana_pool.total() == 0
        assert game.players[1].mana_pool.total() == 0

    def test_empty_mana_pools_on_already_empty(self) -> None:
        """empty_mana_pools on empty pools should be a safe no-op."""
        game = _make_game()
        game.empty_mana_pools()
        assert game.players[0].mana_pool.total() == 0
        assert game.players[1].mana_pool.total() == 0

    def test_advance_phase_empties_mana_pools(self) -> None:
        """Each advance_phase call should empty mana pools (MTG rules)."""
        game = _make_game()
        game.players[0].mana_pool.add(ManaType.WHITE, 5)
        game.players[1].mana_pool.add(ManaType.BLACK, 3)

        game.advance_phase()

        assert game.players[0].mana_pool.total() == 0
        assert game.players[1].mana_pool.total() == 0

    def test_mana_pools_emptied_each_advance(self) -> None:
        """Adding mana between advances: pools should be emptied on each advance."""
        game = _make_game()
        game.players[0].mana_pool.add(ManaType.RED, 2)
        game.advance_phase()  # UNTAP → UPKEEP, pools emptied
        assert game.players[0].mana_pool.total() == 0

        # Add again, advance again
        game.players[0].mana_pool.add(ManaType.GREEN, 4)
        game.advance_phase()  # UPKEEP → DRAW, pools emptied
        assert game.players[0].mana_pool.total() == 0


# ---------------------------------------------------------------------------
# run_turn — full turn execution
# ---------------------------------------------------------------------------
class TestRunTurn:
    """Tests for run_turn() in engine/turn.py."""

    def test_run_turn_increments_turn_number(self) -> None:
        """run_turn should advance through the full turn and increment turn_number."""
        game = _make_game()
        assert game.turn_number == 1
        run_turn(game)
        assert game.turn_number == 2

    def test_run_turn_phase_and_step_at_start_of_next_turn(self) -> None:
        """After run_turn, the game should be at BEGINNING/UNTAP of the next turn."""
        game = _make_game()
        run_turn(game)
        assert game.phase == Phase.BEGINNING
        assert game.step == Step.UNTAP

    def test_run_turn_swaps_active_player(self) -> None:
        """run_turn should swap the active player."""
        game = _make_game()
        assert game.active_player.name == "Alice"
        run_turn(game)
        assert game.active_player.name == "Bob"

    def test_run_turn_twice_alternates_active_player(self) -> None:
        """Two run_turn calls should bring active player back to player 0."""
        game = _make_game()
        run_turn(game)
        assert game.active_player.name == "Bob"
        run_turn(game)
        assert game.active_player.name == "Alice"
        assert game.turn_number == 3

    def test_run_turn_empties_mana_pools(self) -> None:
        """Mana pools should be empty after run_turn completes."""
        game = _make_game()
        game.players[0].mana_pool.add(ManaType.RED, 10)
        run_turn(game)
        assert game.players[0].mana_pool.total() == 0
        assert game.players[1].mana_pool.total() == 0

    def test_run_turn_multiple_turns_turn_number(self) -> None:
        """Running 5 turns should yield turn_number == 6."""
        game = _make_game()
        for _ in range(5):
            run_turn(game)
        assert game.turn_number == 6

    def test_run_turn_multiple_turns_active_player(self) -> None:
        """After an odd number of run_turn calls, active player should be player 1."""
        game = _make_game()
        for _ in range(3):
            run_turn(game)
        assert game.active_player_index == 1  # 0 → 1 → 0 → 1

    def test_run_turn_does_not_set_game_over(self) -> None:
        """run_turn (with stub priority_loop) should not set is_game_over."""
        game = _make_game()
        run_turn(game)
        assert game.is_game_over is False
        assert game.winner is None
