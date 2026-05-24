"""Audited tests for FDN 5 — Celestial Armor."""

from __future__ import annotations

import pytest

from card_impl import CelestialArmor
from benchmarks.sos.workspace.engine.card import Artifact, Creature
from benchmarks.sos.workspace.engine.continuous_effects import Layer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import create_game


class TestCelestialArmorBasics:
    """Basic card properties."""

    def test_is_artifact(self) -> None:
        card = CelestialArmor(owner=None)
        assert isinstance(card, Artifact)

    def test_name(self) -> None:
        card = CelestialArmor(owner=None)
        assert card.name == "Celestial Armor"

    def test_mana_cost(self) -> None:
        card = CelestialArmor(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{W}")

    def test_has_flash(self) -> None:
        card = CelestialArmor(owner=None)
        assert Keyword.FLASH in card.keywords

    def test_has_equipment_subtype(self) -> None:
        card = CelestialArmor(owner=None)
        assert "Equipment" in card.subtypes


class TestCelestialArmorETB:
    """ETB: attach to target creature, grant hexproof+indestructible until EOT."""

    def _setup_etb(self):
        game = create_game()
        p1 = game.players[0]
        creature = Creature(
            name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1
        )
        armor = CelestialArmor(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(armor)
        armor.chosen_targets = [creature]
        armor.on_resolve(game)
        return game, armor, creature, p1

    def test_etb_attaches_to_target_creature(self) -> None:
        game, armor, creature, p1 = self._setup_etb()
        assert armor.attached_to is creature

    def test_etb_grants_hexproof_until_eot(self) -> None:
        game, armor, creature, p1 = self._setup_etb()
        game.effect_manager.apply_all(game)
        assert Keyword.HEXPROOF in creature.keywords

    def test_etb_grants_indestructible_until_eot(self) -> None:
        game, armor, creature, p1 = self._setup_etb()
        game.effect_manager.apply_all(game)
        assert Keyword.INDESTRUCTIBLE in creature.keywords

    def test_etb_no_creature_does_not_crash(self) -> None:
        """If no valid creature target, on_resolve completes without error."""
        game = create_game()
        p1 = game.players[0]
        armor = CelestialArmor(owner=p1, controller=p1)
        game.get_battlefield(p1).add(armor)
        armor.chosen_targets = []
        armor.on_resolve(game)
        assert armor.attached_to is None


class TestCelestialArmorEquipEffects:
    """Equipped creature gets +2/+0 and flying (continuous effects)."""

    def _setup_equipped(self):
        game = create_game()
        p1 = game.players[0]
        creature = Creature(
            name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1
        )
        armor = CelestialArmor(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(armor)
        armor.equip(creature, game)
        return game, armor, creature, p1

    def test_equipped_creature_gets_plus2_power(self) -> None:
        game, armor, creature, p1 = self._setup_equipped()
        game.effect_manager.apply_all(game)
        assert creature.modified_power == 4  # 2 + 2

    def test_equipped_creature_has_flying(self) -> None:
        game, armor, creature, p1 = self._setup_equipped()
        game.effect_manager.apply_all(game)
        assert Keyword.FLYING in creature.keywords

    def test_pt_effect_in_layer_7c(self) -> None:
        game, armor, creature, p1 = self._setup_equipped()
        effects = game.effect_manager.get_effects_by_source(armor)
        pt_effects = [e for e in effects if e.layer == Layer.POWER_TOUGHNESS]
        assert len(pt_effects) >= 1

    def test_flying_effect_in_layer_6(self) -> None:
        game, armor, creature, p1 = self._setup_equipped()
        effects = game.effect_manager.get_effects_by_source(armor)
        ability_effects = [e for e in effects if e.layer == Layer.ABILITY]
        assert len(ability_effects) >= 1


class TestCelestialArmorEquipAbility:
    """Equip {3}{W} activated ability."""

    def test_has_equip_activated_ability(self) -> None:
        armor = CelestialArmor(owner=None)
        abilities = armor.get_activated_abilities()
        assert len(abilities) >= 1

    def test_equip_ability_costs_4_mana(self) -> None:
        """Equip costs {3}{W} approximated as generic 4."""
        game = create_game()
        p1 = game.players[0]
        creature = Creature(
            name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1
        )
        armor = CelestialArmor(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(armor)
        # Not enough mana
        p1.mana_pool.add(ManaType.COLORLESS, 3)
        ability = armor.get_activated_abilities()[0]
        result = ability.cost(game, armor)
        assert result is False

    def test_equip_ability_succeeds_with_enough_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        creature = Creature(
            name="Bear", base_power=2, base_toughness=2, owner=p1, controller=p1
        )
        armor = CelestialArmor(owner=p1, controller=p1)
        bf = game.get_battlefield(p1)
        bf.add(creature)
        bf.add(armor)
        p1.mana_pool.add(ManaType.COLORLESS, 4)
        ability = armor.get_activated_abilities()[0]
        result = ability.cost(game, armor)
        assert result is True

