"""Audited tests for FDN 194 — Etali, Primal Storm."""
from __future__ import annotations
from card_impl import EtaliPrimalStorm
from engine.card import CardImpl, Creature
from engine.types import CardType, ManaCost, Zone
from test_utils import create_game

class TestEtaliBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = EtaliPrimalStorm(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EtaliPrimalStorm(owner=None)
        assert card.name == 'Etali, Primal Storm'

    def test_mana_cost(self) -> None:
        card = EtaliPrimalStorm(owner=None)
        assert card.mana_cost == ManaCost.parse('{4}{R}{R}')

    def test_power_toughness(self) -> None:
        card = EtaliPrimalStorm(owner=None)
        assert card.base_power == 6
        assert card.base_toughness == 6

    def test_is_legendary(self) -> None:
        card = EtaliPrimalStorm(owner=None)
        assert 'Legendary' in getattr(card, 'supertypes', set())

    def test_subtypes(self) -> None:
        card = EtaliPrimalStorm(owner=None)
        assert 'Elder' in card.subtypes
        assert 'Dinosaur' in card.subtypes
