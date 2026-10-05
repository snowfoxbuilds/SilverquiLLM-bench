"""Extra turns (rule 500.7): a player given an extra turn takes it right
after the current one, with its own untap, upkeep and draw steps, and then
the normal turn order resumes.

Temporal Manipulation — the pool's only extra-turn card — gives its caster
an extra turn. With High Fae Trickster in play the player who is not active
casts it too, so either player can be given an extra turn during the other's
turn; when several are waiting, the most recently created is taken first.
"""

from __future__ import annotations

from cards.fdn.fdn_40.card_impl import HighFaeTrickster
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.spg_82.card_impl import TemporalManipulation
from test_interface import Phase, Side, Step, Zone, card, create_game, player
from test_utils import DeterministicPlayer

from engine.game_state import GameState
from silverquillm.table import Table, extra_turn, life, moves, taps

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manipulation(copies: int = 1, *, p1_hand=(), p1_battlefield=()):
    """Turn 1 at player 0's precombat main: player 0 holds ``copies`` Temporal
    Manipulations and five untapped Islands for each; both libraries hold
    Plains to draw."""
    spells = [card(TemporalManipulation) for _ in range(copies)]
    islands = [card(Island) for _ in range(5 * copies)]
    game = create_game(
        Side(hand=spells, battlefield=islands, library=[card(Plains) for _ in range(4)]),
        Side(hand=list(p1_hand), battlefield=list(p1_battlefield), library=[card(Plains) for _ in range(4)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    return Table(game), spells, islands


def _cast_manipulation(t: Table, spell, islands) -> None:
    """Player 0 taps five of ``islands`` and casts ``spell``, which both
    players let resolve."""
    for island in islands[:5]:
        t.act(0, island, then=[taps(island)])
    t.act(0, spell, then=[moves(spell, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), extra_turn(0)])


def _both(p0_copies: int = 0, p1_copies: int = 0, *, active: int = 0):
    """Precombat main of the turn of ``active``: each player holds that many
    Temporal Manipulations with five untapped Islands for each, player 1 has
    High Fae Trickster so they may cast theirs during player 0's turn, and
    both libraries hold Plains to draw."""
    hands = [[card(TemporalManipulation) for _ in range(n)] for n in (p0_copies, p1_copies)]
    islands = [[card(Island) for _ in range(5 * n)] for n in (p0_copies, p1_copies)]
    trickster = [card(HighFaeTrickster)] if p1_copies else []
    game = create_game(
        Side(hand=hands[0], battlefield=islands[0], library=[card(Plains) for _ in range(6)]),
        Side(hand=hands[1], battlefield=trickster + islands[1], library=[card(Plains) for _ in range(6)]),
        start=(Phase.PRECOMBAT_MAIN, active),
    )
    return Table(game), hands, islands


def _cast(t: Table, seat: int, spell, islands) -> None:
    """``seat`` taps five of ``islands`` and casts ``spell``, which both
    players let resolve; ``seat`` will take an extra turn after this one."""
    for island in islands[:5]:
        t.act(seat, island, then=[taps(island)])
    t.act(seat, spell, then=[moves(spell, Zone.STACK)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[moves(spell, Zone.GRAVEYARD), extra_turn(seat)])


def _turns(t: Table, count: int) -> list[int]:
    """Who is active in each of the next ``count`` turns' upkeeps."""
    actives = []
    for _ in range(count):
        t.pass_to(Step.UPKEEP)
        actives.append(t.expected.active)
    final = t.run()
    assert final.active == actives[-1]
    return actives


def _make_game() -> GameState:
    """Create a minimal 2-player GameState for extra-turn tests."""
    p0 = DeterministicPlayer("Alice")
    p1 = DeterministicPlayer("Bob")
    for p in (p0, p1):
        p.life = 20
    return GameState([p0, p1])


# ---------------------------------------------------------------------------
# Attribute initialisation
# ---------------------------------------------------------------------------


class TestExtraTurnsAttribute:
    """GameState.extra_turns should be an empty list by default."""

    def test_extra_turns_initialized_empty(self):
        game = _make_game()
        assert game.extra_turns == []

    def test_extra_turns_is_mutable_list(self):
        game = _make_game()
        assert isinstance(game.extra_turns, list)
        # Should be appendable like a normal list
        game.extra_turns.append(0)
        assert len(game.extra_turns) == 1


# ---------------------------------------------------------------------------
# Single extra turn granted
# ---------------------------------------------------------------------------


class TestExtraTurnGranted:
    """A player given an extra turn takes the next turn."""

    def test_active_player_gets_consecutive_turn(self):
        t, (spell,), islands = _manipulation()
        _cast_manipulation(t, spell, islands)
        t.pass_to(Step.UPKEEP)
        final = t.run()
        assert final.active == 0

    def test_opponent_gets_extra_turn(self):
        """Player 1 casts Temporal Manipulation during player 0's turn: the
        next turn is player 1's, and player 1 draws in it."""
        t, (_, (spell,)), (_, islands) = _both(p1_copies=1)
        t.pass_(0)
        _cast(t, 1, spell, islands)
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        final = t.run()
        assert final.active == 1
        assert len(final.players[1].hand) == 1

    def test_opponent_takes_extra_turn_on_their_own_turn(self):
        """Player 1 casts Temporal Manipulation on their own turn and takes
        the next turn too; then player 0's turn follows."""
        t, (_, (spell,)), (_, islands) = _both(p1_copies=1, active=1)
        _cast(t, 1, spell, islands)
        assert _turns(t, 2) == [1, 0]

    def test_turn_number_increments_on_extra_turn(self):
        """The extra turn is a new turn, so player 0 draws in it — only the
        first turn's draw is skipped — and the turn after it is player 1's."""
        t, (spell,), islands = _manipulation()
        _cast_manipulation(t, spell, islands)
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        t.pass_to(Phase.PRECOMBAT_MAIN, 1)
        final = t.run()
        assert len(final.players[0].hand) == len(final.players[1].hand) == 1


# ---------------------------------------------------------------------------
# Normal turn order resumes after extra turn
# ---------------------------------------------------------------------------


class TestNormalOrderResumes:
    """After extra turns are taken, the normal alternation resumes."""

    def test_resumes_to_opponent_after_self_extra_turn(self):
        t, (spell,), islands = _manipulation()
        _cast_manipulation(t, spell, islands)
        t.pass_to(Step.UPKEEP, 0)
        t.pass_to(Step.UPKEEP)
        final = t.run()
        assert final.active == 1

    def test_resumes_after_opponent_extra_turn(self):
        """After player 1's extra turn, taken after player 0's turn, the
        normal turn order resumes from player 0's turn: player 1 again, then
        player 0."""
        t, (_, (spell,)), (_, islands) = _both(p1_copies=1)
        t.pass_(0)
        _cast(t, 1, spell, islands)
        assert _turns(t, 3) == [1, 1, 0]

    def test_empty_queue_normal_alternation(self):
        """With no extra turn, turns alternate."""
        t, _, _ = _manipulation()
        t.pass_to(Step.UPKEEP)
        t.pass_to(Step.UPKEEP)
        final = t.run()
        assert final.active == 0


# ---------------------------------------------------------------------------
# Multiple extra turns
# ---------------------------------------------------------------------------


class TestMultipleExtraTurns:
    """Several extra turns are each taken, the most recently created first
    (rule 500.7)."""

    def test_two_extra_turns_same_player(self):
        t, (first, second), islands = _manipulation(copies=2)
        _cast_manipulation(t, first, islands[:5])
        _cast_manipulation(t, second, islands[5:])
        t.pass_to(Step.UPKEEP, 0)
        t.pass_to(Step.UPKEEP, 0)
        t.pass_to(Step.UPKEEP)
        final = t.run()
        assert final.active == 1

    def test_most_recent_extra_turn_first_different_players(self):
        """Player 0's Temporal Manipulation resolves, then player 1's: player
        1's extra turn, created last, comes first, then player 0's."""
        t, ((mine,), (theirs,)), (my_islands, their_islands) = _both(p0_copies=1, p1_copies=1)
        _cast(t, 0, mine, my_islands)
        t.pass_(0)
        _cast(t, 1, theirs, their_islands)
        assert _turns(t, 2) == [1, 0]

    def test_response_resolves_first_so_its_extra_turn_comes_last(self):
        """Player 1 casts Temporal Manipulation in response to player 0's:
        player 1's resolves first, so player 0's extra turn is the most
        recent and is taken first, then player 1's."""
        t, ((mine,), (theirs,)), (my_islands, their_islands) = _both(p0_copies=1, p1_copies=1)
        for island in my_islands:
            t.act(0, island, then=[taps(island)])
        t.act(0, mine, then=[moves(mine, Zone.STACK)])
        t.pass_(0)
        for island in their_islands:
            t.act(1, island, then=[taps(island)])
        t.act(1, theirs, then=[moves(theirs, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(theirs, Zone.GRAVEYARD), extra_turn(1)])
        t.pass_(0)
        t.pass_(1, then=[moves(mine, Zone.GRAVEYARD), extra_turn(0)])
        assert _turns(t, 2) == [0, 1]

    def test_three_extras_most_recent_first(self):
        """Player 0 resolves two Temporal Manipulations, then player 1 one:
        player 1's extra turn comes first, then player 0's two."""
        t, ((first, second), (theirs,)), (my_islands, their_islands) = _both(p0_copies=2, p1_copies=1)
        _cast(t, 0, first, my_islands[:5])
        _cast(t, 0, second, my_islands[5:])
        t.pass_(0)
        _cast(t, 1, theirs, their_islands)
        assert _turns(t, 3) == [1, 0, 0]

    def test_normal_order_resumes_after_all_extras_consumed(self):
        """After both players' extra turns, the normal turn order resumes
        from player 0's turn, the last normal one: player 1 is next."""
        t, ((mine,), (theirs,)), (my_islands, their_islands) = _both(p0_copies=1, p1_copies=1)
        _cast(t, 0, mine, my_islands)
        t.pass_(0)
        _cast(t, 1, theirs, their_islands)
        assert _turns(t, 4) == [1, 0, 1, 0]


# ---------------------------------------------------------------------------
# Extra turn during an extra turn
# ---------------------------------------------------------------------------


class TestExtraTurnDuringExtraTurn:
    """An extra turn given during an extra turn is taken too."""

    def test_queue_extra_during_extra(self):
        t, (first, second), islands = _manipulation(copies=2)
        _cast_manipulation(t, first, islands)
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        _cast_manipulation(t, second, islands)
        t.pass_to(Step.UPKEEP, 0)
        t.pass_to(Step.UPKEEP)
        final = t.run()
        assert final.active == 1

    def test_queue_opponent_extra_during_own_extra(self):
        """Player 0 takes an extra turn, and during it player 1 casts Temporal
        Manipulation: player 1's extra turn follows, then the normal order
        resumes from player 0's normal turn, so player 1 again."""
        t, ((mine,), (theirs,)), (my_islands, their_islands) = _both(p0_copies=1, p1_copies=1)
        _cast(t, 0, mine, my_islands)
        t.pass_to(Phase.PRECOMBAT_MAIN, 0)
        t.pass_(0)
        _cast(t, 1, theirs, their_islands)
        assert _turns(t, 3) == [1, 1, 0]


# ---------------------------------------------------------------------------
# Priority and phase reset on extra turn
# ---------------------------------------------------------------------------


class TestPriorityAndPhaseReset:
    """An extra turn starts at its beginning, with priority to its player."""

    def test_priority_set_to_active_player_on_extra_turn(self):
        """Player 1 acts last in player 0's end step; in the extra turn's
        upkeep player 0 is asked first."""
        mountain, bolt = card(Mountain), card(BurstLightning)
        t, (spell,), islands = _manipulation(p1_hand=[bolt], p1_battlefield=[mountain])
        _cast_manipulation(t, spell, islands)
        t.pass_to(Step.END, 0)
        t.pass_(0)
        t.act(1, mountain, then=[taps(mountain)])
        t.act(1, bolt, choices=[player(0)], then=[moves(bolt, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(bolt, Zone.GRAVEYARD), life(0, 18)])
        t.pass_(0)
        t.pass_(1)
        final = t.run()
        assert (final.step, final.active, final.asked) == (Step.UPKEEP, 0, 0)

    def test_phase_resets_to_beginning_on_extra_turn(self):
        """The extra turn begins with its untap step: the Islands tapped for
        Temporal Manipulation untap."""
        t, (spell,), islands = _manipulation()
        _cast_manipulation(t, spell, islands)
        t.pass_to(Step.UPKEEP)
        final = t.run()
        assert not any(seen.tapped for seen in final.players[0].battlefield)
