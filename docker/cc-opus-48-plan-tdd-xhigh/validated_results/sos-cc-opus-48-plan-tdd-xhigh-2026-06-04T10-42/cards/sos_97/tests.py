"""Tests for SOS 97 — Ral Zarek, Guest Lecturer (planeswalker loyalty abilities)."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import CardImpl, Creature, Planeswalker
from engine.types import ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _ability(ral: Any, loyalty_cost: int) -> Any:
    for ab in ral.get_loyalty_abilities():
        if ab.loyalty_cost == loyalty_cost:
            return ab
    raise AssertionError(f"No loyalty ability with cost {loyalty_cost}")


def _card(name: str, owner: Any) -> CardImpl:
    c = CardImpl(name=name)
    c.owner = owner
    c.controller = owner
    return c


def _creature(name: str, cost: str, owner: Any) -> Creature:
    c = Creature(name=name, mana_cost=ManaCost.parse(cost), base_power=2, base_toughness=2)
    c.owner = owner
    c.controller = owner
    return c


class TestRalProperties:
    def test_is_planeswalker(self) -> None:
        assert isinstance(RalZarekGuestLecturer(owner=None), Planeswalker)

    def test_name(self) -> None:
        assert (
            RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"
        )

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse(
            "{1}{B}{B}"
        )

    def test_loyalty(self) -> None:
        c = RalZarekGuestLecturer(owner=None)
        assert c.starting_loyalty == 3
        assert c.loyalty == 3

    def test_legendary_ral(self) -> None:
        c = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in c.supertypes
        assert "Ral" in c.subtypes

    def test_has_four_abilities(self) -> None:
        costs = sorted(ab.loyalty_cost for ab in RalZarekGuestLecturer(owner=None).get_loyalty_abilities())
        assert costs == [-7, -2, -1, 1]


class TestRalPlusOne:
    def test_surveil_2_bins_top_keeps_second(self) -> None:
        game = create_game()
        p0, _ = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])
        bottom = _card("Bottom", p0)
        top = _card("Top", p0)
        p0.zones[Zone.LIBRARY].add(bottom)
        p0.zones[Zone.LIBRARY].add(top)  # last added == top of library

        # Surveil processes top-first: bin the top card, keep the next.
        p0._script.extend([False, True])
        _ability(ral, 1).effect(game)

        assert game.get_graveyard(p0).contains(top)
        assert p0.zones[Zone.LIBRARY].contains(bottom)
        assert not p0.zones[Zone.LIBRARY].contains(top)


class TestRalMinusOne:
    def test_target_opponent_discards(self) -> None:
        game = create_game()
        p0, p1 = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])
        victim = _card("Victim", p1)
        set_board_state(game, 1, hand=[victim])

        # Controller targets only the opponent; opponent then discards Victim.
        p0._script.extend([False, True])  # don't target self, target opponent
        p1._script.append(victim)
        _ability(ral, -1).effect(game)

        assert game.get_graveyard(p1).contains(victim)
        assert not game.get_hand(p1).contains(victim)


class TestRalMinusTwo:
    def test_returns_small_creature_from_graveyard(self) -> None:
        game = create_game()
        p0, _ = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        bear = _creature("Bear", "{1}{G}", p0)  # mana value 2
        giant = _creature("Giant", "{5}", p0)  # mana value 5 — ineligible
        set_board_state(game, 0, battlefield=[ral], graveyard=[bear, giant])

        p0._script.append(bear)
        _ability(ral, -2).effect(game)

        assert game.get_battlefield(p0).contains(bear)
        assert not game.get_graveyard(p0).contains(bear)
        assert game.get_graveyard(p0).contains(giant)  # too expensive, stayed

    def test_no_eligible_creature_does_nothing(self) -> None:
        game = create_game()
        p0, _ = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        giant = _creature("Giant", "{5}", p0)
        set_board_state(game, 0, battlefield=[ral], graveyard=[giant])

        _ability(ral, -2).effect(game)  # no choice requested

        assert game.get_graveyard(p0).contains(giant)
        assert not game.get_battlefield(p0).contains(giant)


class TestRalMinusSeven:
    def test_skips_opponent_turns_equal_to_heads(self) -> None:
        game = create_game()
        p0, p1 = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])

        # 3 heads out of 5, then choose the opponent.
        p0._script.extend([True, True, True, False, False, p1])
        _ability(ral, -7).effect(game)

        assert game.skipped_turns.get(1) == 3

    def test_zero_heads_skips_nothing(self) -> None:
        game = create_game()
        p0, p1 = game.players
        ral = RalZarekGuestLecturer(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[ral])

        p0._script.extend([False, False, False, False, False, p1])
        _ability(ral, -7).effect(game)

        assert game.skipped_turns == {}
