"""Tests for SOS 74 — Arnyn, Deathbloom Botanist."""

from __future__ import annotations

import pytest

from cards.sos.sos_74.card_impl import ArnynDeathbloomBotanist
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


class TestArnynProperties:
    """Static card data should match the SOS 74 spec."""

    def test_is_creature(self) -> None:
        card = ArnynDeathbloomBotanist(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        assert ArnynDeathbloomBotanist(owner=None).name == "Arnyn, Deathbloom Botanist"

    def test_mana_cost(self) -> None:
        assert ArnynDeathbloomBotanist(owner=None).mana_cost == ManaCost.parse("{2}{B}")

    def test_power_toughness(self) -> None:
        card = ArnynDeathbloomBotanist(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_deathtouch(self) -> None:
        card = ArnynDeathbloomBotanist(owner=None)
        assert Keyword.DEATHTOUCH in card.keywords

    def test_is_legendary(self) -> None:
        card = ArnynDeathbloomBotanist(owner=None)
        assert Supertype.LEGENDARY in card.supertypes


class TestArnynTriggeredAbility:
    """Whenever a creature you control with power or toughness 1 or less dies,
    target opponent loses 2 life and you gain 2 life."""

    def test_trigger_on_1_1_creature_dying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        arnyn = ArnynDeathbloomBotanist(owner=p1, controller=p1)
        small = Creature(name="Small Creature", owner=p1, controller=p1,
                         base_power=1, base_toughness=1)
        small.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[arnyn, small], life=20)
        set_board_state(game, 1, life=20)

        # Simulate small creature dying
        arnyn.on_creature_dies(game, small, target_opponent=p2)

        assert p2.life == 18  # loses 2
        assert p1.life == 22  # gains 2

    def test_trigger_on_0_toughness_creature(self) -> None:
        """A creature with 0 power and 1 toughness qualifies."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        arnyn = ArnynDeathbloomBotanist(owner=p1, controller=p1)
        wall = Creature(name="Tiny Wall", owner=p1, controller=p1,
                        base_power=0, base_toughness=1)
        wall.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[arnyn, wall], life=20)
        set_board_state(game, 1, life=20)

        arnyn.on_creature_dies(game, wall, target_opponent=p2)

        assert p2.life == 18
        assert p1.life == 22

    def test_no_trigger_on_large_creature_dying(self) -> None:
        """A 2/2 creature dying should NOT trigger the ability."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        arnyn = ArnynDeathbloomBotanist(owner=p1, controller=p1)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[arnyn, bear], life=20)
        set_board_state(game, 1, life=20)

        arnyn.on_creature_dies(game, bear, target_opponent=p2)

        assert p2.life == 20  # no change
        assert p1.life == 20  # no change

    def test_trigger_on_creature_with_1_power_high_toughness(self) -> None:
        """A 1/4 creature qualifies (power is 1 or less)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        arnyn = ArnynDeathbloomBotanist(owner=p1, controller=p1)
        defender = Creature(name="Big Wall", owner=p1, controller=p1,
                            base_power=1, base_toughness=4)
        defender.card_types = {CardType.CREATURE}

        set_board_state(game, 0, battlefield=[arnyn, defender], life=20)
        set_board_state(game, 1, life=20)

        arnyn.on_creature_dies(game, defender, target_opponent=p2)

        assert p2.life == 18
        assert p1.life == 22
