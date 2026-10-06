"""Known-Best engine checks moved out of the Audited Engine Tests' test_game_state.py:
they drive the engine directly or test its internals, in positions no
FDN card reaches through play, so they guard the Known-Best engine
without being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_272.card_impl import Plains
from engine.game_state import GameState
from engine.types import ManaType, Phase, Step
from test_interface import Side, card
from test_interface import create_game as create_position
from test_utils import DeterministicPlayer


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


# ---------------------------------------------------------------------------
# GameState — initial state
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# GameState — player properties
# ---------------------------------------------------------------------------
class TestGameStatePlayerProperties:
    """Tests for active_player, priority_player, non_active_player properties."""




    def test_active_player_changes_after_full_turn(self) -> None:
        """After advancing through all phases, active_player should swap."""
        game = _make_game()
        # Advance through all 13 steps (12 advances to get to CLEANUP, 1 more to wrap)
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


# ---------------------------------------------------------------------------
# GameState — advance_phase full turn sequence
# ---------------------------------------------------------------------------
class TestAdvancePhaseSequence:
    """Tests for advance_phase walking the full MTG turn structure."""


    def test_full_turn_sequence(self) -> None:
        """advance_phase should walk through all 13 phase/step pairs in MTG order.

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
        """Advances 4-9 should walk through the 6 combat steps."""
        game = _make_game()
        for _ in range(4):
            game.advance_phase()
        assert (game.phase, game.step) == (Phase.COMBAT, Step.BEGIN_COMBAT)

        game.advance_phase()
        assert (game.phase, game.step) == (Phase.COMBAT, Step.DECLARE_ATTACKERS)

        game.advance_phase()
        assert (game.phase, game.step) == (Phase.COMBAT, Step.DECLARE_BLOCKERS)

        game.advance_phase()
        assert (game.phase, game.step) == (Phase.COMBAT, Step.FIRST_STRIKE_DAMAGE)

        game.advance_phase()
        assert (game.phase, game.step) == (Phase.COMBAT, Step.COMBAT_DAMAGE)

        game.advance_phase()
        assert (game.phase, game.step) == (Phase.COMBAT, Step.END_COMBAT)

    def test_advance_to_postcombat_main(self) -> None:
        """After combat, advance to POSTCOMBAT_MAIN (step=None)."""
        game = _make_game()
        for _ in range(10):
            game.advance_phase()
        assert game.phase == Phase.POSTCOMBAT_MAIN
        assert game.step is None

    def test_advance_through_ending_phase(self) -> None:
        """Advances 11-12 walk through END and CLEANUP."""
        game = _make_game()
        for _ in range(11):
            game.advance_phase()
        assert (game.phase, game.step) == (Phase.ENDING, Step.END)

        game.advance_phase()
        assert (game.phase, game.step) == (Phase.ENDING, Step.CLEANUP)

    def test_cleanup_wraps_to_next_turn(self) -> None:
        """Advancing from CLEANUP should wrap to BEGINNING/UNTAP of next turn."""
        game = _make_game()
        # Advance through all 13 steps (starts at 0, 13 advances wraps)
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
