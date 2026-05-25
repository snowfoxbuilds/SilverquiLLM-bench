"""Audited tests for FDN 72 — Tinybones, Bauble Burglar."""

from __future__ import annotations

from card_impl import TinybonesBaubleBurglar
from engine.card import Creature
from engine.types import ManaCost, Zone
from test_utils import create_game


class TestTinybonesBaubleBurglarBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = TinybonesBaubleBurglar(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = TinybonesBaubleBurglar(owner=None)
        assert card.name == "Tinybones, Bauble Burglar"

    def test_mana_cost(self) -> None:
        card = TinybonesBaubleBurglar(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{B}")

    def test_power_toughness(self) -> None:
        card = TinybonesBaubleBurglar(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 3

    def test_subtypes(self) -> None:
        card = TinybonesBaubleBurglar(owner=None)
        assert "Skeleton" in card.subtypes
        assert "Rogue" in card.subtypes

    def test_is_legendary(self) -> None:
        card = TinybonesBaubleBurglar(owner=None)
        assert "Legendary" in getattr(card, "supertypes", set())


class TestTinybonesBaubleBurglarAbility:
    """Tap ability: each opponent discards a card."""

    def test_has_activated_ability(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TinybonesBaubleBurglar(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities(game)
        assert len(abilities) >= 1

    def test_ability_tap_cost(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = TinybonesBaubleBurglar(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities(game)
        assert abilities[0].tap_cost is True

    def test_opponent_discards(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TinybonesBaubleBurglar(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        filler = Creature(name="Filler", base_power=1, base_toughness=1, owner=p2)
        p2.zones[Zone.HAND].add(filler)
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)
        assert len(p2.zones[Zone.HAND].get_all()) == 0

    def test_no_crash_if_opponent_hand_empty(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TinybonesBaubleBurglar(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)
        abilities = card.get_activated_abilities(game)
        abilities[0].effect(game)  # Should not crash
        assert len(p2.zones[Zone.HAND].get_all()) == 0
