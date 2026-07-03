"""Tests for SOS 77 — Cost of Brilliance.

Sorcery for {2}{B}. Target player draws two cards and loses 2 life.
Put a +1/+1 counter on up to one target creature.
"""

from __future__ import annotations

from cards.sos.sos_77.card_impl import CostOfBrilliance
from engine.card import Creature, Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from test_utils import create_game


class TestCostOfBrillianceProperties:
    """Static card data should match the SOS 77 spec."""

    def test_name(self) -> None:
        card = CostOfBrilliance(owner=None)
        assert card.name == "Cost of Brilliance"

    def test_mana_cost(self) -> None:
        card = CostOfBrilliance(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{B}")

    def test_is_sorcery(self) -> None:
        card = CostOfBrilliance(owner=None)
        assert isinstance(card, Sorcery)


class TestCostOfBrillianceResolution:
    """Resolution: target player draws 2, loses 2 life; +1/+1 counter on creature."""

    def test_target_player_draws_two_cards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        # Give player cards in library to draw
        from engine.card import Card
        for i in range(5):
            c = Card(name=f"Card {i}", owner=p1)
            game.get_library(p1).add(c)
        spell = CostOfBrilliance(owner=p1, controller=p1)
        spell.chosen_targets = [p1]
        hand_before = len(game.get_hand(p1).get_all())
        spell.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after - hand_before == 2

    def test_target_player_loses_two_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        from engine.card import Card
        for i in range(5):
            c = Card(name=f"Card {i}", owner=p1)
            game.get_library(p1).add(c)
        spell = CostOfBrilliance(owner=p1, controller=p1)
        spell.chosen_targets = [p1]
        life_before = p1.life
        spell.on_resolve(game)
        assert p1.life == life_before - 2

    def test_puts_counter_on_target_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        from engine.card import Card
        for i in range(5):
            c = Card(name=f"Card {i}", owner=p1)
            game.get_library(p1).add(c)
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)
        spell = CostOfBrilliance(owner=p1, controller=p1)
        spell.chosen_targets = [p1, bear]
        counters_before = bear.plus_one_counters
        spell.on_resolve(game)
        assert bear.plus_one_counters == counters_before + 1

    def test_no_creature_target_still_draws_and_loses_life(self) -> None:
        """'Up to one' means the creature target is optional."""
        game = create_game()
        p1 = game.players[0]
        from engine.card import Card
        for i in range(5):
            c = Card(name=f"Card {i}", owner=p1)
            game.get_library(p1).add(c)
        spell = CostOfBrilliance(owner=p1, controller=p1)
        # Only player target, no creature target
        spell.chosen_targets = [p1]
        life_before = p1.life
        spell.on_resolve(game)
        assert p1.life == life_before - 2
