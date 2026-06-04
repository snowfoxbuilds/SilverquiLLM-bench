"""Tests for SOS 97 — Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Planeswalker, Sorcery
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


def _bear(name: str, cost: str = "{1}{G}") -> Creature:
    c = Creature(name=name, base_power=2, base_toughness=2, mana_cost=ManaCost.parse(cost))
    c.card_types = {CardType.CREATURE}
    return c


class TestProperties:
    def test_basics(self) -> None:
        c = RalZarekGuestLecturer(owner=None)
        assert c.name == "Ral Zarek, Guest Lecturer"
        assert c.mana_cost == ManaCost.parse("{1}{B}{B}")
        assert isinstance(c, Planeswalker)
        assert c.starting_loyalty == 3
        assert Supertype.LEGENDARY in c.supertypes
        assert "Ral" in c.subtypes


class TestSurveil:
    def test_plus1_puts_cards_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        a = Sorcery(name="A", mana_cost=ManaCost.parse("{1}"))
        b = Sorcery(name="B", mana_cost=ManaCost.parse("{1}"))
        p1.zones[Zone.LIBRARY].add(a)
        p1.zones[Zone.LIBRARY].add(b)  # b is on top
        plus1 = ral.get_loyalty_abilities()[0]
        assert plus1.loyalty_cost == 1
        p1._script.extend([True, True])  # bin both
        plus1.effect(game)
        assert a in p1.zones[Zone.GRAVEYARD].get_all()
        assert b in p1.zones[Zone.GRAVEYARD].get_all()


class TestDiscard:
    def test_minus1_targets_chosen_players(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        card_p1 = Sorcery(name="Mine", mana_cost=ManaCost.parse("{1}"))
        card_p2 = Sorcery(name="Theirs", mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, hand=[card_p1])
        set_board_state(game, 1, hand=[card_p2])
        minus1 = ral.get_loyalty_abilities()[1]
        assert minus1.loyalty_cost == -1
        # Controller declines to target self, targets opponent.
        p1._script.extend([False, True])
        p2._script.extend([card_p2])
        minus1.effect(game)
        assert card_p2 in p2.zones[Zone.GRAVEYARD].get_all()
        assert card_p1 in p1.zones[Zone.HAND].get_all()


class TestReanimate:
    def test_minus2_returns_cheap_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        bear = _bear("Bear")  # mana value 2 <= 3
        set_board_state(game, 0, graveyard=[bear])
        minus2 = ral.get_loyalty_abilities()[2]
        assert minus2.loyalty_cost == -2
        p1._script.extend([bear])
        minus2.effect(game)
        assert bear in game.get_battlefield(p1).get_all()
        assert bear not in p1.zones[Zone.GRAVEYARD].get_all()
        assert bear.summoning_sick is True

    def test_minus2_excludes_expensive(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        big = _bear("Big", cost="{4}{G}")  # mana value 5 > 3
        set_board_state(game, 0, graveyard=[big])
        minus2 = ral.get_loyalty_abilities()[2]
        minus2.effect(game)
        # No legal target — stays in the graveyard.
        assert big in p1.zones[Zone.GRAVEYARD].get_all()


class TestSkipTurns:
    def test_minus7_skips_by_heads(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        game.coin_flip_results = [True, True, False, True, False]  # 3 heads
        minus7 = ral.get_loyalty_abilities()[3]
        assert minus7.loyalty_cost == -7
        minus7.effect(game)
        idx = game.players.index(p2)
        assert game.skip_turns.get(idx) == 3

    def test_minus7_no_heads_no_skip(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        game.coin_flip_results = [False, False, False, False, False]
        minus7 = ral.get_loyalty_abilities()[3]
        minus7.effect(game)
        idx = game.players.index(p2)
        assert game.skip_turns.get(idx, 0) == 0
