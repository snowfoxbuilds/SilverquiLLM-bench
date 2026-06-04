"""Tests for SOS 97 — Ral Zarek, Guest Lecturer (planeswalker loyalty abilities)."""

from __future__ import annotations

from collections import deque
from typing import Any

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.abilities import (
    LoyaltyAbilityInstance,
    activate_ability,
    clear_loyalty_tracking,
)
from engine.card import Creature, Instant, Planeswalker
from engine.types import CardType, ManaCost, Phase, Supertype, Zone
from test_utils import create_game, set_board_state, _resolve_top_of_stack


class Filler(Instant):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Filler")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        pass


def _creature(name: str, owner: Any, cost: str) -> Creature:
    c = Creature(name=name, owner=owner, controller=owner,
                 base_power=2, base_toughness=2, mana_cost=ManaCost.parse(cost))
    c.card_types = {CardType.CREATURE}
    return c


def _activate(game: Any, player: Any, pw: RalZarekGuestLecturer, index: int) -> None:
    """Activate the loyalty ability at *index* through the engine and resolve it."""
    clear_loyalty_tracking()
    game.active_player_index = game.players.index(player)
    game.priority_player_index = game.active_player_index
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    ability = pw.get_loyalty_abilities()[index]
    inst = LoyaltyAbilityInstance(
        source=pw, controller=player,
        loyalty_cost=ability.loyalty_cost, effect=ability.effect,
    )
    activate_ability(game, player, inst)
    _resolve_top_of_stack(game)


class TestProperties:
    def test_is_planeswalker(self) -> None:
        c = RalZarekGuestLecturer(owner=None)
        assert isinstance(c, Planeswalker)

    def test_name_cost_loyalty(self) -> None:
        c = RalZarekGuestLecturer(owner=None)
        assert c.name == "Ral Zarek, Guest Lecturer"
        assert c.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert c.starting_loyalty == 3
        assert c.loyalty == 3
        assert Supertype.LEGENDARY in c.supertypes

    def test_four_abilities(self) -> None:
        c = RalZarekGuestLecturer(owner=None)
        costs = [a.loyalty_cost for a in c.get_loyalty_abilities()]
        assert costs == [1, -1, -2, -7]


class TestPlusOneSurveil:
    def test_surveil_two_to_graveyard(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        lib = p1.zones[Zone.LIBRARY]
        for c in [Filler(owner=p1), Filler(owner=p1)]:
            lib.add(c)
        p1._script.extend([True, True])  # send both to graveyard

        _activate(game, p1, ral, 0)

        assert ral.loyalty == 4
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == 2


class TestMinusOneDiscard:
    def test_target_opponent_discards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        opp_card = Filler(owner=p2)
        set_board_state(game, 1, hand=[opp_card])
        my_card = Filler(owner=p1)
        set_board_state(game, 0, battlefield=[ral], hand=[my_card])

        # p1 declines to target itself, targets p2; p2 discards its card.
        p1._script.extend([False, True])
        p2._script.append(opp_card)

        _activate(game, p1, ral, 1)

        assert ral.loyalty == 2
        assert opp_card in p2.zones[Zone.GRAVEYARD].get_all()
        assert my_card in p1.zones[Zone.HAND].get_all()


class TestMinusTwoReanimate:
    def test_returns_low_mv_creature(self) -> None:
        game = create_game()
        p1, _p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        cheap = _creature("Cheap", p1, "{1}{G}")   # mv 2
        pricey = _creature("Pricey", p1, "{5}")     # mv 5
        set_board_state(game, 0, battlefield=[ral], graveyard=[cheap, pricey])
        p1._script.append(cheap)

        _activate(game, p1, ral, 2)

        assert ral.loyalty == 1
        assert cheap in p1.zones[Zone.BATTLEFIELD].get_all()
        assert pricey in p1.zones[Zone.GRAVEYARD].get_all()


class TestMinusSevenSkipTurns:
    def test_heads_count_sets_skip(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[ral])
        ral.loyalty = 7
        p1._coin_flips = deque([True, True, True, False, False])  # 3 heads

        _activate(game, p1, ral, 3)

        assert ral.loyalty == 0
        assert game.skipped_turns[1] == 3

    def test_skip_is_consumed_in_rotation(self) -> None:
        game = create_game()
        p1, p2 = game.players
        # p2 (seat 1) owes one skipped turn.
        game.skipped_turns = {1: 1}
        game.active_player_index = 0
        game._normal_next_index = 1
        # Jump to the last step of p1's turn, then wrap to the next turn.
        from engine.game_state import _TURN_SEQUENCE
        game.phase, game.step = _TURN_SEQUENCE[-1]
        game.advance_phase()

        # p2's turn was skipped; p1 is active again and the skip was consumed.
        assert game.active_player_index == 0
        assert game.skipped_turns.get(1, 0) == 0
