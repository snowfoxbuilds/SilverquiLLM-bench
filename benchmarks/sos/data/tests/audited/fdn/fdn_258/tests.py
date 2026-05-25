"""Audited tests for FDN 258 — Swiftfoot Boots."""

from __future__ import annotations

import pytest

from card_impl import SwiftfootBoots
from engine.card import Artifact, Creature
from engine.continuous_effects import Layer
from engine.types import CardType, Keyword, ManaCost, ManaType
from test_utils import create_game


class TestSwiftfootBootsBasics:
    """Basic card properties."""

    def test_is_artifact(self) -> None:
        card = SwiftfootBoots(owner=None)
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        card = SwiftfootBoots(owner=None)
        assert card.name == "Swiftfoot Boots"

    def test_mana_cost(self) -> None:
        card = SwiftfootBoots(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}")

    def test_has_equipment_subtype(self) -> None:
        card = SwiftfootBoots(owner=None)
        assert "Equipment" in card.subtypes


class TestSwiftfootBootsEquipEffects:
    """Equipped creature has hexproof and haste."""

    def _setup_equipped(self):
        game = create_game()
        p1 = game.players[0]
        creature = Creature(
            name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1
        )
        boots = SwiftfootBoots(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(boots)
        boots.equip(creature, game)
        return game, boots, creature, p1

    def test_equipped_creature_has_hexproof(self) -> None:
        game, boots, creature, p1 = self._setup_equipped()
        game.effect_manager.apply_all(game)
        assert Keyword.HEXPROOF in creature.keywords

    def test_equipped_creature_has_haste(self) -> None:
        game, boots, creature, p1 = self._setup_equipped()
        game.effect_manager.apply_all(game)
        assert Keyword.HASTE in creature.keywords

    def test_effect_in_layer_6(self) -> None:
        game, boots, creature, p1 = self._setup_equipped()
        effects = game.effect_manager.get_effects_by_source(boots)
        ability_effects = [e for e in effects if e.layer == Layer.ABILITY]
        assert len(ability_effects) >= 1

    def test_effect_does_not_apply_when_not_attached(self) -> None:
        """If boots are not attached to anything, no keywords granted."""
        game = create_game()
        p1 = game.players[0]
        creature = Creature(
            name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1
        )
        boots = SwiftfootBoots(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(boots)
        # equip to register effects, then detach
        boots.equip(creature, game)
        boots.attached_to = None
        game.effect_manager.apply_all(game)
        # Creature should NOT have hexproof from boots since not attached
        assert Keyword.HEXPROOF not in creature.keywords

    def test_equip_sets_attached_to(self) -> None:
        game, boots, creature, p1 = self._setup_equipped()
        assert boots.attached_to is creature


class TestSwiftfootBootsEquipAbility:
    """Equip {1} activated ability."""

    def test_has_equip_activated_ability(self) -> None:
        boots = SwiftfootBoots(owner=None)
        abilities = boots.get_activated_abilities()
        assert len(abilities) >= 1

    def test_equip_costs_1_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        boots = SwiftfootBoots(owner=p1, controller=p1)
        game.get_battlefield(p1).add(boots)
        # No mana — should fail
        ability = boots.get_activated_abilities()[0]
        result = ability.cost(game, boots)
        assert result is False

    def test_equip_succeeds_with_1_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        boots = SwiftfootBoots(owner=p1, controller=p1)
        game.get_battlefield(p1).add(boots)
        p1.mana_pool.add(ManaType.COLORLESS, 1)
        ability = boots.get_activated_abilities()[0]
        result = ability.cost(game, boots)
        assert result is True

