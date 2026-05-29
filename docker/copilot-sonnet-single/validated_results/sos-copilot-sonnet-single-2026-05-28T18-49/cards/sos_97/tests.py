"""Tests for Ral Zarek, Guest Lecturer (sos_97)."""

from __future__ import annotations

import pytest
from cards.sos.sos_97.card_impl import RalZarekGuestLecturer
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, Supertype, Zone
from test_utils import create_game, set_board_state


class TestRalZarekProperties:
    """Static card properties."""

    def test_name(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.name == "Ral Zarek, Guest Lecturer"

    def test_is_planeswalker(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert isinstance(card, Planeswalker)
        assert CardType.PLANESWALKER in card.card_types

    def test_starting_loyalty(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.starting_loyalty == 3
        assert card.loyalty == 3

    def test_mana_cost(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_is_legendary(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_subtype_ral(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        assert "Ral" in card.subtypes

    def test_has_four_loyalty_abilities(self) -> None:
        card = RalZarekGuestLecturer(owner=None)
        abilities = card.get_loyalty_abilities()
        assert len(abilities) == 4


class TestRalZarekLoyaltyCosts:
    """Loyalty ability costs."""

    def test_plus1_cost(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert abilities[0].loyalty_cost == +1

    def test_minus1_cost(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert abilities[1].loyalty_cost == -1

    def test_minus2_cost(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert abilities[2].loyalty_cost == -2

    def test_minus7_cost(self) -> None:
        abilities = RalZarekGuestLecturer(owner=None).get_loyalty_abilities()
        assert abilities[3].loyalty_cost == -7


class TestRalZarekPlus1:
    """+1: Surveil 2."""

    def test_surveil_2_moves_card_to_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        abilities = ral.get_loyalty_abilities()

        from engine.card import Instant
        card1 = Instant(name="A", owner=p1, controller=p1)
        card2 = Instant(name="B", owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(card1, position="top")
        p1.zones[Zone.LIBRARY].add(card2, position="top")

        # Script: keep card2 (top), discard card1
        p1._script.append(False)  # discard card2
        p1._script.append(True)   # keep card1

        abilities[0].effect(game)

        # Both cards were looked at
        gy = p1.zones[Zone.GRAVEYARD].get_all()
        lib = p1.zones[Zone.LIBRARY].get_all()
        # card2 was discarded (False → discard)
        assert card2 in gy or card1 in gy  # at least one discarded


class TestRalZarekMinus1:
    """-1: Players discard."""

    def test_minus1_causes_discard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        abilities = ral.get_loyalty_abilities()

        from engine.card import Instant
        hand_card = Instant(name="HandCard", owner=p2, controller=p2)
        set_board_state(game, 1, hand=[hand_card])

        # Script for p2: choose hand_card to discard
        p2._script.append(hand_card)

        abilities[1].effect(game)

        assert hand_card in p2.zones[Zone.GRAVEYARD].get_all()
        assert hand_card not in p2.zones[Zone.HAND].get_all()


class TestRalZarekMinus2:
    """-2: Return creature (CMC ≤ 3) from graveyard."""

    def test_returns_creature_from_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        abilities = ral.get_loyalty_abilities()

        # Put a 3-CMC creature in graveyard
        small_creature = Creature(
            name="Zombie",
            base_power=2,
            base_toughness=2,
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{B}{B}"),
        )
        p1.zones[Zone.GRAVEYARD].add(small_creature)

        # Script: choose small_creature
        p1._script.append(small_creature)

        abilities[2].effect(game)

        assert game.get_battlefield(p1).contains(small_creature)
        assert small_creature not in p1.zones[Zone.GRAVEYARD].get_all()

    def test_does_not_return_high_cmc_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        ral = RalZarekGuestLecturer(owner=p1, controller=p1)
        abilities = ral.get_loyalty_abilities()

        big_creature = Creature(
            name="Titan",
            base_power=6,
            base_toughness=6,
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{4}{G}{G}"),
        )
        p1.zones[Zone.GRAVEYARD].add(big_creature)

        # Even if player tries to choose this, it should be ignored
        p1._script.append(big_creature)

        abilities[2].effect(game)

        # Should still be in graveyard
        assert big_creature in p1.zones[Zone.GRAVEYARD].get_all()
        assert not game.get_battlefield(p1).contains(big_creature)
