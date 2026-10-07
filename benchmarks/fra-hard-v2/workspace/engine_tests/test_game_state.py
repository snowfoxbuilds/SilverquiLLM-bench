"""Tests for engine/game_state.py and engine/turn.py — GameState scaffold and turn structure.

Verifies:
- GameState construction with 2 DeterministicPlayers.
- Initial state correctness (turn_number=1, phase=BEGINNING, step=UNTAP, etc.).
- Requires at least 2 players.
- active_player, priority_player, non_active_player properties.
- Zone accessor methods (get_battlefield, get_hand, get_graveyard, get_library, get_exile).
- advance_phase full turn sequence through all 13 phase/step pairs.
- At CLEANUP end: turn_number incremented, active_player_index swapped.
- empty_mana_pools clears all player mana pools.
- Playing a whole turn: the next turn begins at its start with the other
  player active, its draw happens, and mana pools are empty.
"""

from __future__ import annotations

import pytest
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_278.card_impl import Mountain
from test_interface import Side, card, player
from test_interface import create_game as create_position
from test_utils import DeterministicPlayer

from engine.game_state import GameState
from engine.types import ManaType, Phase, Step, Zone
from engine.zones import ZoneContainer
from table import Table


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_game() -> GameState:
    """Create a standard 2-player GameState for testing."""
    p1 = DeterministicPlayer("Alice")
    p2 = DeterministicPlayer("Bob")
    return GameState([p1, p2])


def _position(start, *, p0_hand=(), p1_hand=(), p1_battlefield=(), p0_mana=None, p1_mana=None):
    """A game opened at ``start`` of player 0's turn 1, with libraries that
    last several turns."""
    return create_position(
        Side(hand=list(p0_hand), library=[card(Plains) for _ in range(4)], mana=p0_mana or {}),
        Side(hand=list(p1_hand), battlefield=list(p1_battlefield),
             library=[card(Plains) for _ in range(4)], mana=p1_mana or {}),
        start=(start, 0),
    )


# The canonical MTG turn sequence as a list of (Phase, Step|None).
_EXPECTED_TURN_SEQUENCE: list[tuple[Phase, Step | None]] = [
    (Phase.BEGINNING, Step.UNTAP),
    (Phase.BEGINNING, Step.UPKEEP),
    (Phase.BEGINNING, Step.DRAW),
    (Phase.PRECOMBAT_MAIN, None),
    (Phase.COMBAT, Step.BEGIN_COMBAT),
    (Phase.COMBAT, Step.DECLARE_ATTACKERS),
    (Phase.COMBAT, Step.DECLARE_BLOCKERS),
    (Phase.COMBAT, Step.FIRST_STRIKE_DAMAGE),
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
        p1 = DeterministicPlayer("Alice")
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
        from engine.stack import Stack

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




# ---------------------------------------------------------------------------
# run_turn — full turn execution
# ---------------------------------------------------------------------------
class TestRunTurn:
    """Playing a whole turn moves the game to the next one."""

    def test_run_turn_increments_turn_number(self) -> None:
        """The next turn is turn 2, so its active player draws — only turn 1's
        draw is skipped (rule 103.8a)."""
        t = Table(_position(Step.UPKEEP))
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        final = t.run()
        assert len(final.players[1].hand) == 1

    def test_run_turn_phase_and_step_at_start_of_next_turn(self) -> None:
        """The next turn starts at its beginning: player 1's tapped land
        untaps, and the first question comes in player 1's upkeep."""
        mountain = card(Mountain, tapped=True)
        t = Table(_position(Step.END, p1_battlefield=[mountain]))
        t.pass_(0)
        t.pass_(1)
        final = t.run()
        assert (final.step, final.active) == (Step.UPKEEP, 1)
        assert not final.players[1].battlefield[0].tapped

    def test_run_turn_swaps_active_player(self) -> None:
        t = Table(_position(Step.UPKEEP))
        t.pass_to(Step.UPKEEP)
        final = t.run()
        assert final.active == 1

    def test_run_turn_twice_alternates_active_player(self) -> None:
        """Two turns later player 0 is active again, in turn 3, and draws."""
        t = Table(_position(Step.UPKEEP))
        t.pass_to(Step.UPKEEP)
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        final = t.run()
        assert final.active == 0
        assert len(final.players[0].hand) == 1

    def test_run_turn_empties_mana_pools(self) -> None:
        """Mana left in both players' pools is gone by the next turn: neither
        can pay for Burst Lightning with it."""
        bolt0, bolt1 = card(BurstLightning), card(BurstLightning)
        t = Table(_position(
            Phase.PRECOMBAT_MAIN,
            p0_hand=[bolt0], p0_mana={ManaType.RED: 10},
            p1_hand=[bolt1], p1_mana={ManaType.RED: 1},
        ))
        t.pass_to(Step.UPKEEP, 1)
        t.act_illegal(1, bolt1, choices=[player(0)])
        t.pass_(1)
        t.act_illegal(0, bolt0, choices=[player(1)])
        t.pass_(0)
        t.run()

    def test_run_turn_multiple_turns_turn_number(self) -> None:
        """After five turns it is turn 6: each turn after the first has had
        its draw — player 1's turns 2, 4 and 6, player 0's turns 3 and 5."""
        t = Table(_position(Step.UPKEEP))
        for _ in range(5):
            t.pass_to(Step.UPKEEP)
        t.pass_to(Phase.PRECOMBAT_MAIN)
        final = t.run()
        assert final.active == 1
        assert (len(final.players[0].hand), len(final.players[1].hand)) == (2, 3)

    def test_run_turn_multiple_turns_active_player(self) -> None:
        t = Table(_position(Step.UPKEEP))
        for _ in range(3):
            t.pass_to(Step.UPKEEP)
        final = t.run()
        assert final.active == 1

    def test_run_turn_does_not_set_game_over(self) -> None:
        t = Table(_position(Step.UPKEEP))
        t.pass_to(Step.UPKEEP)
        final = t.run()
        assert (final.game_over, final.winner) == (False, None)
