"""Audited tests for FDN 32 — Cephalid Inkmage."""

from __future__ import annotations

from card_impl import CephalidInkmage
from engine.card import Creature
from engine.player import DeterministicPlayer
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestCephalidInkmageBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = CephalidInkmage(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = CephalidInkmage(owner=None)
        assert card.name == "Cephalid Inkmage"

    def test_mana_cost(self) -> None:
        card = CephalidInkmage(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{U}")

    def test_power_toughness(self) -> None:
        card = CephalidInkmage(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_subtypes(self) -> None:
        card = CephalidInkmage(owner=None)
        assert "Octopus" in card.subtypes
        assert "Wizard" in card.subtypes


class TestCephalidInkmageETB:
    """When this creature enters, surveil 3."""

    def test_surveil_puts_cards_in_graveyard(self) -> None:
        """When player chooses yes for all, cards go to graveyard."""
        game = create_game(scripts=([True, True, True], []))
        p1 = game.players[0]
        # Add 3 cards to library
        for i in range(3):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        card = CephalidInkmage(owner=p1, controller=p1)
        card.on_resolve(game)
        gy_count = len(list(p1.zones[Zone.GRAVEYARD].get_all()))
        assert gy_count == 3

    def test_surveil_keeps_cards_on_top(self) -> None:
        """When player chooses no for all, cards stay in library."""
        game = create_game(scripts=([False, False, False], []))
        p1 = game.players[0]
        for i in range(3):
            c = Creature(name=f"Lib{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        card = CephalidInkmage(owner=p1, controller=p1)
        card.on_resolve(game)
        gy_count = len(list(p1.zones[Zone.GRAVEYARD].get_all()))
        assert gy_count == 0


class TestCephalidInkmageThreshold:
    """Threshold — can't be blocked when 7+ cards in graveyard."""

    def _setup(self, gy_count: int = 0):
        game = create_game()
        p1 = game.players[0]
        card = CephalidInkmage(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        for i in range(gy_count):
            c = Creature(name=f"GY{i}", base_power=1, base_toughness=1, owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        card.register_triggers(game)
        game.effect_manager.apply_all(game)
        return game, card, p1

    def test_not_unblockable_below_threshold(self) -> None:
        game, card, p1 = self._setup(gy_count=5)
        assert not getattr(card, "unblockable", False)

    def test_unblockable_at_threshold(self) -> None:
        game, card, p1 = self._setup(gy_count=7)
        assert getattr(card, "unblockable", False) is True

    def test_unblockable_above_threshold(self) -> None:
        game, card, p1 = self._setup(gy_count=10)
        assert getattr(card, "unblockable", False) is True
