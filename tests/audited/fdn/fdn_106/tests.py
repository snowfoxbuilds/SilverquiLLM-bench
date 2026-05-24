"""Audited tests for FDN 106 — Loot, Exuberant Explorer."""

from __future__ import annotations

from card_impl import LootExuberantExplorer
from engine.card import ActivatedAbility, Creature, Land
from engine.types import CardType, ManaCost, ManaType, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestLootBasics:
    """Basic card properties."""

    def test_is_creature(self) -> None:
        card = LootExuberantExplorer(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = LootExuberantExplorer(owner=None)
        assert card.name == "Loot, Exuberant Explorer"

    def test_mana_cost(self) -> None:
        card = LootExuberantExplorer(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{G}")

    def test_power_toughness(self) -> None:
        card = LootExuberantExplorer(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 4

    def test_subtypes(self) -> None:
        card = LootExuberantExplorer(owner=None)
        assert "Beast" in card.subtypes
        assert "Noble" in card.subtypes


class TestLootAdditionalLand:
    """Grants additional land play."""

    def test_register_triggers_grants_additional_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        loot = LootExuberantExplorer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(loot)
        loot.register_triggers(game)
        assert getattr(p1, "additional_lands", 0) >= 1

    def test_unregister_removes_additional_land(self) -> None:
        game = create_game()
        p1 = game.players[0]
        loot = LootExuberantExplorer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(loot)
        loot.register_triggers(game)
        loot.unregister_triggers(game)
        assert getattr(p1, "additional_lands", 0) == 0


class TestLootActivatedAbility:
    """Activated ability: look at top 6, put creature onto battlefield."""

    def test_has_activated_ability(self) -> None:
        card = LootExuberantExplorer(owner=None)
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_ability_requires_6_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        loot = LootExuberantExplorer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(loot)
        p1.mana_pool.add(ManaType.COLORLESS, 5)
        ability = loot.get_activated_abilities()[0]
        result = ability.cost(game, loot)
        assert result is False

    def test_ability_succeeds_with_enough_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        loot = LootExuberantExplorer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(loot)
        p1.mana_pool.add(ManaType.COLORLESS, 6)
        ability = loot.get_activated_abilities()[0]
        result = ability.cost(game, loot)
        assert result is True

    def test_ability_taps_loot(self) -> None:
        game = create_game()
        p1 = game.players[0]
        loot = LootExuberantExplorer(owner=p1, controller=p1)
        game.get_battlefield(p1).add(loot)
        p1.mana_pool.add(ManaType.COLORLESS, 6)
        ability = loot.get_activated_abilities()[0]
        ability.cost(game, loot)
        assert getattr(loot, "is_tapped", False) or getattr(loot, "tapped", False)
