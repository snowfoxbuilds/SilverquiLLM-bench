"""Tests for sos_97 — Ral Zarek, Guest Lecturer (Planeswalker)."""

from __future__ import annotations

from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, Planeswalker
from engine.types import ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestRalZarekProperties:
    def test_name(self) -> None:
        assert RalZarekGuestLecturer(owner=None).name == "Ral Zarek, Guest Lecturer"

    def test_mana_cost(self) -> None:
        assert RalZarekGuestLecturer(owner=None).mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_planeswalker(self) -> None:
        assert isinstance(RalZarekGuestLecturer(owner=None), Planeswalker)

    def test_starting_loyalty(self) -> None:
        assert RalZarekGuestLecturer(owner=None).loyalty == 3

    def test_is_legendary(self) -> None:
        assert Supertype.LEGENDARY in RalZarekGuestLecturer(owner=None).supertypes

    def test_has_ral_subtype(self) -> None:
        assert "Ral" in RalZarekGuestLecturer(owner=None).subtypes

    def test_has_loyalty_abilities(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert len(abilities) == 4

    def test_loyalty_costs(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        costs = sorted(a.loyalty_cost for a in abilities)
        assert costs == [-7, -2, -1, 1]


class TestRalZarekSurveil:
    """+1: Surveil 2."""

    def test_plus1_surveils_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        # Put 3 cards in library
        for i in range(3):
            c = Creature(name=f"Lib{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        initial_lib = len(p1.zones[Zone.LIBRARY].get_all())
        initial_gy = len(p1.zones[Zone.GRAVEYARD].get_all())

        # Script: put both cards in graveyard
        p1._script.appendleft(True)
        p1._script.appendleft(True)

        abilities = ral.get_loyalty_abilities()
        plus1 = next(a for a in abilities if a.loyalty_cost == 1)
        plus1.effect(game)

        # Two cards moved to graveyard
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) == initial_gy + 2
        assert len(p1.zones[Zone.LIBRARY].get_all()) == initial_lib - 2

    def test_plus1_keeps_cards_on_library_when_declined(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        for i in range(3):
            c = Creature(name=f"Lib{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)

        initial_lib = len(p1.zones[Zone.LIBRARY].get_all())

        # Script: keep both cards (don't put in GY)
        p1._script.appendleft(False)
        p1._script.appendleft(False)

        abilities = ral.get_loyalty_abilities()
        plus1 = next(a for a in abilities if a.loyalty_cost == 1)
        plus1.effect(game)

        assert len(p1.zones[Zone.LIBRARY].get_all()) == initial_lib


class TestRalZarekDiscard:
    """-1: Any number of target players each discard a card."""

    def test_minus1_player_discards(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = [p2]
        # Put a card in p2's hand
        card_in_hand = Creature(name="Hand Card", owner=p2)
        p2.zones[Zone.HAND].add(card_in_hand)
        # Script: p2 discards card_in_hand
        p2._script.appendleft(card_in_hand)

        abilities = ral.get_loyalty_abilities()
        minus1 = next(a for a in abilities if a.loyalty_cost == -1)
        minus1.effect(game)

        gy = p2.zones[Zone.GRAVEYARD]
        assert gy.contains(card_in_hand)

    def test_minus1_no_targets_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = []

        abilities = ral.get_loyalty_abilities()
        minus1 = next(a for a in abilities if a.loyalty_cost == -1)
        minus1.effect(game)  # should not raise


class TestRalZarekReanimate:
    """-2: Return target creature card with MV 3 or less from GY to battlefield."""

    def test_minus2_reanimates_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        bear = Creature(
            name="Bear", base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{1}{G}"),
            owner=p1, controller=p1,
        )
        p1.zones[Zone.GRAVEYARD].add(bear)
        ral.chosen_targets = [bear]

        abilities = ral.get_loyalty_abilities()
        minus2 = next(a for a in abilities if a.loyalty_cost == -2)
        minus2.effect(game)

        bf = game.get_battlefield(p1).get_all()
        assert bear in bf
        assert not p1.zones[Zone.GRAVEYARD].contains(bear)

    def test_minus2_does_not_reanimate_high_mv(self) -> None:
        """Creature with MV > 3 should not be returned."""
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        big = Creature(
            name="Titan", base_power=6, base_toughness=6,
            mana_cost=ManaCost.parse("{4}{G}{G}"),
            owner=p1, controller=p1,
        )
        p1.zones[Zone.GRAVEYARD].add(big)
        ral.chosen_targets = [big]

        abilities = ral.get_loyalty_abilities()
        minus2 = next(a for a in abilities if a.loyalty_cost == -2)
        minus2.effect(game)

        # Should still be in graveyard
        assert p1.zones[Zone.GRAVEYARD].contains(big)


class TestRalZarekUltimate:
    """-7: Flip 5 coins. Opponent skips their next X turns (X = heads)."""

    def test_minus7_all_heads_skips_five_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = [p2]

        # Script: 5 coin flips, all heads (True)
        for _ in range(5):
            p1._script.appendleft(True)

        abilities = ral.get_loyalty_abilities()
        minus7 = next(a for a in abilities if a.loyalty_cost == -7)
        minus7.effect(game)

        skips = getattr(p2, "turns_to_skip", 0)
        assert skips == 5

    def test_minus7_all_tails_skips_zero_turns(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        ral.chosen_targets = [p2]

        # Script: all tails
        for _ in range(5):
            p1._script.appendleft(False)

        abilities = ral.get_loyalty_abilities()
        minus7 = next(a for a in abilities if a.loyalty_cost == -7)
        minus7.effect(game)

        skips = getattr(p2, "turns_to_skip", 0)
        assert skips == 0
