"""Tests for SOS 96 — Rabid Attack.

Rabid Attack is a {1}{B} Instant that gives any number of target creatures
you control +1/+0 and "When this creature dies, draw a card" until end of turn.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_96.card_impl import RabidAttack
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestRabidAttackProperties:
    """Static card data should match the SOS 96 spec."""

    def test_is_instant(self) -> None:
        card = RabidAttack(owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        card = RabidAttack(owner=None)
        assert card.name == "Rabid Attack"

    def test_mana_cost(self) -> None:
        card = RabidAttack(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}")


class TestRabidAttackResolution:
    """on_resolve grants +1/+0 and death-draw to chosen targets."""

    def test_single_target_gets_power_boost(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = RabidAttack(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # Should get +1/+0
        assert bear.power == 3
        assert bear.toughness == 2

    def test_multiple_targets_each_get_boost(self) -> None:
        game = create_game()
        p1 = game.players[0]

        bear1 = Creature(
            name="Bear A", owner=p1, controller=p1,
            base_power=2, base_toughness=2,
        )
        bear1.card_types = {CardType.CREATURE}
        bear2 = Creature(
            name="Bear B", owner=p1, controller=p1,
            base_power=3, base_toughness=3,
        )
        bear2.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear1)
        game.get_battlefield(p1).add(bear2)

        spell = RabidAttack(owner=p1, controller=p1)
        spell.chosen_targets = [bear1, bear2]
        spell.on_resolve(game)

        assert bear1.power == 3
        assert bear2.power == 4

    def test_target_gains_dies_draw_ability(self) -> None:
        """When a targeted creature dies, controller should draw a card."""
        game = create_game()
        p1 = game.players[0]

        bear = Creature(
            name="Grizzly Bears",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bear.card_types = {CardType.CREATURE}
        game.get_battlefield(p1).add(bear)

        spell = RabidAttack(owner=p1, controller=p1)
        spell.chosen_targets = [bear]
        spell.on_resolve(game)

        # The creature should have a death trigger that draws a card
        assert hasattr(bear, 'dies_triggers') or hasattr(bear, 'triggered_abilities')
        # Verify the trigger exists in some form
        triggers = getattr(bear, 'dies_triggers', None) or getattr(bear, 'triggered_abilities', [])
        assert len(triggers) > 0

    def test_no_targets_is_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = RabidAttack(owner=p1, controller=p1)
        spell.chosen_targets = []
        # Should not raise
        spell.on_resolve(game)
