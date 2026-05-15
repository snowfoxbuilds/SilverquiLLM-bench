"""Audited tests for FDN 159 — Mocking Sprite."""

from __future__ import annotations

from card_impl import MockingSprite
from engine.card import Creature
from engine.types import Keyword, ManaCost
from tests.test_utils import create_game


class TestMockingSpriteBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = MockingSprite(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = MockingSprite(owner=None)
        assert card.name == "Mocking Sprite"

    def test_mana_cost(self) -> None:
        card = MockingSprite(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{U}")

    def test_power_toughness(self) -> None:
        card = MockingSprite(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 1

    def test_has_flying(self) -> None:
        card = MockingSprite(owner=None)
        assert Keyword.FLYING in card.keywords

    def test_subtypes(self) -> None:
        card = MockingSprite(owner=None)
        assert "Faerie" in card.subtypes
        assert "Rogue" in card.subtypes


class TestMockingSpriteCostReduction:
    """Instant and sorcery spells you cast cost {1} less."""

    def test_provides_cost_reduction_flag(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sprite = MockingSprite(owner=p1, controller=p1)
        game.get_battlefield(p1).add(sprite)
        sprite.register_triggers(game)
        assert getattr(sprite, "_provides_cost_reduction", False)
