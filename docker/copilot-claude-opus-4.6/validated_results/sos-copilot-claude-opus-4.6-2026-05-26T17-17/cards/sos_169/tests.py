"""Tests for SOS 169 — Zimone's Experiment."""

from __future__ import annotations

import pytest

from cards.sos.sos_169.card_impl import ZimonesExperiment
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestZimonesExperimentProperties:
    """Static card data should match the SOS 169 spec."""

    def test_name(self) -> None:
        card = ZimonesExperiment(owner=None)
        assert card.name == "Zimone's Experiment"

    def test_is_sorcery(self) -> None:
        card = ZimonesExperiment(owner=None)
        assert isinstance(card, Sorcery)

    def test_mana_cost(self) -> None:
        card = ZimonesExperiment(owner=None)
        assert card.mana_cost == ManaCost.parse("{3}{G}")


class TestZimonesExperimentResolution:
    """Look at top 5, reveal up to 2 creature/land, land->BF tapped, creature->hand."""

    def test_reveals_creature_to_hand(self) -> None:
        """A creature card among top 5 can be revealed and goes to hand."""
        game = create_game()
        p1 = game.players[0]
        creature = Creature(name="Forest Bear", owner=p1, base_power=2, base_toughness=2)
        creature.card_types = {CardType.CREATURE}
        # Stack library with creature on top and fillers
        game.get_library(p1).add_top(creature)
        for i in range(4):
            filler = Creature(name=f"Filler{i}", owner=p1, base_power=1, base_toughness=1)
            filler.card_types = {CardType.CREATURE}
            game.get_library(p1).add_top(filler)

        card = ZimonesExperiment(owner=p1, controller=p1)
        # Player chooses to reveal creature
        p1.reveal_choices = [creature]
        card.on_resolve(game)
        hand = game.get_hand(p1)
        assert creature in hand.cards

    def test_reveals_land_to_battlefield_tapped(self) -> None:
        """A land card among top 5 can be revealed and enters tapped."""
        game = create_game()
        p1 = game.players[0]
        from engine.card import CardImpl
        land = CardImpl(name="Forest", owner=p1)
        land.card_types = {CardType.LAND}
        game.get_library(p1).add_top(land)
        for i in range(4):
            filler = Creature(name=f"Filler{i}", owner=p1, base_power=1, base_toughness=1)
            filler.card_types = {CardType.CREATURE}
            game.get_library(p1).add_top(filler)

        card = ZimonesExperiment(owner=p1, controller=p1)
        p1.reveal_choices = [land]
        card.on_resolve(game)
        bf = game.get_battlefield(p1)
        assert land in bf.cards
        assert land.tapped is True

    def test_rest_goes_to_bottom_of_library(self) -> None:
        """Non-revealed cards go to the bottom of the library in random order."""
        game = create_game()
        p1 = game.players[0]
        cards_in_lib = []
        for i in range(5):
            c = Creature(name=f"Card{i}", owner=p1, base_power=1, base_toughness=1)
            c.card_types = {CardType.CREATURE}
            cards_in_lib.append(c)
            game.get_library(p1).add_top(c)

        card = ZimonesExperiment(owner=p1, controller=p1)
        # Reveal only the first card
        p1.reveal_choices = [cards_in_lib[0]]
        card.on_resolve(game)
        # The other 4 should be in the library (bottom)
        lib_cards = game.get_library(p1).cards
        unrevealed = [c for c in cards_in_lib[1:]]
        for c in unrevealed:
            assert c in lib_cards

    def test_can_reveal_zero_cards(self) -> None:
        """Player may choose to reveal nothing."""
        game = create_game()
        p1 = game.players[0]
        for i in range(5):
            c = Creature(name=f"Card{i}", owner=p1, base_power=1, base_toughness=1)
            c.card_types = {CardType.CREATURE}
            game.get_library(p1).add_top(c)

        card = ZimonesExperiment(owner=p1, controller=p1)
        p1.reveal_choices = []
        card.on_resolve(game)
        hand = game.get_hand(p1)
        assert len(hand.cards) == 0

    def test_can_reveal_up_to_two(self) -> None:
        """Player may reveal at most 2 creature/land cards."""
        game = create_game()
        p1 = game.players[0]
        creatures = []
        for i in range(5):
            c = Creature(name=f"Bear{i}", owner=p1, base_power=2, base_toughness=2)
            c.card_types = {CardType.CREATURE}
            creatures.append(c)
            game.get_library(p1).add_top(c)

        card = ZimonesExperiment(owner=p1, controller=p1)
        # Reveal two creatures
        p1.reveal_choices = [creatures[0], creatures[1]]
        card.on_resolve(game)
        hand = game.get_hand(p1)
        assert creatures[0] in hand.cards
        assert creatures[1] in hand.cards

    def test_fewer_than_five_cards_in_library(self) -> None:
        """Works with fewer than 5 cards in library."""
        game = create_game()
        p1 = game.players[0]
        c = Creature(name="LoneBear", owner=p1, base_power=2, base_toughness=2)
        c.card_types = {CardType.CREATURE}
        game.get_library(p1).add_top(c)

        card = ZimonesExperiment(owner=p1, controller=p1)
        p1.reveal_choices = [c]
        card.on_resolve(game)
        hand = game.get_hand(p1)
        assert c in hand.cards
