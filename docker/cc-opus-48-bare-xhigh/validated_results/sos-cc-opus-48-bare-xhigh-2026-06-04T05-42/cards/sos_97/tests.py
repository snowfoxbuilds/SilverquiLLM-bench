"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Instant, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _ral(p, **scripts):
    pw = RalZarekGuestLecturer(owner=p, controller=p)
    return pw


class TestProperties:
    def test_is_planeswalker(self) -> None:
        assert isinstance(RalZarekGuestLecturer(owner=None), Planeswalker)

    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse(
            "{1}{B}{B}"
        )

    def test_starting_loyalty(self) -> None:
        assert RalZarekGuestLecturer(owner=None).starting_loyalty == 3

    def test_legendary_ral(self) -> None:
        pw = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in pw.supertypes
        assert "Ral" in pw.subtypes


class TestLoyaltyAbilities:
    def test_four_abilities_with_costs(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert [a.loyalty_cost for a in abilities] == [1, -1, -2, -7]


class TestPlus1Surveil:
    def test_surveils_top_two_into_graveyard(self) -> None:
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        c1 = Creature(name="Top", base_power=1, base_toughness=1)
        c2 = Creature(name="Second", base_power=1, base_toughness=1)
        for c in (c2, c1):  # c1 ends on top
            c.owner = p1
            c.controller = p1
            p1.zones[Zone.LIBRARY].add(c)
        pw = _ral(p1)
        pw.get_loyalty_abilities()[0].effect(game)
        assert p1.zones[Zone.GRAVEYARD].contains(c1)
        assert p1.zones[Zone.GRAVEYARD].contains(c2)

    def test_surveil_keep_on_top(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        c1 = Creature(name="Top", base_power=1, base_toughness=1)
        c1.owner = p1
        c1.controller = p1
        p1.zones[Zone.LIBRARY].add(c1)
        pw = _ral(p1)
        pw.get_loyalty_abilities()[0].effect(game)
        assert p1.zones[Zone.LIBRARY].contains(c1)


class TestMinus1Discard:
    def test_target_player_discards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        h1 = Instant(name="H1")
        h2 = Instant(name="H2")
        set_board_state(game, 1, hand=[h1, h2])
        pw = _ral(p1)
        pw._resolve_targets = [p2]
        before = len(p2.zones[Zone.HAND])
        pw.get_loyalty_abilities()[1].effect(game)
        assert len(p2.zones[Zone.HAND]) == before - 1


class TestMinus2Reanimate:
    def test_returns_small_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        small = Creature(
            name="Small", mana_cost=ManaCost.parse("{2}"), base_power=2, base_toughness=2
        )
        set_board_state(game, 0, graveyard=[small])
        pw = _ral(p1)
        pw._resolve_target = small
        pw.get_loyalty_abilities()[2].effect(game)
        assert game.get_battlefield(p1).contains(small)
        assert small.controller is p1

    def test_does_not_return_expensive_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        big = Creature(
            name="Big", mana_cost=ManaCost.parse("{5}"), base_power=5, base_toughness=5
        )
        set_board_state(game, 0, graveyard=[big])
        pw = _ral(p1)
        pw._resolve_target = big
        pw.get_loyalty_abilities()[2].effect(game)
        assert not game.get_battlefield(p1).contains(big)
        assert p1.zones[Zone.GRAVEYARD].contains(big)


class TestMinus7SkipTurns:
    def test_skips_turns_equal_to_heads(self) -> None:
        game = create_game()
        p1, p2 = game.players
        pw = _ral(p1)
        pw._forced_heads = 3
        pw._resolve_target = p2
        pw.get_loyalty_abilities()[3].effect(game)
        seat = game.players.index(p2)
        assert game.skip_turns.get(seat, 0) == 3

    def test_zero_heads_no_skip(self) -> None:
        game = create_game()
        p1, p2 = game.players
        pw = _ral(p1)
        pw._forced_heads = 0
        pw._resolve_target = p2
        pw.get_loyalty_abilities()[3].effect(game)
        seat = game.players.index(p2)
        assert game.skip_turns.get(seat, 0) == 0
