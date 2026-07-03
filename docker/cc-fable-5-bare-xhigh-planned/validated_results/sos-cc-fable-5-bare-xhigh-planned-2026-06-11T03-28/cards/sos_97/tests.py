"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    AbilityError,
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature, Planeswalker
from engine.stack import priority_loop
from engine.types import ManaCost, ManaType, Phase, Supertype, Zone
from test_utils import create_game, set_board_state


def _activate(game, player_index, pw, ability_index, targets=None,
              effect_script=None, other_script=None):
    """Activate a printed loyalty ability by index through the engine and
    resolve it via the priority loop.

    *effect_script* / *other_script* are the choices each player makes
    while the ability's effect resolves (after their priority pass).
    """
    player = game.players[player_index]
    other = game.players[1 - player_index]
    ability = pw.get_loyalty_abilities()[ability_index]
    activate_ability(game, player, LoyaltyAbilityInstance(
        source=pw, controller=player,
        loyalty_cost=ability.loyalty_cost,
        effect=ability.effect,
        description=ability.description,
    ), targets=targets)
    player._script.extend(["pass"] + list(effect_script or []))
    other._script.extend(["pass"] + list(other_script or []))
    priority_loop(game)


def _setup(game):
    """Ral on p1's battlefield at sorcery speed for p1."""
    p1 = game.players[0]
    pw = RalZarekGuestLecturer(owner=p1)
    set_board_state(game, 0, battlefield=[pw])
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    clear_loyalty_tracking()
    return p1, pw


class TestRalZarekProperties:
    def test_static_data(self) -> None:
        pw = RalZarekGuestLecturer(owner=None)
        assert isinstance(pw, Planeswalker)
        assert pw.name == "Ral Zarek, Guest Lecturer"
        assert pw.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert pw.starting_loyalty == 3
        assert pw.loyalty == 3
        assert Supertype.LEGENDARY in pw.supertypes
        assert "Ral" in pw.subtypes
        assert len(pw.get_loyalty_abilities()) == 4


class TestRalZarekPlusOne:
    def test_surveil_two(self) -> None:
        game = create_game()
        p1, pw = _setup(game)
        top = Creature(name="Top Card", base_power=1, base_toughness=1)
        second = Creature(name="Second Card", base_power=1, base_toughness=1)
        library = p1.zones[Zone.LIBRARY]
        for c in (top, second):
            c.owner = c.controller = p1
            library.add(c, position="bottom")
        # Bin the top card, keep the second.
        _activate(game, 0, pw, 0, effect_script=[True, False])
        assert pw.loyalty == 4
        assert game.get_graveyard(p1).contains(top)
        assert game.get_library(p1).contains(second)
        assert library.top(1)[0] is second


class TestRalZarekMinusOne:
    def test_each_target_player_discards(self) -> None:
        game = create_game()
        p1, pw = _setup(game)
        p2 = game.players[1]
        mine = Creature(name="Mine", base_power=1, base_toughness=1)
        theirs = Creature(name="Theirs", base_power=1, base_toughness=1)
        set_board_state(game, 0, hand=[mine])  # battlefield (with pw) untouched
        set_board_state(game, 1, hand=[theirs])
        _activate(game, 0, pw, 1, targets=[p1, p2],
                  effect_script=[mine], other_script=[theirs])
        assert pw.loyalty == 2
        assert game.get_graveyard(p1).contains(mine)
        assert game.get_graveyard(p2).contains(theirs)

    def test_zero_targets_is_legal_noop(self) -> None:
        game = create_game()
        p1, pw = _setup(game)
        _activate(game, 0, pw, 1, targets=[])
        assert pw.loyalty == 2


class TestRalZarekMinusTwo:
    def test_reanimates_cheap_creature(self) -> None:
        game = create_game()
        p1, pw = _setup(game)
        bear = Creature(name="Cheap Bear", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}{G}"))  # MV 2
        set_board_state(game, 0, graveyard=[bear])
        _activate(game, 0, pw, 2, targets=[bear])
        assert pw.loyalty == 1
        assert game.get_battlefield(p1).contains(bear)
        assert not game.get_graveyard(p1).contains(bear)

    def test_mv_four_or_more_not_returned(self) -> None:
        game = create_game()
        p1, pw = _setup(game)
        giant = Creature(name="Giant", base_power=5, base_toughness=5,
                         mana_cost=ManaCost.parse("{3}{G}"))  # MV 4
        set_board_state(game, 0, graveyard=[giant])
        _activate(game, 0, pw, 2, targets=[giant])
        assert game.get_graveyard(p1).contains(giant)
        assert not game.get_battlefield(p1).contains(giant)


class TestRalZarekUltimate:
    def test_needs_seven_loyalty(self) -> None:
        game = create_game()
        p1, pw = _setup(game)
        p2 = game.players[1]
        ability = pw.get_loyalty_abilities()[3]
        try:
            activate_ability(game, p1, LoyaltyAbilityInstance(
                source=pw, controller=p1,
                loyalty_cost=ability.loyalty_cost, effect=ability.effect,
            ), targets=[p2])
            raised = False
        except AbilityError:
            raised = True
        assert raised
        assert pw.loyalty == 3

    def test_opponent_skips_x_turns(self) -> None:
        game = create_game()
        p1, pw = _setup(game)
        p2 = game.players[1]
        pw.loyalty = 7
        game.rng.seed(7)  # flips: 1,0,1,0,0 → 2 heads
        _activate(game, 0, pw, 3, targets=[p2])
        assert pw.loyalty == 0
        assert getattr(p2, "skip_turns", 0) == 2

        def _next_turn_active():
            turn = game.turn_number
            while game.turn_number == turn:
                game.advance_phase()
            return game.active_player

        # p2's next two turns are skipped, so p1 takes the next two turns
        # and only then does p2 get one.
        assert _next_turn_active() is p1
        assert _next_turn_active() is p1
        assert _next_turn_active() is p2
        assert p2.skip_turns == 0
        # Normal rotation resumes afterwards.
        assert _next_turn_active() is p1
        assert _next_turn_active() is p2

    def test_zero_heads_skips_nothing(self) -> None:
        game = create_game()
        p1, pw = _setup(game)
        p2 = game.players[1]
        pw.loyalty = 7
        game.rng.seed(15)  # 0 heads
        _activate(game, 0, pw, 3, targets=[p2])
        assert getattr(p2, "skip_turns", 0) == 0
