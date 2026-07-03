"""Tests for SOS 208 — Paradox Surveyor.

Creature — Elf Druid (3/3) {G}{G/U}{U}
- Reach
- When this creature enters, look at the top five cards of your library.
  You may reveal a land card or a card with {X} in its mana cost from among
  them and put it into your hand. Put the rest on the bottom of your library
  in a random order.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_208.card_impl import ParadoxSurveyor
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestParadoxSurveyorProperties:
    """Static card properties match the spec."""

    def test_name(self) -> None:
        card = ParadoxSurveyor(owner=None)
        assert card.name == "Paradox Surveyor"

    def test_mana_cost(self) -> None:
        card = ParadoxSurveyor(owner=None)
        assert card.mana_cost == ManaCost.parse("{G}{G/U}{U}")

    def test_power_toughness(self) -> None:
        card = ParadoxSurveyor(owner=None)
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_is_creature(self) -> None:
        card = ParadoxSurveyor(owner=None)
        assert isinstance(card, Creature)

    def test_has_reach(self) -> None:
        card = ParadoxSurveyor(owner=None)
        assert Keyword.REACH in card.keywords


class TestParadoxSurveyorETB:
    """ETB: look at top 5, may reveal a land or {X} card, put it into hand."""

    def test_land_card_can_be_put_into_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ParadoxSurveyor(owner=p1, controller=p1)

        # Set up library with a land in top 5
        land = Creature(name="Forest", owner=p1, controller=p1, base_power=0, base_toughness=0)
        land.card_types = {CardType.LAND}
        filler1 = Instant(name="Filler1", owner=p1, controller=p1)
        filler1.card_types = {CardType.INSTANT}
        filler2 = Instant(name="Filler2", owner=p1, controller=p1)
        filler2.card_types = {CardType.INSTANT}
        filler3 = Instant(name="Filler3", owner=p1, controller=p1)
        filler3.card_types = {CardType.INSTANT}
        filler4 = Instant(name="Filler4", owner=p1, controller=p1)
        filler4.card_types = {CardType.INSTANT}

        library = game.get_library(p1)
        for c in [land, filler1, filler2, filler3, filler4]:
            library.add(c)

        card.on_enter_battlefield(game, choice=land)

        hand_cards = game.get_hand(p1).get_all()
        assert land in hand_cards

    def test_x_cost_card_can_be_put_into_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ParadoxSurveyor(owner=p1, controller=p1)

        # Card with {X} in mana cost
        x_spell = Instant(name="Fireball", owner=p1, controller=p1)
        x_spell.mana_cost = ManaCost.parse("{X}{R}")
        x_spell.card_types = {CardType.INSTANT}

        filler1 = Instant(name="Filler1", owner=p1, controller=p1)
        filler1.card_types = {CardType.INSTANT}
        filler2 = Instant(name="Filler2", owner=p1, controller=p1)
        filler2.card_types = {CardType.INSTANT}
        filler3 = Instant(name="Filler3", owner=p1, controller=p1)
        filler3.card_types = {CardType.INSTANT}
        filler4 = Instant(name="Filler4", owner=p1, controller=p1)
        filler4.card_types = {CardType.INSTANT}

        library = game.get_library(p1)
        for c in [x_spell, filler1, filler2, filler3, filler4]:
            library.add(c)

        card.on_enter_battlefield(game, choice=x_spell)

        hand_cards = game.get_hand(p1).get_all()
        assert x_spell in hand_cards

    def test_may_choose_not_to_take_a_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ParadoxSurveyor(owner=p1, controller=p1)

        land = Creature(name="Forest", owner=p1, controller=p1, base_power=0, base_toughness=0)
        land.card_types = {CardType.LAND}
        filler1 = Instant(name="Filler1", owner=p1, controller=p1)
        filler1.card_types = {CardType.INSTANT}

        library = game.get_library(p1)
        for c in [land, filler1]:
            library.add(c)

        # Choose nothing
        card.on_enter_battlefield(game, choice=None)

        hand_cards = game.get_hand(p1).get_all()
        assert land not in hand_cards

    def test_non_land_non_x_card_cannot_be_chosen(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ParadoxSurveyor(owner=p1, controller=p1)

        regular_spell = Instant(name="Cancel", owner=p1, controller=p1)
        regular_spell.mana_cost = ManaCost.parse("{1}{U}{U}")
        regular_spell.card_types = {CardType.INSTANT}

        library = game.get_library(p1)
        for i in range(5):
            filler = Instant(name=f"Filler{i}", owner=p1, controller=p1)
            filler.mana_cost = ManaCost.parse("{1}{U}")
            filler.card_types = {CardType.INSTANT}
            library.add(filler)

        # Cannot choose a non-land, non-X spell
        with pytest.raises(Exception):
            card.on_enter_battlefield(game, choice=regular_spell)

    def test_remaining_cards_go_to_bottom_of_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ParadoxSurveyor(owner=p1, controller=p1)

        land = Creature(name="Forest", owner=p1, controller=p1, base_power=0, base_toughness=0)
        land.card_types = {CardType.LAND}
        fillers = []
        for i in range(4):
            f = Instant(name=f"Filler{i}", owner=p1, controller=p1)
            f.card_types = {CardType.INSTANT}
            fillers.append(f)

        library = game.get_library(p1)
        for c in [land] + fillers:
            library.add(c)

        card.on_enter_battlefield(game, choice=land)

        # Land goes to hand, 4 fillers remain in library
        lib_cards = game.get_library(p1).get_all()
        assert land not in lib_cards
        for f in fillers:
            assert f in lib_cards
