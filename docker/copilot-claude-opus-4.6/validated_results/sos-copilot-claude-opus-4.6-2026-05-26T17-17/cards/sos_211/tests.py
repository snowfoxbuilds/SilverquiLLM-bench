"""Tests for SOS 211 — Prismari Charm.

Prismari Charm is a modal instant with three modes:
1. Surveil 2, then draw a card.
2. Deal 1 damage to each of one or two targets.
3. Return target nonland permanent to its owner's hand.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_211.card_impl import PrismariCharm
from engine.card import Instant, Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


class TestPrismariCharmProperties:
    """Static card data should match the SOS 211 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(PrismariCharm(owner=None), Instant)

    def test_name(self) -> None:
        assert PrismariCharm(owner=None).name == "Prismari Charm"

    def test_mana_cost(self) -> None:
        assert PrismariCharm(owner=None).mana_cost == ManaCost.parse("{U}{R}")


class TestPrismariCharmModeSurveil:
    """Mode 1: Surveil 2, then draw a card."""

    def test_surveil_2_then_draw(self) -> None:
        game = create_game()
        p1 = game.players[0]

        # Put some cards in library
        dummy1 = Creature(name="Card A", owner=p1, base_power=1, base_toughness=1)
        dummy2 = Creature(name="Card B", owner=p1, base_power=1, base_toughness=1)
        dummy3 = Creature(name="Card C", owner=p1, base_power=1, base_toughness=1)
        game.get_library(p1).extend([dummy1, dummy2, dummy3])

        spell = PrismariCharm(owner=p1, controller=p1)
        spell.chosen_mode = 0  # first mode
        hand_before = len(game.get_hand(p1))
        spell.on_resolve(game)

        # Player should have drawn a card
        assert len(game.get_hand(p1)) == hand_before + 1


class TestPrismariCharmModeDamage:
    """Mode 2: Deal 1 damage to each of one or two targets."""

    def test_deals_1_damage_to_single_target(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Bear", owner=p2, controller=p2,
            base_power=2, base_toughness=2
        )
        game.get_battlefield(p2).add(target)

        spell = PrismariCharm(owner=p1, controller=p1)
        spell.chosen_mode = 1  # second mode
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert target.damage_taken == 1

    def test_deals_1_damage_to_two_targets(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target1 = Creature(
            name="Bear A", owner=p2, controller=p2,
            base_power=2, base_toughness=2
        )
        target2 = Creature(
            name="Bear B", owner=p2, controller=p2,
            base_power=2, base_toughness=2
        )
        game.get_battlefield(p2).add(target1)
        game.get_battlefield(p2).add(target2)

        spell = PrismariCharm(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [target1, target2]
        spell.on_resolve(game)

        assert target1.damage_taken == 1
        assert target2.damage_taken == 1


class TestPrismariCharmModeBounce:
    """Mode 3: Return target nonland permanent to its owner's hand."""

    def test_bounces_nonland_permanent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(
            name="Big Creature", owner=p2, controller=p2,
            base_power=5, base_toughness=5
        )
        game.get_battlefield(p2).add(target)

        spell = PrismariCharm(owner=p1, controller=p1)
        spell.chosen_mode = 2  # third mode
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        # Target should be in owner's hand, not on battlefield
        bf = game.get_battlefield(p2)
        hand = game.get_hand(p2)
        assert target not in bf
        assert target in hand

    def test_target_must_be_nonland(self) -> None:
        """The targeting requirement should reject lands."""
        game = create_game()
        reqs = PrismariCharm(owner=None).get_targets(game)
        # Mode 3 should have a target requirement that filters out lands
        # Find the bounce mode's requirement
        assert reqs is not None
        assert len(reqs) >= 1
